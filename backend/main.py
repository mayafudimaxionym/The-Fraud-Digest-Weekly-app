 import base64
 import json
 import requests
 from bs4 import BeautifulSoup
 import spacy
 
 import functions_framework
 
 # Global variables to hold loaded models, etc.
 # This helps to avoid reloading on every function invocation.
 nlp = None
 
 def download_and_load_spacy_model():
     """Loads the spaCy model into memory."""
     global nlp
     if nlp is None:
         print("Loading spaCy model...")
         # In Cloud Functions, we need a writable directory, /tmp is available
         spacy.cli.download("en_core_web_sm")
         nlp = spacy.load("en_core_web_sm")
         print("Model loaded successfully.")
 
 def get_article_text(url):
     """Fetches and extracts text content from a given URL."""
     try:
         response = requests.get(url, timeout=15)
         response.raise_for_status()
         soup = BeautifulSoup(response.content, 'html.parser')
         paragraphs = soup.find_all('p')
         article_text = ' '.join([p.get_text() for p in paragraphs])
         return article_text
     except requests.exceptions.RequestException as e:
         print(f"Error fetching URL {url}: {e}")
         return None
 
 def extract_entities(text):
     """Extracts named entities from text."""
     if not text:
         return []
     doc = nlp(text)
     return [(ent.text, ent.label_) for ent in doc.ents]
 
 # This decorator registers the function to be triggered by Pub/Sub messages.
 @functions_framework.cloud_event
 def main(cloud_event):
     """
     This function is triggered by a message published to a Pub/Sub topic.
     """
     # The message payload is base64-encoded.
     message_data = base64.b64decode(cloud_event.data["message"]["data"]).decode("utf-8")
     print(f"Received message: {message_data}")
 
     try:
         data = json.loads(message_data)
         url = data.get("url")
         email = data.get("email")
 
         if not url or not email:
             print("Error: 'url' or 'email' not found in message.")
             return
 
         # Ensure the spaCy model is loaded before use.
         download_and_load_spacy_model()
 
         print(f"Processing URL: {url} for user: {email}")
         
         article_text = get_article_text(url)
         if not article_text:
             print(f"Could not retrieve text from {url}")
             # TODO: Send a failure email to the user.
             return
         
         entities = extract_entities(article_text)
         
         print(f"Found {len(entities)} entities.")
         print(entities)
 
         # TODO: Implement email sending logic here using Gmail API.
         print(f"TODO: Send results to {email}")
 
     except json.JSONDecodeError:
         print(f"Error: Invalid JSON in message: {message_data}")
     except Exception as e:
         print(f"An unexpected error occurred: {e}")
