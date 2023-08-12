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

def youtube_authenticate():
    '''Performs OAuth 2.0 authentication with googleapis.com.'''
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    api_service_name = "youtube"
    api_version = "v3" 
    client_secrets_file = "credentials.json"
    creds = None
    # the file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)
    # if there are no (valid) credentials availablle, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secrets_file, SCOPES)
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build(api_service_name, api_version, credentials=creds)

youtube_authenticate = youtube_authenticate()

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
