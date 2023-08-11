from pytube import YouTube
import pytube.exceptions
import time
from tqdm import tqdm


video = YouTube("https://www.youtube.com/watch?v=DLk7nkxgsq8")
video_stream = video.streams.get_highest_resolution()

title = video.title

download_path = "./Downloads/Markiplier"

start_time = time.time()
try:
    start_time = time.time()
    video_stream.download(output_path=download_path, filename=title)
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
