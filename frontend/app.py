# frontend/app.py

import streamlit as st
from google.cloud import pubsub_v1
import json
import logging
import os
import sys
import traceback # Import traceback for detailed error logging

# --- Project Configuration ---
PROJECT_ID = None
try:
    # This will work in Cloud Run
    import requests
    response = requests.get("http://metadata.google.internal/computeMetadata/v1/project/project-id", headers={"Metadata-Flavor": "Google"}, timeout=2)
    if response.status_code == 200:
        PROJECT_ID = response.text
except (ImportError, requests.exceptions.RequestException):
    # This will work locally if the env var is set
    logging.warning("Could not contact metadata server, falling back to env var.")
    PROJECT_ID = os.environ.get("GCP_PROJECT_ID")

if not PROJECT_ID:
    st.error("GCP_PROJECT_ID could not be determined. The application cannot function.")
    st.stop()

TOPIC_ID = "fraud-digest-jobs"

# --- Logging Setup ---
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - WEB: %(message)s')

# --- State Management ---
if 'submitted_urls' not in st.session_state:
    st.session_state.submitted_urls = set()

# --- Pub/Sub Publisher ---
publisher = None
def get_publisher():
    """Initializes and returns a Pub/Sub publisher client."""
    global publisher
    if publisher is None:
        logging.info("Initializing Pub/Sub client...")
        publisher = pubsub_v1.PublisherClient()
    return publisher

def publish_message(url, email):
    """Publishes a message to the Pub/Sub topic."""
    logging.info(f"Attempting to publish message for URL: {url}")
    try:
        publisher_client = get_publisher()
        topic_path = publisher_client.topic_path(PROJECT_ID, TOPIC_ID)
        
        message_data = {
            "url": url,
            "email": email
        }
        message_bytes = json.dumps(message_data).encode("utf-8")

        # Publish the message and wait for the result.
        # .result() will raise an exception if publishing fails.
        future = publisher_client.publish(topic_path, data=message_bytes)
        future.result() 

        logging.info(f"Successfully published message for URL: {url}")
        st.session_state.submitted_urls.add(url)
        st.success(f"Analysis request for {url} has been submitted!")

    except Exception as e:
        # Log the full error with traceback for detailed debugging.
        logging.error(f"Failed to publish message for URL {url}: {e}")
        logging.error(traceback.format_exc())
        st.error("Failed to submit the analysis request. An administrator has been notified.")

# --- Streamlit UI ---
st.set_page_config(layout="centered")
st.title("The Fraud Digest Weekly")

# This should be replaced with actual user authentication in a real app
user_email = "maya.fudim@axionym.com" 
st.info(f"Results will be sent to: **{user_email}**")

url_input = st.text_input("Enter article URL:", "https://www.bbc.com/news")

if st.button("Analyze"):
    if url_input:
        logging.info("Analyze button clicked.")
        if url_input in st.session_state.submitted_urls:
            logging.warning(f"Duplicate submission attempted for URL: {url_input}")
            st.warning("This URL has already been submitted for analysis.")
        else:
            publish_message(url_input, user_email)
    else:
        st.error("Please enter a URL.")
        