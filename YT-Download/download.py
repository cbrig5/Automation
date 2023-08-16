from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import threading
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
    next_page_token = None
    while True:
        request = youtube.playlists().list(
            part="snippet",
            channelId=channel_id,
            maxResults=50,
            pageToken=next_page_token,
        )
        response = request.execute()

        for playlist in response["items"]:
            if playlist["snippet"]["title"] == playlist_name:
                return playlist["id"]

        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break

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


def get_video_details(videos, video_url, playlist_name):
    """Get video details from a list of video objects."""
    video_information = {}
    sub_details = {}

    for video in videos:
        try:
            video_id = video["snippet"]["resourceId"]["videoId"]
        except KeyError:
            video_id = video["id"]

        playlist_name = playlist_name
        video_channel_title = video["snippet"].get(
            "videoOwnerChannelTitle", video["snippet"]["channelTitle"]
        )
        video_title = video["snippet"]["title"]
        video_description = video["snippet"]["description"]
        video_url = video_url or f"https://www.youtube.com/watch?v={video_id}"

        sub_details = {
            "playlist_name": playlist_name,
            "video_channel_title": video_channel_title,
            "video_title": video_title,
            "video_description": video_description,
            "video_url": video_url,
        }

        video_information[video_id] = sub_details

    if video_information:
        return video_information
    else:
        raise Exception("No videos found")


def check_path(path):
    """Check if the path exists, if not create it."""
    if not os.path.exists(path):
        os.makedirs(path)


def make_stream_obj(url):
    """Return a stream object from a video URL."""
    return YouTube(url).streams.get_highest_resolution()


def download_chunk(response, channel_file, playlist_file, pbar):
    chunk_size = 1024 * 256  # 256 KB chunks
    for chunk in iter(lambda: response.read(chunk_size), b""):
        channel_file.write(chunk)
        if playlist_file:
            playlist_file.write(chunk)
        pbar.update(len(chunk))


def download_video_with_progress(args):
    stream, channel_path, playlist_path, title = args

    total_size = stream.filesize

    with tqdm(
        total=total_size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=title,
        ascii=True,
    ) as pbar:
        with ExitStack() as stack:
            channel_file = stack.enter_context(open(channel_path, "wb"))
            playlist_file = stack.enter_context(open(playlist_path, "wb")) if playlist_path else None

            response = urlopen(stream.url)

            download_chunk(response, channel_file, playlist_file, pbar)


def download_video(video_details, path):
    for video in video_details:
        url = video_details[video]["video_url"]
        title = video_details[video]["video_title"]
        channel = video_details[video]["video_channel_title"]
        check_path(f"{path}/{channel}")
        channel_path = f"{path}/{channel}/{title}.mp4"
        playlist = video_details[video]["playlist_name"]
        if playlist:
            check_path(f"{path}/{playlist}")
        playlist_path = f"{path}/{playlist}/{title}.mp4" if playlist else None

        stream = make_stream_obj(url)

        args = (stream, channel_path, playlist_path, title)
        download_video_with_progress(args)


def get_time(start_time, end_time):
    """Return the elapsed time between two times in minutes and seconds."""
    total_time = end_time - start_time

    elapsed_minutes = int(total_time // 60)
    elapsed_seconds = int(total_time % 60)

    return elapsed_minutes, elapsed_seconds


def main():
    youtube = youtube_authenticate()

    video_url = None

    download_type = input(
        "Enter 1 to download a single video or 2 to download from a playlist: "
    )

    if download_type == "1":
        video_url = input("Enter the video url: ")
        video = get_video_from_url(youtube, video_url)
        playlist_name = None

    else:
        # user choice to download from own channel or another channel
        channel_type = input(
            "Enter 1 to download from your own channel or 2 to download from another channel: "
        )
        if channel_type == "1":
            channel_id = get_user_id(youtube)
        else:
            channel_id = input("Enter the channel id: ")
        playlist_name = input("Enter the playlist name: ")
        playlist_id = get_playlist_id(youtube, channel_id, playlist_name)
        video = get_videos_from_playlist(youtube, playlist_id)

    video_details = get_video_details(video, video_url, playlist_name)

    download_path = input("Enter the path to download the video: ")

    try:
        start_time = time.time()

        download_video(video_details, download_path)

        end_time = time.time()

        elapsed_minutes, elapsed_seconds = get_time(start_time, end_time)
        print("Download Completed!")
        print(f"Download time: {elapsed_minutes} minutes, {elapsed_seconds} seconds")

    except pytube.exceptions.PytubeError as e:
        print("An error occurred:", str(e))
    except Exception as e:
        print("An unexpected error occurred:", str(e))


if __name__ == "__main__":
    main()
