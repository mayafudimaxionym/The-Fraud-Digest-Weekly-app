import requests
from bs4 import BeautifulSoup
import streamlit as st

@st.cache_data(show_spinner="Fetching article text...")
def get_article_text(url):
    """Fetches and extracts text content from a given URL."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for bad status codes
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all paragraph tags and join their text
        paragraphs = soup.find_all('p')
        article_text = ' '.join([p.get_text() for p in paragraphs])
        return article_text
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching URL: {e}")
        return None
    