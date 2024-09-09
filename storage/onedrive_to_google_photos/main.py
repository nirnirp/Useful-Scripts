# pip install requests msal google-auth-oauthlib google-api-python-client

from datetime import datetime, timedelta
import requests, os, time, os

from msal import ConfidentialClientApplication
from msal import PublicClientApplication, SerializableTokenCache

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# OneDrive Authentication and API details
CLIENT_ID_ONEDRIVE = ""
# CLIENT_SECRET_ONEDRIVE = ""
# TENANT_ID = ""  # or your specific tenant ID
# AUTHORITY_ONEDRIVE_ENTERPRISE = f"https://login.microsoftonline.com/{TENANT_ID}"
AUTHORITY_ONEDRIVE = 'https://login.microsoftonline.com/consumers'
# AUTHORITY_ONEDRIVE = 'https://login.microsoftonline.com/common'  # For personal accounts
ONEDRIVE_API_ENDPOINT = "https://graph.microsoft.com/v1.0/me"
# ONEDRIVE_USER_PRINCIPAL_NAME = ""
TOKEN_FILE_ONEDRIVE = 'onedrive_token.json'
ONEDRIVE_FOLDER = ""
# SCOPES_ONEDRIVE = ['Files.ReadWrite.All', 'User.Read.All']
SCOPES_ONEDRIVE = ['Files.Read', 'Files.ReadWrite']
# REDIRECT_URI = 'https://login.microsoftonline.com/common/oauth2/nativeclient'


# Google Photos Authentication and API details
CREDENTIALS_FILE_GOOGLE = 'google_credentials.json'
TOKEN_PICKLE_GOOGLE = 'google_token.json'  # The path to the Google OAuth token file
ALBUM_TITLE = ''  # Consistent album name
# GOOGLE_PHOTOS_ALBUM_NAME = ""
# SCOPES_GOOGLE = ['https://www.googleapis.com/auth/photoslibrary'] # Scopes for Google Photos API
SCOPES_GOOGLE = [
    'https://www.googleapis.com/auth/photoslibrary.sharing',
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'https://www.googleapis.com/auth/photoslibrary.readonly',
    'https://www.googleapis.com/auth/photoslibrary'
]

# Utils
TRANSFERS_FOLDER = 'transfers'



def load_cache():
    cache = SerializableTokenCache()
    if os.path.exists(TOKEN_FILE_ONEDRIVE):
        with open(TOKEN_FILE_ONEDRIVE, 'r') as token_file:
            cache.deserialize(token_file.read())
    return cache

def save_cache(cache):
    if cache.has_state_changed:
        with open(TOKEN_FILE_ONEDRIVE, 'w') as token_file:
            token_file.write(cache.serialize())

def authenticate_onedrive():
    cache = load_cache()
    
    app = PublicClientApplication(
        client_id=CLIENT_ID_ONEDRIVE,
        authority=AUTHORITY_ONEDRIVE,
        token_cache=cache
    )

    accounts = app.get_accounts()
    if accounts:
        print("Found existing OneDrive account, attempting to use it...")
        result = app.acquire_token_silent(SCOPES_ONEDRIVE, account=accounts[0])
        if result:
            print("Token acquired silently.")
            save_cache(cache)
            return result['access_token']
        else:
            print("Silent token acquisition failed, falling back to device flow.")

    # If silent token acquisition fails, use device flow
    flow = app.initiate_device_flow(scopes=SCOPES_ONEDRIVE)
    if "user_code" not in flow:
        raise Exception("Failed to create device flow")

    print(f"To authenticate, please follow these steps:")
    print(f"1. Open this URL in your web browser: {flow['verification_uri']}")
    print(f"2. Enter this code when prompted: {flow['user_code']}")

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        print("Authentication successful.")
        save_cache(cache)
        return result['access_token']
    else:
        raise Exception(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
    

def list_files_from_onedrive(folder_path, onedrive_token):
    # Use the /me/drive endpoint for personal OneDrive accounts
    endpoint = f"{ONEDRIVE_API_ENDPOINT}/drive/root:/{folder_path}:/children"
    headers = {
        "Authorization": f"Bearer {onedrive_token}",
        "Accept": "application/json"
    }
    
    response = requests.get(endpoint, headers=headers)
    
    if response.status_code == 200:
        return response.json().get('value', [])
    elif response.status_code == 404:
        print(f"Folder '{folder_path}' not found. Please check the path.")
        return []
    else:
        print(f"Failed to list files. Status code: {response.status_code}")
        print(f"Response: {response.text}")
        raise Exception(f"Failed to list files: {response.status_code} - {response.text}")


def authenticate_google_photos():
    print("Authenticating to Google Photos...")

    creds = None

    # Load token.json if it exists to load previously stored credentials
    if os.path.exists(TOKEN_PICKLE_GOOGLE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PICKLE_GOOGLE, SCOPES_GOOGLE)
            print(f"Loaded credentials from {TOKEN_PICKLE_GOOGLE}.")
        except Exception as e:
            print(f"Error loading credentials from {TOKEN_PICKLE_GOOGLE}: {e}")

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
                flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE_GOOGLE, SCOPES_GOOGLE)
                creds = flow.run_local_server(port=8080)
                print("OAuth flow completed successfully.")
            except Exception as e:
                raise Exception(f"OAuth flow failed: {e}")

        # Save the credentials to token.json for future use
        with open(TOKEN_PICKLE_GOOGLE, 'w') as token:
            token.write(creds.to_json())
            print(f"Credentials saved to {TOKEN_PICKLE_GOOGLE}.")

    if not creds or not creds.valid:
        raise Exception("Failed to authenticate to Google Photos.")

    return creds

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


def find_or_create_album(service, album_title):
    try:
        # First, try to find an existing album
        response = service.albums().list(pageSize=50).execute()
        albums = response.get('albums', [])
        for album in albums:
            if album['title'] == album_title:
                if album.get('isWriteable', False):
                    print(f"Found existing writable album: {album_title}")
                    return album['id']
                else:
                    print(f"Found existing album {album_title}, but it's not writable.")
                    break  # Exit the loop to create a new album

        # If no suitable album found, create a new one
        create_album_body = {'album': {'title': album_title}}
        create_album_response = service.albums().create(body=create_album_body).execute()
        album_id = create_album_response.get('id')

        # Share the album
        share_album_body = {
            'sharedAlbumOptions': {
                'isCollaborative': 'true',
                'isCommentable': 'true'
            }
        }
        service.albums().share(albumId=album_id, body=share_album_body).execute()
        
        print(f"Created and shared new album: {album_title}")
        return album_id
    except Exception as e:
        print(f"Error finding or creating album: {str(e)}")
        return None



def upload_to_google_photos(file_path, album_id, creds):
    try:
        service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
        
        if not album_id:
            album_id = find_or_create_album(service, ALBUM_TITLE)
        
        # Step 1: Upload the image bytes
        with open(file_path, 'rb') as image_file:
            image_data = image_file.read()
        
        upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'
        headers = {
            'Authorization': f'Bearer {creds.token}',
            'Content-Type': 'application/octet-stream',
            'X-Goog-Upload-Protocol': 'raw',
        }
        
        upload_response = requests.post(upload_url, data=image_data, headers=headers)
        
        if upload_response.status_code != 200:
            raise Exception(f"Failed to upload image data: {upload_response.text}")
        
        upload_token = upload_response.content.decode('utf-8')
        
        # Step 2: Create the media item using the upload token
        request_body = {
            'newMediaItems': [{
                'description': 'Uploaded by script',
                'simpleMediaItem': {
                    'uploadToken': upload_token
                }
            }],
            'albumId': album_id
        }
        
        create_response = service.mediaItems().batchCreate(body=request_body).execute()
        
        if 'newMediaItemResults' in create_response:
            item = create_response['newMediaItemResults'][0]
            if 'mediaItem' in item:
                print(f"Successfully uploaded {os.path.basename(file_path)} to Google Photos album")
                return True
            else:
                print(f"Failed to create media item for {os.path.basename(file_path)}: {item.get('status', {}).get('message', 'Unknown error')}")
                return False
        else:
            print(f"Unexpected response when creating media item for {os.path.basename(file_path)}")
            return False
        
    except Exception as e:
        print(f"Error uploading {os.path.basename(file_path)} to Google Photos: {str(e)}")
        return False
    

def delete_file_from_onedrive(file, access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    delete_url = f"{ONEDRIVE_API_ENDPOINT}/drive/items/{file['id']}"
    print(f"[SIMULATION!] Successfully deleted {file['name']} from OneDrive")
    # response = requests.delete(delete_url, headers=headers)
    # if response.status_code == 204:
    #     print(f"Successfully deleted {file['name']} from OneDrive")
    # else:
    #     print(f"Failed to delete {file['name']} from OneDrive: {response.status_code} - {response.text}")

def transfer_files(files, album_id, google_creds, onedrive_token):

    if not os.path.exists(TRANSFERS_FOLDER):
        os.makedirs(TRANSFERS_FOLDER)

    for file in files:
        if file['name'].lower().endswith('.png'):
            file_download_url = file['@microsoft.graph.downloadUrl']
            file_name = file['name']
            file_path = os.path.join(TRANSFERS_FOLDER, file_name)
            
            try:
                # Download the file
                response = requests.get(file_download_url)
                response.raise_for_status()
                
                with open(file_path, 'wb') as f:
                    f.write(response.content)
                
                # Upload to Google Photos
                upload_success = upload_to_google_photos(file_path, album_id, google_creds)
                
                if upload_success:
                    # Delete file from OneDrive after successful transfer
                    delete_file_from_onedrive(file, onedrive_token)
                else:
                    print(f"Skipping OneDrive deletion for {file_name} due to upload failure")
            
            except requests.RequestException as e:
                print(f"Error downloading {file_name}: {str(e)}")
            except Exception as e:
                print(f"Error processing {file_name}: {str(e)}")
            
            finally:
                # Clean up: remove the local file
                if os.path.exists(file_path):
                    os.remove(file_path)

    # Delete all .xjr files from OneDrive
    for file in files:
        if file['name'].lower().endswith('.xjr.png'):
            delete_file_from_onedrive(file, onedrive_token)


def sync_photos():
    print(f"Starting photo sync at {datetime.now()}")
    
    try:
        onedrive_token = authenticate_onedrive()
        google_creds = authenticate_google_photos()
        
        # album_id = find_google_photos_album_by_name(GOOGLE_PHOTOS_ALBUM_NAME, google_creds)

        # Find or create the album
        service = build('photoslibrary', 'v1', credentials=google_creds, static_discovery=False)
        album_id = find_or_create_album(service, ALBUM_TITLE)

        if not album_id:
            raise Exception(f"Google Photos album '{ALBUM_TITLE}' not found.")
        
        files = list_files_from_onedrive(ONEDRIVE_FOLDER, onedrive_token)
        
        transfer_files(files, album_id, google_creds, onedrive_token)
        
        print(f"Sync completed at {datetime.now()}")
    
    except Exception as e:
        print(f"Error during sync: {str(e)}")

def main():
    # Schedule the sync to run daily at a specific time (e.g., 2:00 AM)
    # schedule.every().day.at("02:00").do(sync_photos)
    sync_photos()

    print("Automated photo sync scheduled. Press Ctrl+C to exit.")
    
    # while True:
    #     schedule.run_pending()
    #     time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()
