# backend/main.py

import base64
import json
import logging
import os
import sys
import re
import requests
from bs4 import BeautifulSoup

import functions_framework
from google.cloud import secretmanager
import resend

# Import the correct, powerful library for Vertex AI
import vertexai
from vertexai.generative_models import GenerativeModel

# --- Project Configuration ---
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
    logging.error("GCP_PROJECT could not be determined. Exiting.")
    sys.exit(1) 

# --- Logging Setup ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variables ---
gemini_model = None
secrets = {}

def initialize_vertex_ai():
    """Initializes the Vertex AI client and model if they are not already loaded."""
    global gemini_model
    if gemini_model is None:
        logging.info("Cold start: Initializing Vertex AI...")
        try:
            vertexai.init(project=PROJECT_ID, location=REGION)
            gemini_model = GenerativeModel("gemini-2.5-flash")
            logging.info("Vertex AI initialized successfully with gemini-2.5-flash.")
            return True # <-- Возвращаем успех
        except Exception as e:
            logging.error(f"Failed to initialize Vertex AI: {e}", exc_info=True)
            return False # <-- Возвращаем неудачу, но НЕ выбрасываем исключение

def access_secret_version(secret_id, version_id="latest"):
    """Accesses a secret from Secret Manager, with caching."""
    if secret_id in secrets:
        return secrets[secret_id]
    
    logging.info(f"Accessing secret: {secret_id}")
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data.decode("UTF-8").strip()
    secrets[secret_id] = payload
    return payload

def send_email(to_email, from_email, subject, html_content):
    """Sends an email using the Resend API."""
    logging.info(f"Attempting to send email to {to_email} via Resend")
    try:
        api_key = access_secret_version("RESEND_API_KEY")
        resend.api_key = api_key
        params = {
            "from": f"Fraud Digest <{from_email}>",
            "to": [to_email],
            "subject": subject,
            "html": html_content,
        }
        email = resend.Emails.send(params)
        logging.info(f"Email sent successfully to {to_email}. Email ID: {email.get('id')}")
        return True
    except Exception as e:
        logging.error(f"An error occurred while sending email: {e}", exc_info=True)
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
    """
    Extracts named entities using the Gemini model with a more robust prompt and parsing.
    """
    if not text or not gemini_model:
        return []
    
    logging.info("Extracting entities with Gemini...")
    truncated_text = text[:15000]

    # Improved prompt to strongly encourage JSON output
    prompt = f"""
    Analyze the following news article text and extract all named entities.
    Your response MUST be ONLY a valid JSON array of objects. Do not include ```json, ```, or any other text.
    Each object must have two keys: "entity" and "label".
    Example: [ {{"entity": "Elon Musk", "label": "PERSON"}}, {{"entity": "Tesla", "label": "ORG"}} ]
    If no entities are found, return an empty JSON array: [].

    Article text:
    ---
    {truncated_text}
    ---
    """
    
    try:
        response = gemini_model.generate_content(prompt)
        
        # More robust parsing: find the JSON block within the response text
        response_text = response.text
        logging.info(f"Gemini raw response: {response_text}")

        # Find the start and end of the JSON array
        json_start = response_text.find('[')
        json_end = response_text.rfind(']') + 1

        if json_start != -1 and json_end != 0:
            json_str = response_text[json_start:json_end]
            entities = json.loads(json_str)
            logging.info(f"Successfully parsed {len(entities)} entities from Gemini response.")
            return [(item.get("entity"), item.get("label")) for item in entities]
        else:
            logging.error(f"Could not find a valid JSON array in Gemini response: {response_text}")
            return []

    except json.JSONDecodeError:
        logging.error(f"Failed to decode JSON from Gemini response snippet: {response_text[json_start:json_end]}")
        return []
    except Exception as e:
        logging.error(f"An error occurred during Gemini API call: {e}", exc_info=True)
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
    The main entry point, wrapping the core logic to ensure Pub/Sub messages
    are always acknowledged, preventing infinite retries.
    """
    try:
        _handle_message(cloud_event)
    except Exception as e:
        logging.critical(f"A critical, unhandled error occurred in the main handler: {e}", exc_info=True)
    
    logging.info("Function execution finished, message acknowledged.")

def _handle_message(cloud_event):
    """The core logic of the function."""
    logging.info("Core message handling started.")
    
    initialize_vertex_ai()

    message_data_encoded = cloud_event.data.get("message", {}).get("data")
    if not message_data_encoded:
        logging.error("No data in Pub/Sub message.")
        return

    message_data = base64.b64decode(message_data_encoded).decode("utf-8")
    data = parse_message_safely(message_data)
    if not data: return

    url = data.get("url")
    email = data.get("email")

    logging.info(f"Processing request for user: {email}")
    article_text = get_article_text(url)
    
    if not article_text:
        logging.warning(f"Could not retrieve text from {url}. Sending failure email.")
        subject = f"Failed to analyze URL: {url}"
        body = f"<h1>Analysis Failed</h1><p>Sorry, we could not retrieve the article content from the provided URL.</p><p>URL: {url}</p>"
    else:
        entities = extract_entities_with_gemini(article_text)
        subject = f"Fraud Digest Analysis (Gemini) for: {url}"
        body = f"<h1>Analysis Results</h1><p>Found {len(entities)} entities in the article from {url}.</p>"
        if entities:
            body += "<table border='1' style='border-collapse: collapse; width: 100%;'><tr><th style='padding: 8px; text-align: left;'>Entity</th><th style='padding: 8px; text-align: left;'>Label</th></tr>"
            for entity, label in entities:
                body += f"<tr><td style='padding: 8px;'>{entity}</td><td style='padding: 8px;'>{label}</td></tr>"
            body += "</table>"
        else:
            body += "<p>No entities were found.</p>"
    
    from_email = "digest@axionym.com" 
    send_email(email, from_email, subject, body)