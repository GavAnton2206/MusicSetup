import os
import time
from pathlib import Path
from yt_dlp import YoutubeDL
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, APIC

BASE_DIR = Path(__file__).resolve().parent
FFMPEG_PATH = BASE_DIR / "venv/Lib/ffmpeg/bin"

MAX_RETRIES = 3
RETRY_DELAY = 2
MAX_CONCURRENT_WORKERS = 5
DEFAULT_CONCURRENT_WORKERS = 3

def convert_image(img: str):
    from os.path import splitext
    path, ext = splitext(img)
    png_file = f"{path}.png"

    from PIL import Image
    png = Image.open(img).convert("RGB")
    png.save(png_file, "png")
    return png_file


def update_metadata(
    file_path: str,
    title: str,
    artist: str,
    album: str,
    cover: str
):
    audio = ID3(file_path)

    audio["TIT2"] = TIT2(encoding=3, text=title)
    audio["TPE1"] = TPE1(encoding=3, text=artist)
    audio["TALB"] = TALB(encoding=3, text=album)

    if cover != "":
        with open(cover, "rb") as img:
            audio["APIC"] = APIC(
        	encoding=3,
        	mime="image/jpeg",
        	type=3,
        	desc="Cover",
        	data=img.read(),
    	)
            
    audio.save()

def download_audio(saveName: str, url: str, output_path: str, thread_id: int = 0) -> dict:
    ydl_opts = {
        "format": "bestaudio/best",
        "ffmpeg_location": str(FFMPEG_PATH),
        "outtmpl": os.path.join(output_path, saveName + ".%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        }],
        "noplaylist": True,
        "retries": MAX_RETRIES,
        "fragment_retries": MAX_RETRIES,
        "quiet": True,
    }

    print(f"[Thread {thread_id}] Starting audio download")

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)

            return {
                "url": url,
                "success": True,
                "count": 1,
                "message": (
                    f"[Thread {thread_id}] Audio download completed. "
                    f"Title: '{info.get('title', 'Unknown')}'. "
                    f"Output directory: {output_path}"
                )
            }

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                delay = RETRY_DELAY * (2 ** (attempt - 1))
                print(
                    f"[Thread {thread_id}] Attempt {attempt} failed. "
                    f"Retrying in {delay} seconds. Error: {str(e)[:200]}"
                )
                time.sleep(delay)

    return {
        "url": url,
        "success": False,
        "count": 0,
        "message": (
            f"[Thread {thread_id}] Audio download failed after "
            f"{MAX_RETRIES} attempts. Last error: {last_error}"
        )
    }

print("URL: ", end = "")
url = input()
while url != "exit":
    print("Title: ", end = "")
    title = input()
    saveName = title.replace(" ", "")
    download_audio(saveName, url, BASE_DIR / "output")
    print("Artist: ", end = "")
    artist = input()
    print("Album: ", end = "")
    album = input()
    if(album == ""):
        album = "Single"
    print("Cover art: ", end = "")
    art = input()
    if art.find(".webp"):
        art = convert_image("cover/" + art)
    update_metadata(BASE_DIR / "output" / (saveName + ".mp3"), title, artist, album, BASE_DIR / art)

    print("-------------------------- Successs! --------------------------")
    print("URL: ", end = "")
    url = input()