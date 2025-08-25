# backend/main.py

import base64
import json
import logging
import os
import sys
import re
import requests
from bs4 import BeautifulSoup
import spacy

import functions_framework # pyright: ignore[reportMissingImports]

from google.cloud import secretmanager
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Project Configuration ---
#PROJECT_ID = os.environ.get("GCP_PROJECT")
response = requests.get("http://metadata.google.internal/computeMetadata/v1/project/project-id", headers={"Metadata-Flavor": "Google"})
PROJECT_ID = response.text if response.status_code == 200 else PROJECT_ID = os.environ.get("GCP_PROJECT")
if not PROJECT_ID:
    logging.error("GCP_PROJECT environment variable is not set and could not fetch from metadata server.")
    sys.exit(1)

# --- Logging Setup ---
# Set log level from environment variable, default to INFO
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(stream=sys.stdout, level=LOG_LEVEL,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variables ---
nlp = None
gmail_service = None
secrets = {}

def access_secret_version(secret_id, version_id="latest"):
    """Accesses a secret version from Google Cloud Secret Manager."""
    if secret_id in secrets:
        return secrets[secret_id]
    
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    payload = response.payload.data.decode("UTF-8")
    secrets[secret_id] = payload
    return payload

def initialize_gmail_service():
    """Initializes the Gmail API service using stored credentials."""
    global gmail_service
    if gmail_service is None:
        logging.info("Initializing Gmail service...")
        try:
            client_id = access_secret_version("GMAIL_CLIENT_ID")
            client_secret = access_secret_version("GMAIL_CLIENT_SECRET")
            refresh_token = access_secret_version("GMAIL_REFRESH_TOKEN")

            creds = Credentials.from_authorized_user_info(
                info={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                },
                scopes=['https://www.googleapis.com/auth/gmail.send']
            )
            gmail_service = build('gmail', 'v1', credentials=creds)
            logging.info("Gmail service initialized successfully.")
        except Exception as e:
            logging.error(f"Failed to initialize Gmail service: {e}", exc_info=True)
            raise

def send_email(to_email, subject, message_text):
    """Sends an email using the Gmail API."""
    try:
        message = {
            'raw': base64.urlsafe_b64encode(
                f"To: {to_email}\r\n"
                f"Subject: {subject}\r\n"
                f"Content-Type: text/html; charset=utf-8\r\n\r\n"
                f"{message_text}".encode('utf-8')
            ).decode('ascii')
        }
        sent_message = gmail_service.users().messages().send(userId='me', body=message).execute()
        logging.info(f"Email sent successfully to {to_email}. Message ID: {sent_message['id']}")
        return sent_message
    except HttpError as error:
        logging.error(f"An error occurred while sending email: {error}")
        return None

# ... (The functions download_and_load_spacy_model, get_article_text, extract_entities, parse_message_safely remain unchanged) ...

def download_and_load_spacy_model():
    global nlp
    if nlp is None:
        logging.info("Cold start: Loading spaCy model...")
        try:
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            logging.info("Model loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load spaCy model: {e}", exc_info=True)
            raise
def get_article_text(url):
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
def extract_entities(text):
    if not text: return []
    logging.info("Extracting entities...")
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    logging.info(f"Found {len(entities)} entities.")
    return entities
def parse_message_safely(message_str):
    logging.info(f"Attempting to parse message: {message_str}")
    url_match = re.search(r'"url"\s*:\s*"(.*?)"', message_str)
    email_match = re.search(r'"email"\s*:\s*"(.*?)"', message_str)
    url = url_match.group(1) if url_match else None
    email = email_match.group(1) if email_match else None
    if url and email:
        logging.info(f"Successfully parsed with regex: url={url}, email={email}")
        return {"url": url, "email": email}
    else:
        logging.error(f"Failed to parse URL and/or email from message: {message_str}")
        return None

@functions_framework.cloud_event
def main(cloud_event):
    logging.info("Function execution started.")
    try:
        download_and_load_spacy_model()

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
            logging.warning(f"Could not retrieve text from {url}. Aborting.")
            return
        
        entities = extract_entities(article_text)
        
        # --- DEBUGGING: Create and Log Email Body ---
        subject = f"Fraud Digest Analysis for: {url}"
        body = f"<h1>Analysis Results</h1><p>Found {len(entities)} entities in the article from {url}.</p>"
        if entities:
            body += "<table border='1' style='border-collapse: collapse; width: 100%;'><tr><th style='padding: 8px; text-align: left;'>Entity</th><th style='padding: 8px; text-align: left;'>Label</th></tr>"
            for entity, label in entities:
                body += f"<tr><td style='padding: 8px;'>{entity}</td><td style='padding: 8px;'>{label}</td></tr>"
            body += "</table>"
        else:
            body += "<p>No entities were found.</p>"
        
        # Instead of sending an email, we log the subject and body
        logging.info(f"--- SIMULATED EMAIL TO {email} ---")
        logging.info(f"SUBJECT: {subject}")
        logging.info(f"BODY: {body}")
        logging.info("--- END OF SIMULATED EMAIL ---")

    except Exception as e:
        logging.error(f"An unexpected error occurred in main handler: {e}", exc_info=True)
    
    logging.info("Function execution finished.")


def main(cloud_event):
    logging.info("Function execution started.")
    try:
        # Initialize services on cold start
        download_and_load_spacy_model()
        initialize_gmail_service()

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
            failure_subject = f"Failed to analyze URL: {url}"
            failure_body = f"<p>Sorry, we could not retrieve the article content from the provided URL.</p><p>URL: {url}</p>"
            send_email(email, failure_subject, failure_body)
            return
        
        entities = extract_entities(article_text)
        
        # --- Create Email Body ---
        subject = f"Fraud Digest Analysis for: {url}"
        body = f"<h1>Analysis Results</h1><p>Found {len(entities)} entities in the article from {url}.</p>"
        if entities:
            body += "<table border='1' style='border-collapse: collapse; width: 100%;'><tr><th style='padding: 8px; text-align: left;'>Entity</th><th style='padding: 8px; text-align: left;'>Label</th></tr>"
            for entity, label in entities:
                body += f"<tr><td style='padding: 8px;'>{entity}</td><td style='padding: 8px;'>{label}</td></tr>"
            body += "</table>"
        else:
            body += "<p>No entities were found.</p>"
        
        send_email(email, subject, body)

    except Exception as e:
        logging.error(f"An unexpected error occurred in main handler: {e}", exc_info=True)
    
    logging.info("Function execution finished.")
    