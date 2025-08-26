# frontend/app.py (FINAL, CORRECTED VERSION)
import streamlit as st
import json
from google.cloud import pubsub_v1
import os

PROJECT_ID = "fraud-digest-app-v2-469310"
TOPIC_ID = "analysis-requests"

@st.cache_resource
def get_publisher():
    return pubsub_v1.PublisherClient()

publisher = get_publisher()
topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)

def main():
    st.title("The Fraud Digest Weekly")
    user_email = "maya.fudim@axionym.com"
    st.info(f"Results will be sent to: **{user_email}**")

    url = st.text_input("Enter article URL:")

    if st.button("Analyze"):
        if url:
            try:
                data = {"url": url, "email": user_email}
                message_data = json.dumps(data).encode("utf-8")
                future = publisher.publish(topic_path, message_data)
                future.result()
                st.success("Request submitted successfully!")
            except Exception as e:
                st.error(f"Failed to submit request: {e}")
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
    