# pip install requests msal google-auth-oauthlib google-api-python-client Pillow 

import asyncio, aiohttp, aiofiles
from datetime import datetime, timedelta
import requests, os, time, os, io

from msal import ConfidentialClientApplication
from msal import PublicClientApplication, SerializableTokenCache
from PIL import Image
import boto3

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import logging
import os
from datetime import datetime
import pytz
from PIL.ExifTags import TAGS
import piexif
from PIL.PngImagePlugin import PngInfo
import re

# Set up logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
# Create a logger for our script
logger = logging.getLogger(__name__)

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
ONEDRIVE_FOLDER = "Pictures/Xbox Screenshots"
# SCOPES_ONEDRIVE = ['Files.ReadWrite.All', 'User.Read.All']
SCOPES_ONEDRIVE = ['Files.Read', 'Files.ReadWrite']
# REDIRECT_URI = 'https://login.microsoftonline.com/common/oauth2/nativeclient'


# Google Photos Authentication and API details
CREDENTIALS_FILE_GOOGLE = 'google_credentials.json'
TOKEN_PICKLE_GOOGLE = 'google_token.json'  # The path to the Google OAuth token file
ALBUM_TITLE = ""  # Consistent album name
# SCOPES_GOOGLE = ['https://www.googleapis.com/auth/photoslibrary'] # Scopes for Google Photos API
SCOPES_GOOGLE = [
    'https://www.googleapis.com/auth/photoslibrary.sharing',
    'https://www.googleapis.com/auth/photoslibrary.appendonly',
    'https://www.googleapis.com/auth/photoslibrary.readonly',
    'https://www.googleapis.com/auth/photoslibrary'
]

# Utils
TRANSFERS_FOLDER = 'transfers'
MAX_BATCH_SIZE = 20
UPLOAD_DELAY = 1  # Delay in seconds between batch uploads
MAX_DIMENSION = 16 * 1024 * 1024  # 16MP
JPEG_QUALITY = 85

def get_parameter(param_name):
    ssm = boto3.client('ssm')
    response = ssm.get_parameter(Name=param_name, WithDecryption=True)
    return response['Parameter']['Value']

async def load_cache():
    logger.info("Loading OneDrive token cache")
    cache = SerializableTokenCache()
    if os.path.exists(TOKEN_FILE_ONEDRIVE):
        async with aiofiles.open(TOKEN_FILE_ONEDRIVE, 'r') as token_file:
            cache.deserialize(await token_file.read())
    return cache

async def save_cache(cache):
    logger.info("Saving OneDrive token cache")
    if cache.has_state_changed:
        async with aiofiles.open(TOKEN_FILE_ONEDRIVE, 'w') as token_file:
            await token_file.write(cache.serialize())

async def authenticate_onedrive():
    logger.info("Starting OneDrive authentication")
    cache = await load_cache()
    
    app = PublicClientApplication(
        client_id=CLIENT_ID_ONEDRIVE,
        authority=AUTHORITY_ONEDRIVE,
        token_cache=cache
    )

    accounts = app.get_accounts()
    if accounts:
        logger.info("Found existing OneDrive account, attempting to use it")
        result = app.acquire_token_silent(SCOPES_ONEDRIVE, account=accounts[0])
        if result:
            logger.info("Token acquired silently")
            await save_cache(cache)
            return result['access_token']
        else:
            logger.info("Silent token acquisition failed, falling back to device flow")

    flow = app.initiate_device_flow(scopes=SCOPES_ONEDRIVE)
    if "user_code" not in flow:
        logger.error("Failed to create device flow")
        raise Exception("Failed to create device flow")

    print(f"To authenticate, please follow these steps:")
    print(f"1. Open this URL in your web browser: {flow['verification_uri']}")
    print(f"2. Enter this code when prompted: {flow['user_code']}")

    result = await asyncio.to_thread(app.acquire_token_by_device_flow, flow)

    if "access_token" in result:
        logger.info("Authentication successful")
        await save_cache(cache)
        return result['access_token']
    else:
        logger.error(f"Authentication failed: {result.get('error_description', 'Unknown error')}")
        raise Exception(f"Authentication failed: {result.get('error_description', 'Unknown error')}")

async def list_files_from_onedrive(folder_path, onedrive_token):
    logger.info(f"Listing files from OneDrive folder: {folder_path}")
    endpoint = f"{ONEDRIVE_API_ENDPOINT}/drive/root:/{folder_path}:/children"
    headers = {
        "Authorization": f"Bearer {onedrive_token}",
        "Accept": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.get(endpoint, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                files = data.get('value', [])
                logger.info(f"Found {len(files)} files in OneDrive folder")
                return files
            elif response.status == 404:
                logger.warning(f"Folder '{folder_path}' not found. Please check the path.")
                return []
            else:
                text = await response.text()
                logger.error(f"Failed to list files. Status code: {response.status}")
                logger.error(f"Response: {text}")
                raise Exception(f"Failed to list files: {response.status} - {text}")

async def authenticate_google_photos():
    logger.info("Starting Google Photos authentication")
    creds = None

    if os.path.exists(TOKEN_PICKLE_GOOGLE):
        logger.info(f"Loading credentials from {TOKEN_PICKLE_GOOGLE}")
        creds = Credentials.from_authorized_user_file(TOKEN_PICKLE_GOOGLE, SCOPES_GOOGLE)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired credentials")
            await asyncio.to_thread(creds.refresh, Request())
        else:
            logger.info("Starting new OAuth flow")
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE_GOOGLE, SCOPES_GOOGLE)
            creds = await asyncio.to_thread(flow.run_local_server, port=0)
        
        logger.info(f"Saving credentials to {TOKEN_PICKLE_GOOGLE}")
        async with aiofiles.open(TOKEN_PICKLE_GOOGLE, 'w') as token:
            await token.write(creds.to_json())

    return creds

async def find_or_create_album(service, album_title):
    logger.info(f"Finding or creating album: {album_title}")
    try:
        request = service.albums().list(pageSize=50, excludeNonAppCreatedData=True)
        while request is not None:
            response = await asyncio.to_thread(request.execute)
            albums = response.get('albums', [])
            for album in albums:
                if album['title'] == album_title:
                    logger.info(f"Found existing album: {album_title}")
                    return album['id']
            request = service.albums().list_next(request, response)

        logger.info(f"Album not found, creating new album: {album_title}")
        create_album_body = {'album': {'title': album_title}}
        create_album_response = await asyncio.to_thread(service.albums().create(body=create_album_body).execute)
        album_id = create_album_response.get('id')

        logger.info(f"Sharing album: {album_title}")
        share_album_body = {
            'sharedAlbumOptions': {
                'isCollaborative': 'true',
                'isCommentable': 'true'
            }
        }
        await asyncio.to_thread(service.albums().share(albumId=album_id, body=share_album_body).execute)
        
        logger.info(f"Created and shared new album: {album_title}")
        return album_id
    except Exception as e:
        logger.error(f"Error finding or creating album: {str(e)}")
        return None

async def resize_image(file_path):
    logger.info(f"Resizing image: {file_path}")
    with Image.open(file_path) as img:
        original_size = img.size
        if img.width * img.height > MAX_DIMENSION:
            aspect_ratio = img.width / img.height
            new_height = int((MAX_DIMENSION / aspect_ratio) ** 0.5)
            new_width = int(aspect_ratio * new_height)
            img = img.resize((new_width, new_height), Image.LANCZOS)
            logger.info(f"Resized image from {original_size} to {img.size}")
        else:
            logger.info(f"Image size {original_size} is within limits, no resize needed")
        
        if img.mode != 'RGB':
            img = img.convert('RGB')
            logger.info(f"Converted image to RGB mode")
        
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG', quality=JPEG_QUALITY)
        buffer.seek(0)
        logger.info(f"Image processed and converted to JPEG with quality {JPEG_QUALITY}")
        return buffer.getvalue()

async def upload_single_file(image_data, creds):
    logger.info("Uploading single file to Google Photos")
    upload_url = 'https://photoslibrary.googleapis.com/v1/uploads'
    headers = {
        'Authorization': f'Bearer {creds.token}',
        'Content-Type': 'application/octet-stream',
        'X-Goog-Upload-Protocol': 'raw',
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(upload_url, data=image_data, headers=headers) as upload_response:
            if upload_response.status != 200:
                logger.error(f"Failed to upload image data: {await upload_response.text()}")
                return None
            logger.info("File uploaded successfully")
            return await upload_response.text()  # This now returns a string
  # Changed from content.read() to text()


async def upload_to_google_photos(files_to_upload, album_id, creds):
    logger.info(f"Starting upload process for {len(files_to_upload)} files")
    service = build('photoslibrary', 'v1', credentials=creds, static_discovery=False)
    
    if not album_id:
        logger.info("Album ID not provided, finding or creating album")
        album_id = await find_or_create_album(service, ALBUM_TITLE)

    for i in range(0, len(files_to_upload), MAX_BATCH_SIZE):
        batch = files_to_upload[i:i+MAX_BATCH_SIZE]
        logger.info(f"Processing batch {i//MAX_BATCH_SIZE + 1} with {len(batch)} files")
        upload_tokens = []

        for file_path in batch:
            try:
                logger.info(f"Resizing and uploading file: {file_path}")
                image_data = await resize_image(file_path)
                upload_token = await upload_single_file(image_data, creds)
                if upload_token:
                    upload_tokens.append((file_path, upload_token))
                    logger.info(f"Successfully uploaded file: {file_path}")
                else:
                    logger.warning(f"Failed to get upload token for file: {file_path}")
            except Exception as e:
                logger.error(f"Error uploading {os.path.basename(file_path)}: {str(e)}")

        if upload_tokens:
            try:
                logger.info(f"Creating media items for {len(upload_tokens)} files")
                new_media_items = []
                for file_path, token in upload_tokens:
                    original_filename = os.path.splitext(os.path.basename(file_path))[0]
                    new_media_items.append({
                        'simpleMediaItem': {
                            'uploadToken': token,
                            'fileName': original_filename
                        }
                    })

                request_body = {
                    'newMediaItems': new_media_items,
                    'albumId': album_id
                }

                create_response = await asyncio.to_thread(
                    service.mediaItems().batchCreate(body=request_body).execute
                )

                for (file_path, _), result in zip(upload_tokens, create_response.get('newMediaItemResults', [])):
                    if 'mediaItem' in result:
                        google_photos_filename = result['mediaItem']['filename']
                        logger.info(f"Successfully created media item: {google_photos_filename}")
                        yield file_path, True
                    else:
                        logger.warning(f"Failed to create media item for {os.path.basename(file_path)}: {result.get('status', {}).get('message', 'Unknown error')}")
                        yield file_path, False

            except Exception as e:
                logger.error(f"Error in batch create: {str(e)}")
                for file_path, _ in upload_tokens:
                    yield file_path, False

        logger.info(f"Waiting {UPLOAD_DELAY} seconds before processing next batch")
        await asyncio.sleep(UPLOAD_DELAY)


def get_file_creation_time(file_path):
    try:
        stat = os.stat(file_path)
        creation_time = datetime.fromtimestamp(stat.st_ctime, tz=pytz.UTC)
        return creation_time.strftime("%Y-%m-%dT%H:%M:%SZ")  # RFC3339 UTC "Zulu" format
    except Exception as e:
        logger.error(f"Error getting creation time for {file_path}: {str(e)}")
        return None


async def delete_file_from_onedrive(file, access_token):
    logger.info(f"Deleting file from OneDrive: {file['name']}")
    headers = {"Authorization": f"Bearer {access_token}"}
    delete_url = f"{ONEDRIVE_API_ENDPOINT}/drive/items/{file['id']}"
    async with aiohttp.ClientSession() as session:
        async with session.delete(delete_url, headers=headers) as response:
            if response.status == 204:
                logger.info(f"Successfully deleted {file['name']} from OneDrive")
            else:
                logger.error(f"Failed to delete {file['name']} from OneDrive: {response.status} - {await response.text()}")

async def download_file(file, onedrive_token):
    file_download_url = file['@microsoft.graph.downloadUrl']
    original_file_name = file['name']
    # sanitized_file_name = sanitize_filename(original_file_name)
    file_path = os.path.join(TRANSFERS_FOLDER, original_file_name)
    
    logger.info(f"Downloading file from OneDrive: {original_file_name}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(file_download_url) as response:
                response.raise_for_status()
                content = await response.read()
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)

        # Get creation time from OneDrive metadata
        creation_time = datetime.strptime(file['createdDateTime'], "%Y-%m-%dT%H:%M:%S.%fZ")
        logger.info(f"Original createdDateTime of {original_file_name}: {creation_time}")
        creation_time = creation_time.replace(tzinfo=pytz.UTC)
        logger.info(f"UTC createdDateTime of {original_file_name}: {creation_time}")

        # Add creation time to metadata
        await add_creation_time_to_png(file_path, creation_time)

        logger.info(f"File downloaded and metadata updated successfully: {os.path.basename(file_path)}")
        return file_path
    except Exception as e:
        logger.error(f"Error downloading {original_file_name}: {str(e)}")
        return None

async def add_creation_time_to_png(file_path, creation_time):
    try:
        # Check if creation_time is already a datetime object
        if isinstance(creation_time, datetime):
            creation_time_dt = creation_time
        else:
            # If it's a string, parse it
            creation_time_dt = datetime.strptime(creation_time, "%Y-%m-%d %H:%M:%S.%f")
        
        # Format the creation time as required by EXIF
        exif_time_str = creation_time_dt.strftime("%Y:%m:%d %H:%M:%S")
        
        # Open the image
        with Image.open(file_path) as img:
            # Check if EXIF data already exists
            exif_data = img.info.get('exif', None)
            
            if exif_data:
                # If EXIF exists, load it
                exif_dict = piexif.load(exif_data)
            else:
                # If no EXIF, create a new dictionary
                exif_dict = {"0th":{}, "Exif":{}}
            
            # Add or update DateTimeOriginal tag
            exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = exif_time_str
            
            # Convert EXIF dict to bytes
            exif_bytes = piexif.dump(exif_dict)
            
            # Save the image with the new EXIF data
            img.save(file_path, "PNG", exif=exif_bytes)

        logger.info(f"Creation time added/updated for PNG: {os.path.basename(file_path)}")
    except Exception as e:
        logger.error(f"Error adding creation time to PNG {os.path.basename(file_path)}: {str(e)}")



async def process_files_in_batches(files, album_id, google_creds, onedrive_token):
    logger.info(f"Processing {len(files)} files in batches of {MAX_BATCH_SIZE}")
    
    for i in range(0, len(files), MAX_BATCH_SIZE):
        batch = files[i:i+MAX_BATCH_SIZE]
        logger.info(f"Processing batch {i//MAX_BATCH_SIZE + 1} of {-(-len(files)//MAX_BATCH_SIZE)}")
        
        # Download batch
        downloaded_files = []
        for file in batch:
            if file['name'].lower().endswith('.png'):
                file_path = await download_file(file, onedrive_token)
                if file_path:
                    downloaded_files.append((file, file_path))
            elif file['name'].lower().endswith('.xjr'):
                await delete_file_from_onedrive(file, onedrive_token)

        # Upload batch to Google Photos
        upload_results = []
        async for file_path, upload_success in upload_to_google_photos(
            [f[1] for f in downloaded_files], album_id, google_creds
        ):
            upload_results.append((file_path, upload_success))

        # Process results and clean up
        for (file, file_path), (_, upload_success) in zip(downloaded_files, upload_results):
            if upload_success:
                logger.info(f"Successfully uploaded {file['name']} to Google Photos")
                await delete_file_from_onedrive(file, onedrive_token)
            else:
                logger.warning(f"Failed to upload {file['name']} to Google Photos")
            
            # Clean up local file
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Removed local file: {file_path}")

        logger.info(f"Completed processing batch {i//MAX_BATCH_SIZE + 1}")


async def sync_photos():
    logger.info(f"Starting photo sync at {datetime.now()}")
    
    try:
        onedrive_token = await authenticate_onedrive()
        google_creds = await authenticate_google_photos()
        
        service = build('photoslibrary', 'v1', credentials=google_creds, static_discovery=False)
        album_id = await find_or_create_album(service, ALBUM_TITLE)

        if not album_id:
            raise Exception(f"Failed to find or create Google Photos album '{ALBUM_TITLE}'")
        
        files = await list_files_from_onedrive(ONEDRIVE_FOLDER, onedrive_token)
        
        await process_files_in_batches(files, album_id, google_creds, onedrive_token)
        
        logger.info(f"Sync completed at {datetime.now()}")
    
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}", exc_info=True)

async def main():
    logger.info("Script started")
    await sync_photos()
    logger.info("Script finished")

if __name__ == "__main__":
    asyncio.run(main())
