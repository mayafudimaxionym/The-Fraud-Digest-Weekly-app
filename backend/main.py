# backend/main.py

import base64
import json
import logging
import os
import sys
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

import functions_framework
from google.cloud import secretmanager
from google.cloud import firestore
import resend

# Import the correct, powerful library for Vertex AI
import vertexai
from vertexai.generative_models import GenerativeModel

# --- Project Configuration ---
# Attempt to automatically determine Project ID from the metadata server,
# which is the standard way in Google Cloud environments.
PROJECT_ID = None
REGION = "europe-west1" 

try:
    response = requests.get("http://metadata.google.internal/computeMetadata/v1/project/project-id", headers={"Metadata-Flavor": "Google"}, timeout=2)
    if response.status_code == 200:
        PROJECT_ID = response.text
except requests.exceptions.RequestException:
    logging.warning("Could not contact metadata server, falling back to env var.")
    PROJECT_ID = os.environ.get("GCP_PROJECT")

if not PROJECT_ID:
    logging.critical("GCP_PROJECT could not be determined. The function cannot proceed.")
    sys.exit(1) 

# --- Logging Setup ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variables ---
# These are declared globally to be reused across function invocations (handling "warm starts")
# This avoids re-initializing clients on every request, which saves time and resources.
gemini_model = None
firestore_db = None
secrets = {} # Simple in-memory cache for secrets

def initialize_vertex_ai():
    """
    Initializes the Vertex AI client and model if they haven't been already.
    This function is designed to handle "cold starts" gracefully.
    Returns True on success, False on failure.
    """
    global gemini_model
    if gemini_model is None:
        logging.info("Cold start: Initializing Vertex AI client...")
        try:
            vertexai.init(project=PROJECT_ID, location=REGION)
            # Use the correct and available model name for fast, efficient tasks.
            gemini_model = GenerativeModel("gemini-1.5-flash-001")
            logging.info("Vertex AI initialized successfully with gemini-1.5-flash-001.")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize Vertex AI: {e}", exc_info=True)
            return False
    return True

def initialize_firestore():
    """
    Initializes the Firestore client if it hasn't been already.
    Handles "cold starts" for database connections.
    Returns True on success, False on failure.
    """
    global firestore_db
    if firestore_db is None:
        logging.info("Cold start: Initializing Firestore client...")
        try:
            # The client automatically uses the project's credentials and configuration.
            firestore_db = firestore.Client()
            logging.info("Firestore client initialized successfully.")
            return True
        except Exception as e:
            logging.error(f"Failed to initialize Firestore: {e}", exc_info=True)
            return False
    return True

def access_secret_version(secret_id, version_id="latest"):
    """
    Accesses a secret from Secret Manager.
    Uses a simple in-memory dictionary to cache secrets for the lifetime of the function instance.
    """
    if secret_id in secrets:
        return secrets[secret_id]
    
    logging.info(f"Accessing secret from Secret Manager: {secret_id}")
    try:
        client = secretmanager.SecretManagerServiceClient()
        name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
        response = client.access_secret_version(request={"name": name})
        payload = response.payload.data.decode("UTF-8").strip()
        secrets[secret_id] = payload # Cache the secret
        return payload
    except Exception as e:
        logging.error(f"Failed to access secret {secret_id}: {e}", exc_info=True)
        return None

def save_to_firestore(url, user_email, status, entities=None, error_message=None):
    """
    Saves the analysis result as a new document in the 'analyses' collection in Firestore.
    """
    if not firestore_db:
        logging.error("Firestore client not initialized. Cannot save result.")
        return

    try:
        logging.info(f"Saving analysis for {url} to Firestore with status: {status}")
        # Create a new document with an auto-generated ID in the 'analyses' collection.
        doc_ref = firestore_db.collection("analyses").document()
        
        # Structure the data to be saved.
        analysis_record = {
            "url": url,
            "user_email": user_email,
            "status": status, # "SUCCESS" or "FAILURE"
            "timestamp": datetime.now(timezone.utc), # Use timezone-aware UTC timestamp
            "entities": entities or [], # Store the list of entities, or an empty list
            "error_message": error_message or "" # Store an error message if the analysis failed
        }
        
        doc_ref.set(analysis_record)
        logging.info(f"Successfully saved analysis to Firestore. Document ID: {doc_ref.id}")
    except Exception as e:
        logging.error(f"Failed to save to Firestore: {e}", exc_info=True)

def send_notification_email(to_email, subject, html_content):
    """Sends a simple notification email using the Resend API."""
    logging.info(f"Attempting to send notification email to {to_email}")
    try:
        api_key = access_secret_version("RESEND_API_KEY")
        if not api_key:
            logging.error("Resend API key is not available. Cannot send email.")
            return False
            
        resend.api_key = api_key
        from_email = "digest@axionym.com" # This should be a verified sender in Resend
        params = {
            "from": f"Fraud Digest Notifier <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        email = resend.Emails.send(params)
        logging.info(f"Notification email sent successfully to {to_email}. Email ID: {email.get('id')}")
        return True
    except Exception as e:
        logging.error(f"An error occurred while sending notification email: {e}", exc_info=True)
        return False

def get_article_text(url):
    """Fetches and extracts all paragraph text from a given URL."""
    logging.info(f"Fetching text from URL: {url}")
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        paragraphs = soup.find_all('p')
        article_text = ' '.join([p.get_text() for p in paragraphs])
        logging.info(f"Successfully extracted text from {url}. Length: {len(article_text)} chars.")
        return article_text
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching URL {url}: {e}")
        return None

def extract_entities_with_gemini(text):
    """Sends the article text to the Gemini model to perform NER."""
    if not text or not gemini_model:
        return []
    logging.info("Extracting entities with Gemini...")
    # Truncate text to fit within model context limits if necessary
    truncated_text = text[:15000] 
    prompt = f"""
    Analyze the following news article text and extract all named entities.
    Categorize entities using standard labels like PERSON, ORG, GPE, etc.
    Your response MUST be a valid JSON array of objects, where each object has two keys: "entity" and "label".
    Example: [ {{"entity": "Elon Musk", "label": "PERSON"}}, {{"entity": "Tesla", "label": "ORG"}} ]
    If no entities are found, return an empty JSON array: [].
    Do not include any explanations or markdown formatting in your response.
    Article text:
    ---
    {truncated_text}
    ---
    """
    try:
        response = gemini_model.generate_content(prompt)
        # Clean up potential markdown formatting from the model's response
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "").strip()
        logging.info(f"Gemini raw response received, attempting to parse JSON.")
        entities = json.loads(cleaned_response)
        logging.info(f"Successfully parsed {len(entities)} entities from Gemini response.")
        # Convert from list of dicts to list of tuples for consistency
        return [(item.get("entity"), item.get("label")) for item in entities]
    except Exception as e:
        logging.error(f"An error occurred during Gemini API call or JSON parsing: {e}", exc_info=True)
        return []

def parse_message_safely(message_str):
    """A robust parser for the Pub/Sub message."""
    logging.info(f"Attempting to parse message: {message_str}")
    try:
        data = json.loads(message_str)
        if "url" in data and "email" in data:
            logging.info("Successfully parsed as valid JSON.")
            return data
    except json.JSONDecodeError:
        logging.warning("Message is not valid JSON, attempting regex fallback.")
    
    # Fallback for malformed strings that are not perfect JSON
    url_match = re.search(r'"url"\s*:\s*"(.*?)"', message_str) or re.search(r"url:\s*([^,}\s]+)", message_str)
    email_match = re.search(r'"email"\s*:\s*"(.*?)"', message_str) or re.search(r"email:\s*([^,}\s]+)", message_str)
    url = url_match.group(1) if url_match else None
    email = email_match.group(1) if email_match else None
    
    if url and email:
        logging.info(f"Successfully parsed with fallback regex: url={url}, email={email}")
        return {"url": url, "email": email}
        
    logging.error(f"Failed to parse URL and/or email from message: {message_str}")
    return None

@functions_framework.cloud_event
def main(cloud_event):
    """
    Main entry point for the Cloud Function, triggered by a Pub/Sub message.
    The function's success or failure determines if the message is acknowledged (ACK) or not (NACK).
    A NACK will cause Pub/Sub to attempt redelivery.
    """
    # The core logic is wrapped in a separate function for clarity.
    # If _handle_message raises an exception, the Functions Framework will catch it,
    # log it, and the message will be NACK'd for redelivery.
    _handle_message(cloud_event)
    logging.info("Function execution completed successfully.")

def _handle_message(cloud_event):
    """The core logic of the function."""
    logging.info("Core message handling started.")
    
    # Initialize clients. If any fails, log the error and exit.
    # The exception will be caught by the framework, causing a NACK.
    if not initialize_vertex_ai() or not initialize_firestore():
        logging.critical("Aborting due to failed client initialization.")
        # Raising an exception is better than returning, as it signals a retryable error.
        raise RuntimeError("Failed to initialize necessary GCP clients.")

    message_data_encoded = cloud_event.data.get("message", {}).get("data")
    if not message_data_encoded:
        logging.error("No data in Pub/Sub message. Acknowledging to remove from queue.")
        return # Exit gracefully, message will be ACK'd

    message_data = base64.b64decode(message_data_encoded).decode("utf-8")
    data = parse_message_safely(message_data)
    if not data:
        logging.error("Could not parse message content. Acknowledging to remove from queue.")
        return # Exit gracefully, message will be ACK'd

    url = data.get("url")
    email = data.get("email")

    logging.info(f"Processing request for user: {email}, url: {url}")
    article_text = get_article_text(url)
    
    if not article_text:
        logging.warning(f"Could not retrieve text from {url}.")
        error_msg = "Could not retrieve article content from the provided URL."
        save_to_firestore(url, email, "FAILURE", error_message=error_msg)
        subject = f"Failed to analyze URL: {url}"
        body = f"<h1>Analysis Failed</h1><p>{error_msg}</p><p>URL: {url}</p>"
    else:
        entities = extract_entities_with_gemini(article_text)
        save_to_firestore(url, email, "SUCCESS", entities=entities)
        subject = f"Fraud Digest Analysis Complete for: {url}"
        body = f"<h1>Analysis Complete</h1><p>The analysis for {url} is complete and has been saved. You can view the results in the application soon.</p>"
    
    send_notification_email(email, subject, body)
    