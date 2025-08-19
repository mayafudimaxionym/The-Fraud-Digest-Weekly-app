 # src/nlp_processor.py
import spacy
import streamlit as st

# Load the model once and cache it
@st.cache_resource(show_spinner="Loading NLP model...")
def load_model():
    """Loads the spaCy model."""
    return spacy.load("en_core_web_sm")

def extract_entities(text, nlp_model):
    """Extracts named entities from text using the spaCy model."""
    if not text:
        return []
    doc = nlp_model(text)
    return [(ent.text, ent.label_) for ent in doc.ents]
 
