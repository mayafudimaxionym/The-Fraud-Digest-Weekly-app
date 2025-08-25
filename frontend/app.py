# frontend/app.py

import streamlit as st
import json
from google.cloud import pubsub_v1
import os

# --- Configuration ---
# In Cloud Run, the project ID is automatically available.
# For local testing, you might need to set this environment variable.
PROJECT_ID = os.environ.get("GCP_PROJECT", "fraud-digest-app-v2-469310")
TOPIC_ID = "analysis-requests"

# Initialize a Pub/Sub publisher client.
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def publish_analysis_request(url, email):
    """Publishes a message to the Pub/Sub topic."""
    try:
        data = {"url": url, "email": email}
        # Data must be a bytestring
        message_data = json.dumps(data).encode("utf-8")
        
        future = publisher.publish(topic_path, message_data)
        # Wait for the publish operation to complete.
        future.result() 
        
        st.success(f"Analysis request for {url} has been submitted! Results will be sent to {email}.")
        return True
    except Exception as e:
        st.error(f"Failed to submit request: {e}")
        return False

def main():
    """Main function to run the Streamlit app."""
    st.title("The Fraud Digest Weekly")
    st.subheader("AI-Powered Named Entity Recognition")

    # For now, we'll use a hardcoded email.
    # In a real app, this would come from the logged-in user.
    user_email = "maya.fudim@axionym.com"
    st.info(f"Analysis results will be sent to: **{user_email}**")

    url = st.text_input("Enter article URL:", "")

    if st.button("Analyze"):
        if url:
            with st.spinner("Submitting request..."):
                publish_analysis_request(url, user_email)
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
    