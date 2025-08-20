# backend/main.py

import base64
import logging
import sys
import re
import requests
from bs4 import BeautifulSoup
import spacy

import functions_framework

# --- Logging Setup ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

# --- Global variables ---
nlp = None

def download_and_load_spacy_model():
    # ... (остальной код этой функции не меняется)
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
    # ... (остальной код этой функции не меняется)
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
    # ... (остальной код этой функции не меняется)
    if not text:
        return []
    logging.info("Extracting entities...")
    doc = nlp(text)
    entities = [(ent.text, ent.label_) for ent in doc.ents]
    logging.info(f"Found {len(entities)} entities.")
    return entities

def parse_message_safely(message_str):
    """
    A robust parser that handles malformed JSON-like strings.
    It uses regular expressions to find the URL and email.
    """
    logging.info(f"Attempting to parse message: {message_str}")
    
    # Regex to find url and email
    url_match = re.search(r"url:\s*['\"]?(.*?)['\"]?[\s,}]", message_str)
    email_match = re.search(r"email:\s*['\"]?(.*?)['\"]?[\s,}]", message_str)
    
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
        
        # Use the new, safe parser instead of json.loads()
        data = parse_message_safely(message_data)
        if not data:
            return

        url = data.get("url")
        email = data.get("email")

        logging.info(f"Processing request for user: {email}")
        
        article_text = get_article_text(url)
        if not article_text:
            logging.warning(f"Could not retrieve text from {url}. Aborting.")
            return
        
        entities = extract_entities(article_text)
        
        logging.info(f"Extracted entities: {entities}")

        logging.info(f"TODO: Send results to {email}")

    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}", exc_info=True)
    
    logging.info("Function execution finished.")
    