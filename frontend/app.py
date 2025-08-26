# frontend/app.py (VERSION WITH LOGGING)

import streamlit as st
import json
from google.cloud import pubsub_v1
import os
import logging

# --- Logging Setup ---
# This will make logs appear in the Cloud Run logs viewer
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration ---
PROJECT_ID = "fraud-digest-app-v2-469310"
TOPIC_ID = "analysis-requests"

@st.cache_resource
def get_publisher():
    logging.info("Initializing Pub/Sub client...")
    return pubsub_v1.PublisherClient()

publisher = get_publisher()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def publish_analysis_request(url, email):
    """Publishes a message to the Pub/Sub topic."""
    try:
        logging.info(f"Attempting to publish message for URL: {url}")
        data = {"url": url, "email": email}
        message_data = json.dumps(data).encode("utf-8")
        
        future = publisher.publish(topic_path, message_data)
        future.result()
        
        logging.info(f"Successfully published message for URL: {url}")
        st.session_state.last_submitted_url = url
        return True
    except Exception as e:
        logging.error(f"Failed to publish message: {e}", exc_info=True)
        st.error(f"Failed to submit request: {e}")
        return False

def main():
    st.title("The Fraud Digest Weekly")
    
    if 'last_submitted_url' not in st.session_state:
        st.session_state.last_submitted_url = None

    user_email = "maya.fudim@axionym.com"
    st.info(f"Results will be sent to: **{user_email}**")

    url = st.text_input("Enter article URL:", key="url_input")

    if st.button("Analyze"):
        logging.info("Analyze button clicked.")
        if url:
            if url != st.session_state.last_submitted_url:
                with st.spinner("Submitting request..."):
                    publish_analysis_request(url, user_email)
            else:
                logging.warning(f"Duplicate submission attempted for URL: {url}")
                st.warning("This URL has already been submitted.")
        else:
            st.warning("Please enter a URL.")

    if st.session_state.last_submitted_url:
        st.success(f"Analysis request for {st.session_state.last_submitted_url} has been submitted!")

if __name__ == "__main__":
    main()
    