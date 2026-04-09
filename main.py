import os
import time
from pathlib import Path
from yt_dlp import YoutubeDL
from pytubefix import YouTube
import requests
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TRCK, TDRC, TCON, APIC, TXXX

BASE_DIR = Path(__file__).resolve().parent
# FFMPEG_PATH = "/opt/homebrew/bin/ffmpeg" # -> MacOS
FFMPEG_PATH = "C:/Anton/Dev/Projects/Active/MusicSetup/venv/Lib/ffmpeg/bin/"
PLAYLIST_PATH = "/Users/anton/Music/tplaylists"

MAX_RETRIES = 3
RETRY_DELAY = 2
MAX_CONCURRENT_WORKERS = 5
DEFAULT_CONCURRENT_WORKERS = 3

# -------------------------------------------------
def read_metadata(filepath):
    audio = ID3(filepath)
    
    meta = {}
    meta["title"] = audio.get("TIT2").text[0] if audio.get("TIT2") else None
    meta["artist"] = audio.get("TPE1").text[0] if audio.get("TPE1") else None
    meta["album"] = audio.get("TALB").text[0] if audio.get("TALB") else None
    meta["genre"] = audio.get("TCON").text[0] if audio.get("TCON") else None
    meta["year"] = audio.get("TDRC").text[0] if audio.get("TDRC") else None
    meta["playlists"] = read_playlists(audio)

    print(f"Title: {meta["title"]}")
    print(f"Artist: {meta["artist"]}")
    print(f"Album: {meta["album"]}")
    print(f"Genre: {meta["genre"]}")
    print(f"Year: {meta["year"]}")
    print(f"Playlists: {meta["playlists"]}")

# -------------------------------------------------
def change_playlists(audio, playlists):
    audio.delall("TXXX:playlists")
    audio.add(
        TXXX(
            encoding=3,              # UTF-8
            desc="playlists",        # your custom tag name
            text=playlists
        )
    )

    audio.save()

def read_playlists(audio):
    for frame in audio.getall("TXXX"):
        if frame.desc == "playlists":
            return tuple(frame.text)
    return ()

def set_playlists(music_dir: str):
    for filename in os.listdir(music_dir):
        if not filename.endswith(".mp3"):
            continue
        try:
            audio = ID3(os.path.join(music_dir, filename))
            playlists = read_playlists(audio)
            cmd = input(f"Update the playlists of [{filename}]: {playlists}? [enter/new playlists] ")
            if cmd and cmd != "n":
                change_playlists(audio, cmd.split())
        except Exception:
            continue

    print(f"✓ '{music_dir}': worked through all files.")

def set_empty_playlists(music_dir: str):
    for filename in os.listdir(music_dir):
        if not filename.endswith(".mp3"):
            continue
        try:
            audio = ID3(os.path.join(music_dir, filename))
            playlists = read_playlists(audio)
            if(len(playlists) == 0):
                cmd = input(f"Update the playlists of [{filename}]: {playlists}? [enter/new playlists] ")
                if cmd and cmd != "n":
                    change_playlists(audio, cmd.split())
        except Exception:
            continue

    print(f"✓ '{music_dir}': worked through all files.")

def create_playlist(playlist_name: str, music_dir: str, output_dir: str = "output/"):
    matches = []

    for filename in os.listdir(music_dir):
        if not filename.endswith(".mp3"):
            continue
        try:
            audio = ID3(os.path.join(music_dir, filename))
            playlists = read_playlists(audio)
            if playlist_name in playlists:
                matches.append(filename)
        except Exception:
            continue

    playlist_path = os.path.join(output_dir, f"{safe_filename(playlist_name)}.m3u8")
    with open(playlist_path, "w", encoding="utf-8") as f:
        for filename in sorted(matches):
            f.write(f"../Library/{filename}\n")

    print(f"✓ '{playlist_name}': {len(matches)} tracks → {playlist_path}")

def get_youtube_title(url: str) -> str:
    try:
        yt = YouTube(url)
        return yt.title
    except Exception as e:
        print(f"Failed to get title: {e}")
        res = input("Manual Title:")
        return res

def download_image(url: str, save_path: str) -> bool:
    response = requests.get(url)
    if response.status_code == 200:
        with open(save_path, "wb") as f:
            f.write(response.content)
        return True
    return False

def convert_image(img: str):
    from os.path import splitext
    path, ext = splitext(img)
    png_file = f"{path}.png"

    from PIL import Image
    png = Image.open(img).convert("RGB")
    png.save(png_file, "png")
    return png_file

def get_itunes_metadata(artist: str, title: str) -> dict:
    response = requests.get(
        "https://itunes.apple.com/search",
        params={"term": f"{artist} {title}", "media": "music", "limit": 1}
    )
    results = response.json().get("results", [])
    if not results:
        return {}

    r = results[0]
    return {
        "title":     r.get("trackName", ""),
        "artist":    r.get("artistName", ""),
        "album":     r.get("collectionName", ""),
        "year":      r.get("releaseDate", "")[:4],  # "2018-01-01" → "2018"
        "genre":     r.get("primaryGenreName", ""),
        "cover_url": r.get("artworkUrl100", "").replace("100x100", "600x600")
    }

def parse_artists(yt_title: str) -> tuple[str, str, str]:
    clean = yt_title.split(" | ")[0].strip()

    trash = ["[Official Lyric Video]", "(Official Lyric Video)",
             "[Lyric Video]", "(Lyric Video)",
             "[Official Music Video]", "(Official Music Video)",
             "[Music Video]", "(Music Video)",
              "[Official Audio]", "(Official Audio)",
              "[Live Performance]", "(Live Performance)",
              "[Extended]", "(Extended)"]
    
    for word in trash:
        clean = clean.replace(word, "")

    dash_parts = clean.split(" - ", 1)
    artists_raw = dash_parts[0].strip()
    title_and_feat = dash_parts[1].strip() if len(dash_parts) > 1 else ""

    feat_artist = ""
    title = title_and_feat
    if "(feat." in title_and_feat:
        before_feat, feat_part = title_and_feat.split("(feat.", 1)
        title = before_feat.strip()
        feat_artist = feat_part.replace(")", "").strip()

    for sep in [" & ", " x ", " X ", ", ", "; "]:
        artists_raw = artists_raw.replace(sep, ", ")
    main_artists = [a.strip() for a in artists_raw.split(", ") if a.strip()]

    artists_title = ", ".join(main_artists)
    if feat_artist:
        artists_title += f" feat. {feat_artist}"

    all_artists = main_artists + ([feat_artist] if feat_artist else [])
    artists_tags = "; ".join(all_artists)

    return artists_title, artists_tags, title

# -------------------------------------------------
def prompt_manual_metadata(prefilled: dict) -> dict:
    print("\nMetadata not found or incomplete. Please fill in manually.")
    print("(Press Enter to keep the prefilled value, or type a new one)\n")

    fields = {
        "title":  "Title",
        "artist": "Artist",
        "album":  "Album",
        "year":   "Year",
        "genre":  "Genre",
        "cover_url": "Cover URL"
    }

    result = {}

    for key, label in fields.items():
        prefill = prefilled.get(key, "")
        prompt = f"  {label} [{prefill}]: " if prefill else f"  {label}: "
        user_input = input(prompt).strip()
        result[key] = user_input if user_input else prefill

    return result

def manual_metadata_from_file_with_fallback(filepath: str) -> dict:
    meta = {}
    audio = ID3(filepath)

    meta["title"] = audio.get("TIT2").text[0] if audio.get("TIT2") else None
    meta["artist"] = audio.get("TPE1").text[0] if audio.get("TPE1") else None
    meta["album"] = audio.get("TALB").text[0] if audio.get("TALB") else None
    meta["genre"] = audio.get("TCON").text[0] if audio.get("TCON") else None
    meta["year"] = audio.get("TDRC").text[0] if audio.get("TDRC") else None

    meta["playlists"] = read_playlists(audio)

    # --- If nothing useful ---
    if not meta.get("title") or not meta.get("artist"):
        print(f"✗ No metadata found in file: {filepath}")
        meta["title"] = meta.get("title") or input("Title: ")
        meta["artist"] = meta.get("artist") or input("Artist: ")
        return prompt_manual_metadata(meta)

    required = ["title", "artist", "album", "year", "genre"]
    missing = [f for f in required if not meta.get(f)]

    # --- Missing fields ---
    if missing:
        print(f"⚠ Metadata incomplete. Missing: {', '.join(missing)}")
        return prompt_manual_metadata(meta)

    # --- Playlists input (fallback if not present) ---
    if not meta.get("playlists"):
        meta["playlists"] = input(
            "What playlists the music should be in? (space-separated): "
        ).split()

    return meta

def get_metadata_with_fallback(artist: str, title: str) -> dict:
    meta = get_itunes_metadata(artist, title)

    required = ["title", "artist", "album", "year", "genre", "cover_url"]
    missing = [f for f in required if not meta.get(f)]

    if not meta:
        print(f"✗ No metadata found for: {artist} - {title}")
        meta = {"title": title, "artist": artist}  # prefill what we already know
        return prompt_manual_metadata(meta)

    if missing:
        print(f"⚠ Metadata incomplete. Missing: {', '.join(missing)}")
        return prompt_manual_metadata(meta)
    
    print(f"  Found: {meta['artist']} - {meta['title']} ({meta['year']})")
    confirm = input("  Is this correct? [Y/n/m]: ").strip().lower()
    if confirm == "n":
        artist = input("Artist: ")
        title = input("Title: ")
        return get_metadata_with_fallback(title, artist)
    elif confirm == "m":
        return prompt_manual_metadata(meta)

    meta["playlists"] = input("What playlists the music should be in? (space-separated) ").split()

    return meta

def get_artist_from_mp3(file_path: str) -> str:
    try:
        audio = ID3(file_path)
        return str(audio["TPE1"])  # TPE1 = artist tag
    except Exception:
        return ""
    
def safe_filename(name: str) -> str:
    for char in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(char, "")
    return name.strip()

# ------------------------------------------------------------------
def update_metadata(
    file_path: str,
    title: str,
    artist: str,
    album: str,
    year: str,
    genre: str,
    cover: str,
    playlists: list
):
    audio = ID3(file_path)

    audio["TIT2"] = TIT2(encoding=3, text=title)
    audio["TPE1"] = TPE1(encoding=3, text=artist)
    audio["TALB"] = TALB(encoding=3, text=album)
    audio["TDRC"] = TDRC(encoding=3, text=[year])
    audio["TCON"] = TCON(encoding=3, text=genre)

    if cover != "":
        with open(cover, "rb") as img:
            audio["APIC"] = APIC(
        	encoding=3,
        	mime="image/jpeg",
        	type=3,
        	desc="Cover",
        	data=img.read(),
    	)
        
    if playlists != "":
        change_playlists(audio, playlists)
    
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

# --------------------------------------------------------------------
def download_music(url: str):
    yt_title = get_youtube_title(url)

    a_title, a_tags, title = parse_artists(yt_title)

    print(f"Title -> {title}\nArtists -> {a_title}")
    print("(Press Enter to keep the prefilled value, or type a new one)")

    ans = input()

    if ans == "y" or ans == "":
        pass
    else:
        t = input(f"Title [{title}]: ")
        if t: 
            title = t
        t = input(f"Artist in title [{a_title}]: ")
        if t: 
            a_title = t        
        t = input(f"Artist tags [{a_tags}]: ")
        if t: 
            a_tags = t
    
    metadata = get_metadata_with_fallback(a_title, title)
    
    saveName = a_title + " - " + title
    
    download_image(metadata["cover_url"], f"cover/{saveName}.jpg")
    download_audio(saveName, url, BASE_DIR / "output")

    # todo update a_tags with metadata["artist"]
    update_metadata(BASE_DIR / "output" / (saveName + ".mp3"), 
                    title, 
                    a_tags, 
                    metadata["album"], 
                    metadata["year"], 
                    metadata["genre"], 
                    BASE_DIR / f"cover/{saveName}.jpg",
                    metadata["playlists"])

def update_metadata_file(file_path: str):
    filename = os.path.splitext(os.path.basename(file_path))[0]
    name = filename
    music_dir = os.path.dirname(file_path)

    cmd = input(f"Update the file [{filename}] with metadata from internet? [Y/n] ")

    if cmd == "n":
        meta = manual_metadata_from_file_with_fallback(file_path)
        update_metadata(
            file_path=file_path,
            title=meta.get("title", "XXX"),
            artist=meta.get("artist", "YYY"),
            album=meta.get("album", ""),
            year=meta.get("year", ""),
            genre=meta.get("genre", ""),
            cover="",
            playlists=meta.get("playlists", "")
        )
        
        new_filename = f"{safe_filename(meta['artist'])} - {safe_filename(meta['title'])}.mp3"
        new_file_path = os.path.join(music_dir, new_filename)
        os.rename(file_path, new_file_path)
        print(f"  ✓ Updated: {meta.get('artist')} - {meta.get('title')}\n")
    else:
        # try to parse "Artist - Title" from filename
        if " - " in name:
            artist, title = name.split(" - ", 1)
        elif " : " in name:
            artist, title = name.split(" : ", 1)
        else:
            artist, title = get_artist_from_mp3(file_path), name
            if(artist == ""):
                print("Title: ", title)
                artist = input("Artist: ")

        print(f"Processing: {filename}")

        meta = get_metadata_with_fallback(artist.strip(), title.strip())

        download_image(meta["cover_url"], f"cover/{safe_filename(meta['artist'])} - {safe_filename(meta['title'])}.jpg")

        # update the file
        update_metadata(
            file_path=file_path,
            title=meta.get("title", title),
            artist=meta.get("artist", artist),
            album=meta.get("album", ""),
            year=meta.get("year", ""),
            genre=meta.get("genre", ""),
            cover=f"cover/{safe_filename(meta['artist'])} - {safe_filename(meta['title'])}.jpg",
            playlists=meta.get("playlists", "")
        )

        new_filename = f"{safe_filename(meta['artist'])} - {safe_filename(meta['title'])}.mp3"
        new_file_path = os.path.join(music_dir, new_filename)
        os.rename(file_path, new_file_path)
        print(f"  ✓ Updated: {meta.get('artist')} - {meta.get('title')}\n")

def update_all_metadata(music_dir: str):
    mp3_files = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]

    print(f"Found {len(mp3_files)} mp3 files in {music_dir}\n")

    for filename in mp3_files:
        update_metadata_file(music_dir + "\\" + filename)

    print("Done. All files updated.")

def read_all_metadata(music_dir: str, condition: bool):
    mp3_files = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]

    print(f"Found {len(mp3_files)} mp3 files in {music_dir}\n")

    for filename in mp3_files:
        read_metadata(music_dir + "\\" + filename)
        print("---------------------------------------------------------------")

    print("Done. All files read.")


# --------------------------------------------------------------------
print("-d to download\n-u to update (-a for all files)\n-r to read metadata (-a for all files)\n-cp to create playlists\n-sp to set playlists (-ep for empty playlists)")

cmd = "-"
rep = input("One type of operation? [Y/n] ") != 'n'

if rep:
    cmd = input("Working with: ")

    if(cmd == "-d"):
        url = input("URL: ")
        while url != "exit" and url != "quit":
            download_music(url)
            print("-------------------------- Successs! --------------------------")
            url = input("URL: ")
    elif(cmd == "-r"):
        dir = input("File path: ")
        while dir != "exit" and dir != "quit":
            read_metadata(dir)
            print("---------------------------------------------------------------")
            dir = input("File path: ")
    elif(cmd == "-r -a"):
        dir = input("Directory: ")
        while dir != "exit" and dir != "quit":
            read_all_metadata(dir)
            print("-------------------------- Successs! --------------------------")
            dir = input("Directory: ")
    elif(cmd == "-sp -ep"):
        dir = input("Directory: ")
        while dir != "exit" and dir != "quit":
            set_empty_playlists(dir)
            print("-------------------------- Successs! --------------------------")
            dir = input("Directory: ")
    elif(cmd == "-u"):
        dir = input("File path: ")
        while dir != "exit" and dir != "quit":
            update_metadata_file(dir)
            print("-------------------------- Successs! --------------------------")
            dir = input("File path: ")
    elif(cmd == "-u -a"):
        dir = input("Directory: ")
        while dir != "exit" and dir != "quit":
            update_all_metadata(dir)
            print("-------------------------- Successs! --------------------------")
            dir = input("Directory: ")
    elif(cmd == "-cp"):
        playlist_name = input("Playlist name: ")
        while playlist_name != "exit" and playlist_name != "quit":
            dir = input("Music directory: ")
            create_playlist(playlist_name=playlist_name, music_dir=dir)
            print("-------------------------- Successs! --------------------------")
            playlist_name = input("Playlist name: ")
    elif(cmd == "-sp"):
        dir = input("Music directory: ")
        while dir != "exit" and dir != "quit":
            set_playlists(dir)
            print("-------------------------- Successs! --------------------------")
            dir = input("Music directory: ")
else:
    cmd = input("Operation: ")
    while cmd != "quit" and cmd != "exit":
        if(cmd == "-d"):
            url = input("URL: ")
            download_music(url)
            print("-------------------------- Successs! --------------------------")
        elif(cmd == "-r"):
            dir = input("File path: ")
            read_metadata(dir)
            print("---------------------------------------------------------------")
        elif(cmd == "-r -a"):
            dir = input("Directory: ")
            read_all_metadata(dir)
            print("-------------------------- Successs! --------------------------")
        elif(cmd == "-sp -ep"):
            dir = input("Directory: ")
            set_empty_playlists(dir)
            print("-------------------------- Successs! --------------------------")
        elif(cmd == "-u"):
            dir = input("File path: ")
            update_metadata_file(dir)
            print("-------------------------- Successs! --------------------------")
        elif(cmd == "-u -a"):
            dir = input("Directory: ")
            update_all_metadata(dir)
            print("-------------------------- Successs! --------------------------")
        elif(cmd == "-cp"):
            playlist_name = input("Playlist name: ")
            dir = input("Music directory: ")
            create_playlist(playlist_name=playlist_name, music_dir=dir)
            print("-------------------------- Successs! --------------------------")
        elif(cmd == "-sp"):
            dir = input("Music directory: ")
            set_playlists(dir)
            print("-------------------------- Successs! --------------------------")