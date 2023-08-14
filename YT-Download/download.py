from pytube import YouTube
import pytube.exceptions
import time
from urllib.request import urlopen
from tqdm import tqdm

from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import requests

import urllib.parse as p
import re
import os
import pickle

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


def youtube_authenticate():
    """Performs OAuth 2.0 authentication with googleapis.com."""
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
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secrets_file, SCOPES
            )
            creds = flow.run_local_server(port=0)
        # save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return build(api_service_name, api_version, credentials=creds)


def search(youtube, **kwargs):
    return youtube.search().list(part="snippet", **kwargs).execute()


def get_user_id(youtube):
    """Get the user's YouTube channel ID."""
    return youtube.channels().list(part="id", mine=True).execute()["items"][0]["id"]


def get_playlist_id(youtube, channel_id, playlist_name):
    """Get the playlist ID for a given playlist name."""
    for i in (
        youtube.playlists()
        .list(part="snippet", channelId=channel_id)
        .execute()
        .get("items")
    ):
        if i["snippet"]["title"] == playlist_name:
            return i["id"]

    raise Exception(f"Cannot find playlist:{playlist_name}")


def parse_url(url):
    """Return a dict of the query parameters of a URL."""

    # if url is for a short raise error
    if "/short" in url:
        raise Exception("URL's for shorts are not supported")

    return p.parse_qs(p.urlsplit(url).query)["v"][0]


def get_videos_from_playlist(youtube, playlist_id):
    """Get all video ids in a playlist."""
    request = youtube.playlistItems().list(
        part="snippet", playlistId=playlist_id, maxResults=50
    )

    playlist_videos = []

    while request:
        response = request.execute()
        playlist_videos += response["items"]
        request = youtube.playlistItems().list_next(request, response)

    return playlist_videos


def get_video_from_url(youtube, video_url):
    """Gets video object from a video URL."""
    video_id = parse_url(video_url)

    request = youtube.videos().list(part="snippet", id=video_id)

    response = request.execute()

    return response["items"]


def get_video_details(videos, video_url):
    """Get video details from a list of video objects."""
    video_information = {}
    sub_details = {}

    for video in videos:
        try:
            video_id = video["snippet"]["resourceId"]["videoId"]
        except KeyError:
            video_id = video["id"]

        video_channel_title = video["snippet"].get(
            "VideoOwnerChannelTitle", video["snippet"]["channelTitle"]
        )
        video_title = video["snippet"]["title"]
        video_description = video["snippet"]["description"]
        video_url = video_url or f"https://www.youtube.com/watch?v={video_id}"

        sub_details.update(
            {
                "video_channel_title": video_channel_title,
                "video_title": video_title,
                "video_description": video_description,
                "video_url": video_url,
            }
        )

        video_information[video_id] = sub_details

    if video_information:
        return video_information
    else:
        raise Exception("No videos found")


def download_with_progress(stream, file_path):
    """Download a video with a progress bar."""
    response = urlopen(stream.url)
    total_size = int(response.getheader("content-length"))

    with tqdm(
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=stream.default_filename,
        ascii=True,
    ) as pbar:
        with open(file_path, "wb") as file:
            chunk_size = 1024 * 256  # 256 KB chunks
            for chunk in iter(lambda: response.read(chunk_size), b""):
                file.write(chunk)
                pbar.update(len(chunk))


def main():
    youtube = youtube_authenticate()

    # user choice to download from own channel or another channel
    channel_type = input(
        "Enter 1 to download from your own channel or 2 to download from another channel: "
    )

    if channel_type == "1":
        channel_id = get_user_id(youtube)
    else:
        channel_id = input("Enter the channel id: ")

    video_url = None

    download_type = input(
        "Enter 1 to download a single video or 2 to download from a playlist : "
    )
    if download_type == "1":
        video_url = input("Enter the video url: ")
        video = get_video_from_url(youtube, video_url)

    else:
        playlist_name = input("Enter the playlist name: ")
        playlist_id = get_playlist_id(youtube, channel_id, playlist_name)
        video = get_videos_from_playlist(youtube, playlist_id)

    video_details = get_video_details(video, video_url)
    print(video_details)

    # video_url = "https://www.youtube.com/watch?v=PJg_rnK7TFo"
    # video = YouTube(video_url)
    # video_stream = video.streams.get_highest_resolution()

    # title = video.title

    # download_path = "./Downloads/Markiplier"

    try:
        start_time = time.time()
        # download_with_progress(video_stream, f"{download_path}/{title}.mp4")
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


if __name__ == "__main__":
    main()
