"""
- Installation -
pip install youtube-dl

- On Ubuntu/Debian
sudo apt-get install ffmpeg
- On macOS
brew install ffmpeg
"""

import os
import youtube_dl 

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
        'noplaylist': False,
        'extractaudio': True,
        'audioformat': "mp3",
        'ignoreerrors': True,
        'quiet': False,
}

    # Create the download directory if it doesn't exist
    if not os.path.exists(download_directory):
        os.makedirs(download_directory)

    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        ydl.download([playlist_url])

if __name__ == "__main__":
    playlist_url = input("Enter the SoundCloud playlist URL: ")
    download_soundcloud_playlist(playlist_url)
