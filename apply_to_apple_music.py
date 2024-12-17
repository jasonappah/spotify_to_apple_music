import requests
from sqlmodel import Session
from db import Song, engine
from dotenv import load_dotenv
import os
load_dotenv()

ITUNES_STOREFRONT = "US"

def get_many_apple_music_catalog_songs_by_isrc(isrcs: list[str]):
  # max 25 at a time
  url = f"https://api.music.apple.com/v1/catalog/{ITUNES_STOREFRONT}/songs"
  params = {
    "filter[isrc]": ",".join(isrcs),
  }
  headers = {
    "Authorization": f"Bearer {os.getenv('APPLE_DEVELOPER_TOKEN')}",
    "Music-User-Token": os.getenv('APPLE_MUSIC_USER_TOKEN'),
  }
  
  res = requests.get(url, params=params, headers=headers)
  
  res.raise_for_status()
  
  return res.text
  return res.json()
  
with Session(engine) as session:
  songs = session.query(Song).all()
  
  song_chunks = [
      songs[i : i + 25] for i in range(0, len(songs), 25)
  ]
  
  
  for chunk in song_chunks:
    catalog = get_many_apple_music_catalog_songs_by_isrc([song.isrc for song in chunk])
    print(catalog)
    break