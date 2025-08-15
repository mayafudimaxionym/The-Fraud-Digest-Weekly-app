# src/ui.py
import streamlit as st
import pandas as pd

def display_header():
    """Displays the main header and subheader of the app."""
    st.title("The Fraud Digest Weekly")
    st.subheader("AI-Powered Named Entity Recognition")

def display_entity_dataframe(entities):
    """Displays the extracted entities in a DataFrame."""
    if entities:
        df = pd.DataFrame(entities, columns=("Entity", "Label"))
        st.dataframe(df)
    else:
        st.info("No entities found or text could not be processed.")
  
