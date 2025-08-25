# check_models.py (Corrected)
from google.cloud import aiplatform

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

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    list_gemini_models()
