# get_refresh_token.py
from google_auth_oauthlib.flow import InstalledAppFlow

# Define the scopes: we only need permission to send emails.
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# Path to the client secret file you downloaded.
# IMPORTANT: Make sure this path is correct.
CLIENT_SECRET_FILE = 'gmail-api-credentials.json'

def main():
    """Runs the authentication flow and prints the refresh token."""
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
    
    # This will open a browser window for you to log in and give consent.
    creds = flow.run_local_server(port=0)
    
    # Print the refresh token. This is the value we need to save.
    print("\n--- Your Refresh Token (save this!) ---")
    print(creds.refresh_token)
    print("---------------------------------------\n")

if __name__ == '__main__':
    main()
