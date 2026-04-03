import os
from mutagen.id3 import ID3
from mutagen.mp3 import MP3

def save_playlist_m3u(directory: str, output_file: str = "playlist.m3u"):
    mp3_files = sorted([f for f in os.listdir(directory) if f.endswith(".mp3")])

    with open(output_file, "w", encoding="utf-8") as playlist:
        for filename in mp3_files:
            playlist.write(f"../Library/{filename}\n")

    print(f"✓ Playlist saved to {output_file} ({len(mp3_files)} tracks)")


dir = input("Directory: ")
output = input("Output: ")

save_playlist_m3u(dir, output)