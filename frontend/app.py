# app.py
import streamlit as st
from src.scraper import get_article_text
from src.nlp_processor import load_model, extract_entities
from src.ui import display_header, display_entity_dataframe

def main():
    """Main function to run the Streamlit app."""
    display_header()
    
    # Load the NLP model
    nlp = load_model()

    url = st.text_input("Enter article URL:", "")

    if st.button("Analyze"):
        if url:
            article_text = get_article_text(url)
            if article_text:
                entities = extract_entities(article_text, nlp)
                display_entity_dataframe(entities)
        else:
            st.warning("Please enter a URL.")

if __name__ == "__main__":
    main()
  
