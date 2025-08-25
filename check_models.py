# check_models.py (Corrected)
from google.cloud import aiplatform
import google.generativeai as genai
import os

PROJECT_ID = "fraud-digest-app-v2-469310"
REGION = "us-central1"

def list_gemini_models():
    """Lists available Gemini models in the specified project and region."""
    try:
        aiplatform.init(project=PROJECT_ID, location=REGION)
        
        print(f"--- Available Generative Models in {REGION} ---")
        
        # This is the correct way to list models
        models = aiplatform.Model.list()
        
        gemini_models_found = False
        for model in models:
            # We filter for models that have "gemini" in their name
            if "gemini" in model.name:
                print(f"Model Name: {model.name}")
                print(f"  Display Name: {model.display_name}")
                print(f"  Version: {model.version_id}")
                print("-" * 20)
                gemini_models_found = True
        
        if not gemini_models_found:
            print("No Gemini models found in this region.")

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")

        # Configure with the simplest possible settings
        genai.configure(api_key=api_key)

        print("\n--- Models available for 'generateContent' ---")
        found_models = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
                found_models = True
        
        if not found_models:
            print("No models supporting 'generateContent' found with default settings.")



    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    list_gemini_models()
