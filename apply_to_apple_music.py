import requests
from sqlmodel import Session
from db import Song, engine
from dotenv import load_dotenv
import os

load_dotenv()

# TODO: set storefront based on user credentials?
ITUNES_STOREFRONT = "US"

APPLE_MUSIC_REQUEST_HEADERS = headers = {
    "Authorization": f"Bearer {os.getenv('APPLE_DEVELOPER_TOKEN')}",
    "Music-User-Token": os.getenv("APPLE_MUSIC_USER_TOKEN"),
    "Origin": "https://music.apple.com",
    "Priority": "u=3, i",
    "Referer": "https://music.apple.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
}


def get_many_apple_music_catalog_songs_by_isrc(isrcs: list[str]):
    # max 25 at a time
    url = f"https://amp-api.music.apple.com/v1/catalog/{ITUNES_STOREFRONT}/songs"
    params = {
        "filter[isrc]": ",".join(isrcs),
    }

    res = requests.get(url, params=params, headers=APPLE_MUSIC_REQUEST_HEADERS)
    res.raise_for_status()

    return res.json()["data"]


with Session(engine) as session:
    songs = session.query(Song).filter(Song.apple_track_id.is_(None)).all()
    isrc_to_db_song = {song.isrc: song for song in songs}

    song_chunks = [songs[i : i + 25] for i in range(0, len(songs), 25)]
    seen_isrcs: set[str] = set()

    for chunk in song_chunks:
        catalog = get_many_apple_music_catalog_songs_by_isrc(
            [song.isrc for song in chunk]
        )
        for catalog_song in catalog:
            isrc = catalog_song["attributes"]["isrc"]
            apple_track_name = catalog_song["attributes"]["name"]
            if isrc not in isrc_to_db_song:
                print(
                    f"ISRC {isrc} not found in db. {apple_track_name} by {catalog_song['attributes']['artistName']}"
                )
                continue
            db_song = isrc_to_db_song[isrc]
            db_song.apple_track_id = catalog_song["id"]
            db_song.apple_track_name = apple_track_name
            if isrc in seen_isrcs:
                print(
                    f"ISRC {catalog_song['attributes']['isrc']} returned multiple songs"
                )

        session.commit()


def create_playlist(
    playlist_name: str,
    playlist_description: str,
    public: bool = False,
    song_ids: list = [],
):
    # TODO: maybe re impl this method using the public api so i don't need to keep track of so many different auth methods lol
    playlist = {
        "attributes": {
            "name": playlist_name,
            "description": playlist_description,
            "isPublic": public,
        },
        "relationships": {
            "tracks": {"data": [{"id": song, "type": "songs"} for song in song_ids]}
        },
    }

    res = requests.post(
        "https://amp-api.music.apple.com/v1/me/library/playlists",
        json=playlist,
        headers=APPLE_MUSIC_REQUEST_HEADERS,
        params={"art[url]": "f", "l": "en-US"},
    )
    )

    created_playlist_id: str = res.json()["data"][0]["id"]

    return created_playlist_id