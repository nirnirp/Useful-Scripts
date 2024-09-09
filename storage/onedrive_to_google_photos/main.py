# Transfer a OneDrive folder into a Google Photos Album then purge it, using the APIs. 
#
# Requirements: 
# pip install requests msal google-auth-oauthlib google-api-python-client

from datetime import datetime, timezone
import requests, os, time, json

from msal import ConfidentialClientApplication
from msal import PublicClientApplication

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# OneDrive Authentication and API details
CLIENT_ID_ONEDRIVE = ""
CLIENT_SECRET_ONEDRIVE = ""
TENANT_ID = ""  # or your specific tenant ID
AUTHORITY_ONEDRIVE = f"https://login.microsoftonline.com/{TENANT_ID}"
AUTHORITY_ONEDRIVE_PERSONAL = 'https://login.microsoftonline.com/common'  # For personal accounts
ONEDRIVE_API_ENDPOINT = "https://graph.microsoft.com/v1.0/me/drive"
ONEDRIVE_USER_PRINCIPAL_NAME = ""
TOKEN_FILE_ONEDRIVE = 'onedrive_token.json'
ONEDRIVE_FOLDER = "Pictures/Xbox Screenshots"
SCOPES_ONEDRIVE = ['Files.ReadWrite.All', 'User.Read.All']

# Google Photos Authentication and API details
CREDENTIALS_JSON = 'google_credentials.json'
TOKEN_JSON_GOOGLE = 'google_token.json'  # The path to the Google OAuth token file
GOOGLE_PHOTOS_ALBUM_NAME = "XBOX-Screenshots"
SCOPES = ['https://www.googleapis.com/auth/photoslibrary'] # Scopes for Google Photos API

def authenticate_onedrive():
    if os.path.exists(TOKEN_FILE_ONEDRIVE):
        with open(TOKEN_FILE_ONEDRIVE, 'r') as token_file:
            token = json.load(token_file)
            # Check if token is still valid
            if is_token_valid(token):
                return token['access_token']

    app = PublicClientApplication(
        client_id=CLIENT_ID_ONEDRIVE,
        authority=AUTHORITY_ONEDRIVE_PERSONAL
    )

    # First, check if there's a refresh token available
    if os.path.exists(TOKEN_FILE_ONEDRIVE):
        with open(TOKEN_FILE_ONEDRIVE, 'r') as token_file:
            token = json.load(token_file)
            if 'refresh_token' in token:
                result = app.acquire_token_by_refresh_token(token['refresh_token'], SCOPES_ONEDRIVE)
                if 'access_token' in result:
                    print("Refreshed access token successfully.")
                    save_token(result)
                    return result['access_token']

    # Otherwise, initiate device code flow
    result = app.initiate_device_flow(scopes=SCOPES_ONEDRIVE)
    if "user_code" not in result:
        raise Exception("Failed to initiate device flow. Error: {}".format(result))

    print("To authenticate, use a web browser to visit {} and enter the code: {}".format(result['verification_uri'], result['user_code']))

     # Polling for token acquisition
    print("Waiting for user authentication...")
    while True:
        token_response = app.acquire_token_by_device_flow(result)
        if "access_token" in token_response:
            print("Authentication successful. Token acquired.")
            save_token(token_response)
            return token_response['access_token']
        elif "error" in token_response and token_response['error'] == 'authorization_pending':
            print("Waiting for user to complete authentication...")  # User has not authenticated yet
            time.sleep(5)  # Poll every 5 seconds
        else:
            raise Exception(f"Failed to authenticate: {token_response}")

def save_token(token_data):
    # Save token data with expiration timestamp
    token_data['expires_at'] = time.time() + int(token_data['expires_in'])
    with open(TOKEN_FILE_ONEDRIVE, 'w') as token_file:
        json.dump(token_data, token_file)
        print(f"Token saved to {TOKEN_FILE_ONEDRIVE}")

def is_token_valid(token):
    # Check if the access token is still valid
    if 'access_token' in token:
        current_timestamp = time.time()  # Get the current time in seconds since the epoch
        if current_timestamp < token['expires_at']:
            print("Access token is still valid.")
            return True
        else:
            print("Access token has expired.")
            return False
    else:
        print("No access token found.")
        return False
    

# List all files from a specific OneDrive folder using the folder path
def list_files_from_onedrive(user_id, folder_path, onedrive_token):
    # Access a specific user's drive by user ID
    endpoint = f"https://graph.microsoft.com/v1.0/users/{user_id}/drive/root:/{folder_path}:/children"
    
    headers = {
        "Authorization": f"Bearer {onedrive_token}"
    }
    
    # Send request to list files
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"Failed to list files from OneDrive: {response.status_code} - {response.text}")
    
    # Return the JSON response containing file list
    return response.json()

def get_user_id_in_tenant(onedrive_token, user_name):
    # Microsoft Graph API endpoint to list users
    endpoint = "https://graph.microsoft.com/v1.0/users"
    
    headers = {
        "Authorization": f"Bearer {onedrive_token}"
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        users = response.json().get('value', [])
        
        # Print detailed info about all users
        print("Listing all users with detailed information:")
        for user in users:
            print(f"User ID: {user['id']}")
            print(f"User Principal Name: {user['userPrincipalName']}")
            print(f"Display Name: {user.get('displayName', 'N/A')}")
            print(f"Email: {user.get('mail', 'N/A')}")
            print(f"Job Title: {user.get('jobTitle', 'N/A')}")
            print(f"Mobile Phone: {user.get('mobilePhone', 'N/A')}")
            print("-" * 50)
        
        # Iterate over users and find the one that matches the user_name
        for user in users:
            if user['userPrincipalName'].lower() == user_name.lower():
                print(f"\nMatching user found: {user['userPrincipalName']}, User ID: {user['id']}")
                return user['id']
        
        # If no match is found, raise an exception
        raise Exception(f"\nUser with the name {user_name} not found.")
    
    else:
        raise Exception(f"Failed to list users: {response.status_code} - {response.text}")


# Upload a PNG file to Google Photos
def upload_to_google_photos(file_path, album_id, creds):
    photos_service = googleapiclient.discovery.build('photoslibrary', 'v1', credentials=creds, discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1')

    # Upload the media
    with open(file_path, 'rb') as file_data:
        upload_token = photos_service.mediaItems().upload(
            media_body=file_data,
            media_mime_type='image/png'
        ).execute()['uploadToken']
    
    # Create media item in album
    new_media_item = {
        'newMediaItems': [{
            'description': 'Uploaded by script',
            'simpleMediaItem': {
                'uploadToken': upload_token
            }
        }]
    }
    if album_id:
        new_media_item['albumId'] = album_id
    
    # Add to Google Photos
    photos_service.mediaItems().batchCreate(body=new_media_item).execute()

# Find album by name in Google Photos
def find_google_photos_album_by_name(album_name, creds):
    # Corrected build call with discoveryServiceUrl
    photos_service = build('photoslibrary', 'v1', credentials=creds, discoveryServiceUrl='https://photoslibrary.googleapis.com/$discovery/rest?version=v1')

    # Get the albums from Google Photos
    albums_result = photos_service.albums().list(pageSize=50).execute()
    albums = albums_result.get('albums', [])
    
    for album in albums:
        if album['title'] == album_name:
            print(f"gPhotos album {album['title']} found. ID = {album['id']}")
            return album['id']
    
    return None

# Purge all files in the OneDrive folder
def delete_files_from_onedrive(folder_path, files, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    
    for file in files:
        file_id = file['id']
        delete_url = f"{ONEDRIVE_API_ENDPOINT}/items/{file_id}"
        response = requests.delete(delete_url, headers=headers)
        if response.status_code == 204:
            print(f"Deleted {file['name']} from OneDrive")
        else:
            print(f"Failed to delete {file['name']}: {response.status_code} - {response.text}")


def authenticate_google_photos():
    print("Authenticating to Google Photos...")

    # Define the required scopes
    SCOPES = [
        'https://www.googleapis.com/auth/photoslibrary.readonly',
        'https://www.googleapis.com/auth/photoslibrary.appendonly',
    ]
    creds = None

    # Load token.json if it exists to load previously stored credentials
    if os.path.exists(TOKEN_JSON_GOOGLE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_JSON_GOOGLE, SCOPES)
            print(f"Loaded credentials from {TOKEN_JSON_GOOGLE}.")
        except Exception as e:
            print(f"Error loading credentials from {TOKEN_JSON_GOOGLE}: {e}")

    # If there are no valid credentials, or they are expired without a refresh token, do the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                print("Refreshing expired credentials...")
                creds.refresh(Request())
                print("Token refreshed successfully.")
            except Exception as e:
                print(f"Error refreshing the token: {e}")
                creds = None  # Ensure OAuth flow starts if refresh fails
        else:
            try:
                print("No valid credentials found. Starting OAuth flow...")
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_JSON, SCOPES)
                creds = flow.run_local_server(port=8080)
                print("OAuth flow completed successfully.")
            except Exception as e:
                raise Exception(f"OAuth flow failed: {e}")

        # Save the credentials to token.json for future use
        with open(TOKEN_JSON_GOOGLE, 'w') as token:
            token.write(creds.to_json())
            print(f"Credentials saved to {TOKEN_JSON_GOOGLE}.")

    if not creds or not creds.valid:
        raise Exception("Failed to authenticate to Google Photos.")

    return creds

# Main function to upload PNG files from OneDrive to Google Photos and purge the OneDrive folder
def main():
    # Step 1: Authenticate OneDrive
    onedrive_token = authenticate_onedrive()
    user_id = get_user_id_in_tenant(onedrive_token, ONEDRIVE_USER_PRINCIPAL_NAME)
    
    # Step 2: Authenticate Google Photos
    google_creds = authenticate_google_photos()
    
    # Step 3: Find the specified Google Photos album by name
    album_id = find_google_photos_album_by_name(GOOGLE_PHOTOS_ALBUM_NAME, google_creds)
    if not album_id:
        raise Exception(f"Google Photos album '{GOOGLE_PHOTOS_ALBUM_NAME}' not found.")
    
    # Step 4: List all files from the OneDrive folder
    folder_path = ONEDRIVE_FOLDER
    files = list_files_from_onedrive(user_id, folder_path, onedrive_token)
    
    # Step 5: Filter PNG files and upload them to Google Photos
    for file in files:
        if file['name'].lower().endswith('.png'):
            file_download_url = file['@microsoft.graph.downloadUrl']
            file_path = file['name']
            
            # Download file temporarily
            response = requests.get(file_download_url)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            
            # Upload file to Google Photos
            upload_to_google_photos(file_path, album_id, google_creds)
            
            # Remove the temporary file after upload
            os.remove(file_path)
    
    # Step 6: Purge all files from the OneDrive folder
    delete_files_from_onedrive(folder_path, files, onedrive_token)
    print(f"All files from {folder_path} have been deleted from OneDrive.")

if __name__ == "__main__":
    main()
