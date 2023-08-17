from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
import threading
from tkinter import Entry, filedialog, simpledialog, ttk, messagebox
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

import tkinter as tk
from tkinter import ttk
from ttkthemes import ThemedTk

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]


class CustomDialog:
    def __init__(
        self, parent, title, prompt, button_text, dialog_width, dialog_height, x, y
    ):
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.configure(background="#61677A")

        ttk.Label(self.dialog, text=prompt).pack(pady=(10, 0))

        self.entry = ttk.Entry(self.dialog)
        self.entry.pack(pady=(5, 10))

        button = ttk.Button(self.dialog, text=button_text, command=self.get_result)
        button.pack(pady=5)

        # Adjust dialog size and position
        x_position = parent.winfo_rootx() + (parent.winfo_width() - dialog_width) // x
        y_position = parent.winfo_rooty() + (parent.winfo_height() - dialog_height) // y
        self.dialog.geometry(
            "{}x{}+{}+{}".format(dialog_width, dialog_height, x_position, y_position)
        )

    def get_result(self):
        self.result = self.entry.get()
        self.dialog.destroy()


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


def download_chunk(response, channel_file, playlist_file, pbar, root, pb):
    chunk_size = 1024 * 256  # 256 KB chunks
    for chunk in iter(lambda: response.read(chunk_size), b""):
        channel_file.write(chunk)
        if playlist_file:
            playlist_file.write(chunk)
        pbar.update(len(chunk))

        pb.step(len(chunk))

        root.update()


def download_video_with_progress(args):
    stream, channel_path, playlist_path, title, root = args

    total_size = stream.filesize

    label = tk.Label(root, text=f"Downloading {title}...", wraplength=350)
    label.pack(pady=(40, 0))

    pb = ttk.Progressbar(root, orient="horizontal", mode="determinate", length=280)

    pb.pack(pady=(5))
    pb["maximum"] = total_size

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
            playlist_file = (
                stack.enter_context(open(playlist_path, "wb"))
                if playlist_path
                else None
            )

            response = urlopen(stream.url)

            download_chunk(response, channel_file, playlist_file, pbar, root, pb)

    label.destroy()
    pb.destroy()

    root.update()


def download_video(video_details, path, root):
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

        args = (stream, channel_path, playlist_path, title, root)
        download_video_with_progress(args)

        # root.after(50)


def get_time(start_time, end_time):
    """Return the elapsed time between two times in minutes and seconds."""
    total_time = end_time - start_time

    elapsed_minutes = int(total_time // 60)
    elapsed_seconds = int(total_time % 60)

    return elapsed_minutes, elapsed_seconds


def center_popup(root, popup, popup_width, popup_height, x, y):
    """Center the popup window on the screen."""
    x = root.winfo_x() + (root.winfo_width() - popup_width) // x
    y = root.winfo_y() + (root.winfo_height() - popup_height) // y

    popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")


def gui_download(video_details, download_path, root):
    start_time = time.time()

    download_video(video_details, download_path, root)

    end_time = time.time()
    elapsed_minutes, elapsed_seconds = get_time(start_time, end_time)

    messagebox.showinfo(
        "Information",
        f"Download Completed!\n\nDownload time: {elapsed_minutes} minutes, {elapsed_seconds} seconds",
    )


def playlist_download_button(youtube, popup, root, user_id, download_path):
    popup.destroy()
    if user_id:
        channel_id = get_user_id(youtube)
    else:
        channel__id_dialog = CustomDialog(
            root, "Input", "Enter the channel id:", "Enter", 300, 100, 2, 2
        )
        root.wait_window(channel__id_dialog.dialog)
        channel_id = channel__id_dialog.result

    if channel_id:
        playlist_dialog = CustomDialog(
            root, "Input", "Enter the playlist name:", "Download", 300, 100, 2, 2
        )
        root.wait_window(playlist_dialog.dialog)
        playlist_name = playlist_dialog.result
        playlist_id = get_playlist_id(youtube, channel_id, playlist_name)
        videos = get_videos_from_playlist(youtube, playlist_id)
        video_details = get_video_details(videos, None, playlist_name)

        gui_download(video_details, download_path, root)


def single_download_button(youtube, root, download_path):
    url_dialog = CustomDialog(
        root, "Input", "Enter video url:", "Download", 300, 100, 2, 2
    )
    root.wait_window(url_dialog.dialog)
    video_url = url_dialog.result

    if video_url:
        video = get_video_from_url(youtube, video_url)
        video_details = get_video_details(video, video_url, None)
        gui_download(video_details, download_path, root)


def show_playlist_popup(youtube, root, download_path):
    popup = tk.Toplevel(root)
    popup.configure(background="#61677A")
    popup.title("Whose channel?")

    popup_width = 350
    popup_height = 100

    x = 2
    y = 2

    center_popup(root, popup, popup_width, popup_height, x, y)

    button1 = ttk.Button(
        popup,
        text="My channel",
        command=lambda: playlist_download_button(
            youtube, popup, root, True, download_path
        ),
    )
    button1.pack(padx=10, pady=(10, 5))

    button2 = ttk.Button(
        popup,
        text="Other channel",
        command=lambda: playlist_download_button(
            youtube, popup, root, False, download_path
        ),
    )
    button2.pack(padx=10, pady=5)


def download_type_button(youtube, root, single):
    # Ask the user to select a folder.
    download_path = filedialog.askdirectory(
        parent=root, initialdir=os.getcwd(), title="Please select a download path:"
    )
    # check download_path
    if download_path:
        check_path(download_path)

        if single:
            single_download_button(youtube, root, download_path)
        else:
            show_playlist_popup(youtube, root, download_path)


def gui(youtube):
    """GUI for the program."""
    window = ThemedTk(theme="black")
    window.title("YouTube Downloader")
    window.configure(background="#61677A")
    window.geometry("500x250")

    style = ttk.Style()
    style.configure("Large.TLabel", font=("Anson", 17))

    label_frame = ttk.Frame(window)
    label_frame.pack(pady=(10))

    label = ttk.Label(
        label_frame, text="Welcome to my YouTube Downloader!", style="Large.TLabel"
    )
    label.pack(pady=(10), padx=(15))

    style.configure("Large.TButton", font=("Helvetica", 14), padding=10)
    button_width = 23

    single_button = ttk.Button(
        window,
        text="Download a single video",
        style="Large.TButton",
        width=button_width,
        command=lambda: download_type_button(youtube, window, True),
    )
    single_button.pack(pady=10)

    playlist_button = ttk.Button(
        window,
        text="Download a playlist",
        style="Large.TButton",
        width=button_width,
        command=lambda: download_type_button(youtube, window, False),
    )
    playlist_button.pack(pady=10)

    window.mainloop()


def main():
    youtube = youtube_authenticate()

    gui(youtube)


if __name__ == "__main__":
    main()
