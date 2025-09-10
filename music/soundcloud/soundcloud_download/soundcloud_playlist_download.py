"""
- Installation -
pip install yt-dlp mutagen requests

- On Ubuntu/Debian
sudo apt-get install ffmpeg
- On macOS
brew install ffmpeg
"""

import os
import json
import sys
import argparse
import yt_dlp
import requests
from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from mutagen.mp3 import MP3

def normalize_title(title):
    """Normalize track title for comparison by removing all non-alphanumeric characters"""
    import re
    # Remove all non-alphanumeric characters and normalize spaces
    normalized = re.sub(r'[^a-zA-Z0-9\s]', '', title)
    normalized = ' '.join(normalized.split())  # Remove extra whitespace
    return normalized.lower()  # Convert to lowercase for comparison

def debug_print(message, debug_mode=False):
    """Print debug messages only when debug mode is enabled"""
    if debug_mode:
        print(message)

def download_soundcloud_playlist(playlist_url, download_directory='downloads', debug_mode=False):
    print(f"🔍 Starting download of playlist: {playlist_url}")
    print(f"📁 Download directory: {download_directory}")
    
    if debug_mode:
        # DEBUG: Print all variables in scope
        print(f"🔍 DEBUG - Variables in scope:")
        print(f"   playlist_url: {playlist_url}")
        print(f"   download_directory: {download_directory}")
        print(f"   Current working directory: {os.getcwd()}")
    
    # Set up yt-dlp options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(download_directory, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'noplaylist': False,  # Set to False to download playlists
        'ignoreerrors': True,  # Skip errors
        'quiet': False,  # Only be quiet if not in debug mode
        'writeinfojson': True, # Write metadata to JSON
        'keepvideo': False,    # Don't keep video files
        'concurrent_fragment_downloads': 4,  # Download fragments in parallel
        'fragment_retries': 2,  # Retry failed fragments
        'retries': 1,  # Retry failed downloads
        'socket_timeout': 30,  # Timeout for network operations
        'http_chunk_size': 10485760,  # 10MB chunks for faster downloads
        'no_check_certificate': True, # Skip SSL verification
    }
    
    # DEBUG: Print ydl_opts configuration
    debug_print(f"🔍 DEBUG - yt-dlp options:", debug_mode)
    if debug_mode:
        for key, value in ydl_opts.items():
            print(f"   {key}: {value}")
    
    # Create the download directory if it doesn't exist
    if not os.path.exists(download_directory):
        os.makedirs(download_directory)
        print(f"✅ Created download directory: {download_directory}")

    # Download the playlist directly (no need to extract info twice)
    print("⬇️  Starting download process...")
    
    # Extract playlist info to get expected tracks
    print("📋 Extracting playlist information...")
    expected_tracks = []
    download_errors = {}  # Track download errors
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'extract_flat': False}) as ydl:
            info = ydl.extract_info(playlist_url, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if entry:
                        expected_tracks.append({
                            'title': entry.get('title', 'Unknown Title'),
                            'url': entry.get('webpage_url', 'Unknown URL'),
                            'id': entry.get('id', 'Unknown ID')
                        })
                print(f"📊 Expected tracks in playlist: {len(expected_tracks)}")
    except Exception as e:
        print(f"⚠️  Could not extract playlist info: {e}")
        expected_tracks = []
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([playlist_url])

    # Wait for FFmpeg conversion to complete
    print("⏳ Waiting for FFmpeg conversion to complete...")
    import time
    time.sleep(2)  # Give FFmpeg time to finish converting files

    print("🔄 Processing downloaded tracks...")
    
    # Track successfully downloaded files
    downloaded_tracks = []
    
    # DEBUG: Print download directory contents before processing
    debug_print(f"🔍 DEBUG - Files in download directory before processing:", debug_mode)
    if debug_mode:
        for file_name in os.listdir(download_directory):
            file_path = os.path.join(download_directory, file_name)
            file_size = os.path.getsize(file_path) if os.path.isfile(file_path) else 'DIR'
            print(f"   {file_name} ({file_size} bytes)")
    
    # Process each downloaded track
    for file_name in os.listdir(download_directory):
        if file_name.endswith('.mp3'):
            track_path = os.path.join(download_directory, file_name)
            json_path = track_path.replace('.mp3', '.info.json')
            
            # Extract track title from filename (remove .mp3 extension)
            track_title = file_name.replace('.mp3', '')
            downloaded_tracks.append(track_title)
            
            print(f"🎵 Processing: {track_title}")
            
            # DEBUG: Print file processing details
            debug_print(f"🔍 DEBUG - Processing file: {file_name}", debug_mode)
            if debug_mode:
                print(f"   Track path: {track_path}")
                print(f"   JSON path: {json_path}")
                print(f"   JSON exists: {os.path.exists(json_path)}")
            
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    track_info = json.load(f)
                
                # DEBUG: Print track info structure (but not binary data)
                debug_print(f"🔍 DEBUG - Track info keys: {list(track_info.keys())}", debug_mode)
                if debug_mode:
                    # Only print non-binary track info
                    safe_track_info = {}
                    for key, value in track_info.items():
                        if isinstance(value, str) and len(str(value)) < 100:  # Avoid long strings
                            safe_track_info[key] = value
                        elif isinstance(value, (int, float, bool)):
                            safe_track_info[key] = value
                        else:
                            safe_track_info[key] = f"[{type(value).__name__}]"
                    print(f"🔍 DEBUG - Track info (safe): {safe_track_info}")
                
                # Download the track image
                if 'thumbnail' in track_info:
                    image_url = track_info['thumbnail']
                    print(f"🖼️  Downloading artwork for: {track_title}")
                    debug_print(f"🔍 DEBUG - Image URL: {image_url}", debug_mode)
                    
                    try:
                        image_data = requests.get(image_url).content
                        debug_print(f"🔍 DEBUG - Downloaded image size: {len(image_data)} bytes", debug_mode)
                        
                        # Initialize MP3 file with ID3 tag if missing
                        try:
                            audio = ID3(track_path)
                            debug_print(f"🔍 DEBUG - Existing ID3 tags: {list(audio.keys()) if audio else 'None'}", debug_mode)
                        except ID3NoHeaderError:
                            audio = ID3()  # Create a new ID3 tag if not present
                            audio.save(track_path)  # Save the empty ID3 tag
                            debug_print(f"🔍 DEBUG - Created new ID3 tag for: {track_path}", debug_mode)
                        
                        # Embed the image as album art in the MP3 file
                        audio = ID3(track_path)
                        audio['APIC'] = APIC(
                            encoding=3,  # 3 is for utf-8
                            mime='image/jpeg',  # Image mime type
                            type=3,  # 3 is for album front cover
                            desc=u'Cover',
                            data=image_data
                        )
                        audio.save()
                        print(f"✅ Artwork embedded for: {track_title}")
                        debug_print(f"🔍 DEBUG - APIC tag added successfully", debug_mode)
                    except Exception as e:
                        print(f"❌ Failed to embed artwork for {track_title}: {e}")
                        debug_print(f"🔍 DEBUG - Error details: {type(e).__name__}: {str(e)}", debug_mode)
                
                # Remove the JSON file after processing
                os.remove(json_path)
                debug_print(f"🔍 DEBUG - Removed JSON file: {json_path}", debug_mode)
                
                # Remove the image file if it was saved
                image_path = track_path.replace('.mp3', '.jpg')
                if os.path.exists(image_path):
                    os.remove(image_path)
                    debug_print(f"🔍 DEBUG - Removed image file: {image_path}", debug_mode)
    
    # Clean up any other files or folders that are not MP3s
    print("🧹 Cleaning up temporary files...")
    for file_name in os.listdir(download_directory):
        file_path = os.path.join(download_directory, file_name)
        if not file_name.endswith('.mp3'):
            os.remove(file_path)
            debug_print(f"🔍 DEBUG - Removed temporary file: {file_name}", debug_mode)
    
    # DEBUG: Print final state
    debug_print(f"🔍 DEBUG - Final downloaded tracks: {downloaded_tracks}", debug_mode)
    debug_print(f"🔍 DEBUG - Final expected tracks: {[t['title'] for t in expected_tracks]}", debug_mode)
    debug_print(f"🔍 DEBUG - Download errors captured: {download_errors}", debug_mode)
    
    # Analyze failed downloads
    print("\n" + "="*60)
    print("📊 DOWNLOAD SUMMARY")
    print("="*60)
    
    if expected_tracks:
        print(f"📋 Expected tracks: {len(expected_tracks)}")
        print(f"✅ Successfully downloaded: {len(downloaded_tracks)}")
        
        # Find failed downloads with improved matching using simplified normalization
        failed_tracks = []
        for expected in expected_tracks:
            expected_title = expected['title']
            expected_normalized = normalize_title(expected_title)
            
            # Check if any downloaded track title matches the expected title
            found = False
            for downloaded in downloaded_tracks:
                downloaded_normalized = normalize_title(downloaded)
                
                # Try multiple matching strategies with simplified normalization
                if (expected_normalized == downloaded_normalized or
                    expected_normalized in downloaded_normalized or
                    downloaded_normalized in expected_normalized):
                    found = True
                    if debug_mode:
                        print(f"🔍 DEBUG - MATCH FOUND: '{expected_title}' -> '{downloaded}'")
                    break
            
            if not found:
                # Add error reason if available
                error_reason = download_errors.get(expected_title, 'Unknown error - track not found in downloads')
                failed_tracks.append({
                    **expected,
                    'error_reason': error_reason
                })
                if debug_mode:
                    print(f"🔍 DEBUG - NO MATCH: '{expected_title}' (normalized: '{expected_normalized}')")
        
        if failed_tracks:
            print(f"❌ Failed downloads: {len(failed_tracks)}")
            print("\n🚫 TRACKS THAT FAILED TO DOWNLOAD:")
            print("-" * 50)
            for i, track in enumerate(failed_tracks, 1):
                print(f"{i}. {track['title']}")
                print(f"   URL: {track['url']}")
                print(f"   ID: {track['id']}")
                print(f"   Error: {track['error_reason']}")
                print()
        else:
            print("🎉 All tracks downloaded successfully!")
    else:
        print("⚠️  Could not determine expected tracks - cannot analyze failures")
    
    print(f"📁 Final MP3 files in {download_directory}: {len(downloaded_tracks)}")
    print("="*60)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Download SoundCloud playlist')
    parser.add_argument('-p', '--playlist', type=str, help='SoundCloud playlist URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    
    args = parser.parse_args()
    
    # Get playlist URL from command line or prompt user
    if args.playlist:
        playlist_url = args.playlist
    else:
        playlist_url = input("Enter the SoundCloud playlist URL: ")
    
    print(f"🔍 DEBUG - Using playlist URL: {playlist_url}")
    print(f"🔍 DEBUG - Debug mode: {args.debug}")
    
    download_soundcloud_playlist(playlist_url, debug_mode=args.debug)
