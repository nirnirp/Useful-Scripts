"""
- Installation -
pip install youtube_dl mutagen requests

- On Ubuntu/Debian
sudo apt-get install ffmpeg
- On macOS
brew install ffmpeg
"""

import os
import json
import youtube_dl
import requests
from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from mutagen.mp3 import MP3

def download_soundcloud_playlist(playlist_url, download_directory='downloads'):
    # Set up youtube-dl options
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(download_directory, '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',
        }],
        'noplaylist': False,  # Set to False to download playlists
        'extractaudio': True,  # Only keep the audio
        'audioformat': "mp3",  # Convert to mp3
        'ignoreerrors': True,  # Skip errors
        'quiet': False,        # Print messages
        'writeinfojson': True, # Write metadata to JSON
    }

    # Create the download directory if it doesn't exist
    if not os.path.exists(download_directory):
        os.makedirs(download_directory)

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([playlist_url])

    # Process each downloaded track
    for file_name in os.listdir(download_directory):
        if file_name.endswith('.mp3'):
            track_path = os.path.join(download_directory, file_name)
            json_path = track_path.replace('.mp3', '.info.json')
            
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    track_info = json.load(f)
                
                # Download the track image
                if 'thumbnail' in track_info:
                    image_url = track_info['thumbnail']
                    image_data = requests.get(image_url).content
                    
                    # Initialize MP3 file with ID3 tag if missing
                    try:
                        audio = ID3(track_path)
                    except ID3NoHeaderError:
                        audio = ID3()  # Create a new ID3 tag if not present
                        audio.save(track_path)  # Save the empty ID3 tag
                    
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
                
                # Remove the JSON file after processing
                os.remove(json_path)
                
                # Remove the image file if it was saved
                image_path = track_path.replace('.mp3', '.jpg')
                if os.path.exists(image_path):
                    os.remove(image_path)
    
    # Optional: Clean up any other files or folders that are not MP3s
    for file_name in os.listdir(download_directory):
        file_path = os.path.join(download_directory, file_name)
        if not file_name.endswith('.mp3'):
            os.remove(file_path)

if __name__ == "__main__":
    playlist_url = input("Enter the SoundCloud playlist URL: ")
    download_soundcloud_playlist(playlist_url)
