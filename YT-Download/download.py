from pytube import YouTube
import pytube.exceptions
import time
from urllib.request import urlopen
from tqdm import tqdm

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

import urllib.parse as p
import re
import os
import pickle

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

def download_with_progress(stream, file_path):
    response = urlopen(stream.url)
    total_size = int(response.getheader('content-length'))

    with tqdm(total=total_size, unit='B', unit_scale=True, unit_divisor=1024, desc=stream.default_filename, ascii=True) as pbar:
        with open(file_path, 'wb') as file:
            chunk_size = 1024 * 256  # 256 KB chunks
            for chunk in iter(lambda: response.read(chunk_size), b''):
                file.write(chunk)
                pbar.update(len(chunk))

video_url = "https://www.youtube.com/watch?v=PJg_rnK7TFo"

video = YouTube(video_url)
video_stream = video.streams.get_highest_resolution()

title = video.title

download_path = "./Downloads/Markiplier"


try:
    start_time = time.time()
    download_with_progress(video_stream, f"{download_path}/{title}.mp4")
    end_time = time.time()

    total_time = end_time - start_time

    # Convert total time to minutes and seconds
    elapsed_minutes = int(total_time // 60)
    elapsed_seconds = int(total_time % 60)

    print("Download Completed!")
    print(f"Download time: {elapsed_minutes} minutes, {elapsed_seconds} seconds")

except pytube.exceptions.PytubeError as e:
    print("An error occurred:", str(e))
except Exception as e:
    print("An unexpected error occurred:", str(e))
