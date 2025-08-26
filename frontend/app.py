# frontend/app.py (FINAL, CORRECTED VERSION)

import streamlit as st
import json
from google.cloud import pubsub_v1
import os

# --- Configuration ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "fraud-digest-app-v2-469310")
TOPIC_ID = "analysis-requests"

# Initialize a Pub/Sub publisher client.
# Use st.cache_resource to ensure this is created only once per session.
@st.cache_resource
def get_publisher():
    return pubsub_v1.PublisherClient()

publisher = get_publisher()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def publish_analysis_request(url, email):
    """Publishes a message to the Pub/Sub topic."""
    try:
        data = {"url": url, "email": email}
        message_data = json.dumps(data).encode("utf-8")
        
        future = publisher.publish(topic_path, message_data)
        future.result() # Wait for the publish operation to complete.
        
        # Use session state to show a persistent success message
        st.session_state.last_submitted_url = url
        st.session_state.last_submitted_email = email
        return True
    except Exception as e:
        st.error(f"Failed to submit request: {e}")
        return False

def main():
    """Main function to run the Streamlit app."""
    st.title("The Fraud Digest Weekly")
    st.subheader("AI-Powered Named Entity Recognition")

    # Initialize session state variables if they don't exist
    if 'last_submitted_url' not in st.session_state:
        st.session_state.last_submitted_url = None
    if 'last_submitted_email' not in st.session_state:
        st.session_state.last_submitted_email = None

    user_email = "maya.fudim@axionym.com"
    st.info(f"Analysis results will be sent to: **{user_email}**")

    url = st.text_input("Enter article URL:", key="url_input")

    if st.button("Analyze"):
        if url:
            with st.spinner("Submitting request..."):
                # Only publish if the URL is new
                if url != st.session_state.last_submitted_url:
                    publish_analysis_request(url, user_email)
                else:
                    # If the same URL is submitted again, just show the success message
                    st.success(f"Analysis request for {url} has already been submitted! Results will be sent to {user_email}.")
        else:
            st.warning("Please enter a URL.")

    # Show a persistent success message after a successful submission
    if st.session_state.last_submitted_url:
        st.success(f"Analysis request for {st.session_state.last_submitted_url} has been submitted! Results will be sent to {st.session_state.last_submitted_email}.")

if __name__ == "__main__":
    main()
    