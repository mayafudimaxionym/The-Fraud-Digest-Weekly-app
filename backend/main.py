# backend/main.py

import base64
import json
import logging
import sys
import requests
from bs4 import BeautifulSoup
import spacy

import functions_framework

# --- Logging Setup ---
# This will ensure that logs are formatted correctly for Cloud Logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variables ---
nlp = None

def download_and_load_spacy_model():
    """Loads the spaCy model into memory if it's not already loaded."""
    global nlp
    if nlp is None:
        logging.info("Cold start: Loading spaCy model...")
        try:
            # In Cloud Functions, /tmp is the only writable directory
            spacy.cli.download("en_core_web_sm")
            nlp = spacy.load("en_core_web_sm")
            logging.info("Model loaded successfully.")
        except Exception as e:
            logging.error(f"Failed to load spaCy model: {e}", exc_info=True)
            raise  # Re-raise the exception to fail the function invocation

def get_article_text(url):
    """Fetches and extracts text content from a given URL."""
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
    """Extracts named entities from text."""
    if not text:
        return []
    logging.info("Extracting entities...")
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    logging.info(f"Found {len(entities)} entities.")
    return entities

@functions_framework.cloud_event
def main(cloud_event):
    """
    This function is triggered by a message published to a Pub/Sub topic.
    """
    logging.info("Function execution started.")
    
    try:
        # Ensure the spaCy model is loaded before use. This handles cold starts.
        download_and_load_spacy_model()

        message_data_encoded = cloud_event.data.get("message", {}).get("data")
        if not message_data_encoded:
            logging.error("No data in Pub/Sub message.")
            return

        message_data = base64.b64decode(message_data_encoded).decode("utf-8")
        logging.info(f"Received message: {message_data}")

        data = json.loads(message_data)
        url = data.get("url")
        email = data.get("email")

        if not url or not email:
            logging.error(f"'url' or 'email' not found in message: {data}")
            return

        logging.info(f"Processing request for user: {email}")
        
        article_text = get_article_text(url)
        if not article_text:
            # TODO: Send a failure email to the user.
            logging.warning(f"Could not retrieve text from {url}. Aborting.")
            return
        
        entities = extract_entities(article_text)
        
        # For now, just log the entities.
        logging.info(f"Extracted entities: {entities}")

        # TODO: Implement email sending logic here using Gmail API.
        logging.info(f"TODO: Send results to {email}")

    except json.JSONDecodeError:
        logging.error(f"Invalid JSON in message: {message_data}", exc_info=True)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
    
    logging.info("Function execution finished.")
    