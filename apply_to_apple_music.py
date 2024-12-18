import requests
from sqlmodel import Session, select
from sqlalchemy.orm import selectinload
from db import Song, engine, Playlist, Config, PlaylistTrack
from datetime import datetime
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


def link_songs_to_apple_music_by_isrc():
    with Session(engine) as session:
        songs = session.exec(select(Song).where(Song.apple_track_id == None)).all()
        isrc_to_db_song = {song.isrc: song for song in songs}

        song_chunks = [songs[i : i + 25] for i in range(0, len(songs), 25)]
        seen_isrcs: set[str] = set()

        for chunk in song_chunks:
            catalog = get_many_apple_music_catalog_songs_by_isrc(
                [song.isrc for song in chunk if song.isrc]
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
                        f"Multiple songs on Apple Music have ISRC {catalog_song['attributes']['isrc']}"
                    )

            session.commit()


def _create_apple_music_playlist_folder(session: Session, name: str) -> str:
    res = requests.post(
        "https://api.music.apple.com/v1/me/library/playlist-folders",
        json={"attributes": {"name": name}},
        headers=APPLE_MUSIC_REQUEST_HEADERS,
    )
    res.raise_for_status()
    json = res.json()
    return json["data"][0]["id"]


def _get_root_library_playlist_folder_id(session: Session):
    config = Config.get_or_create(session)
    if config.apple_music_playlist_folder_id:
        return config.apple_music_playlist_folder_id

    id = _create_apple_music_playlist_folder(session, "Spotify converted playlists")
    config.apple_music_playlist_folder_id = id
    session.commit()
    return id


def create_apple_music_playlist(
    playlist_name: str,
    playlist_description: str,
    playlist_folder_id: str,
    apple_music_song_ids: list[str] = [],
):
    playlist = {
        "attributes": {
            "name": playlist_name,
            "description": playlist_description,
            "isPublic": False,
        },
        "relationships": {
            "tracks": {
                "data": [{"id": song, "type": "songs"} for song in apple_music_song_ids]
            },
            "parent": {
                "data": [
                    {
                        "id": playlist_folder_id,
                        "type": "library-playlist-folders",
                    }
                ]
            },
        },
    }

    res = requests.post(
        "https://amp-api.music.apple.com/v1/me/library/playlists",
        json=playlist,
        headers=APPLE_MUSIC_REQUEST_HEADERS,
        params={"art[url]": "f", "l": "en-US"},
    )

    try:
        res.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print(res.text)
        raise e
    json = res.json()
    created_playlist_id: str = json["data"][0]["id"]

    return created_playlist_id


def create_apple_music_playlist_from_db_playlist(
    session: Session, playlist: Playlist, playlist_folder_id: str
):
    date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    song_ids = [
        track.song.apple_track_id
        for track in sorted(playlist.playlist_tracks, key=lambda x: x.index)
    ]
    playlist_name = (
        playlist.csv_path.split("/")[-1].replace("_", " ").replace(".csv", "").title()
        if playlist.csv_path
        else date
    )
    apple_playlist_id = create_apple_music_playlist(
        playlist_name,
        f"Created by Spotify to Apple Music import script on {date}",
        playlist_folder_id,
        [si for si in song_ids if si],
    )
    with session.begin_nested():
        playlist.apple_playlist_name = playlist_name
        playlist.apple_playlist_id = apple_playlist_id
        session.commit()


def create_apple_music_playlists_from_db_playlist():
    with Session(engine) as session:
        playlist_folder_id = _get_root_library_playlist_folder_id(session)
        playlists = session.exec(
            select(Playlist)
            .options(
                selectinload(Playlist.playlist_tracks).selectinload(PlaylistTrack.song)
            )
            .where(Playlist.apple_playlist_id == None)
        ).all()
        for playlist in playlists:
            create_apple_music_playlist_from_db_playlist(
                session, playlist, playlist_folder_id
            )


link_songs_to_apple_music_by_isrc()
create_apple_music_playlists_from_db_playlist()

# TODO: like all the songs on apple
# TODO: follow all the artists on apple
# TODO: investgate why sometimes create_apple_music_playlist function gets a 500 from apple even though the playlist is created as expected in the music app. returned err on 500: {"errors":[{"id":"<REDACTED_REQ_ID>","title":"Upstream Service Error","detail":"Service failure: Cloud Library","status":"500","code":"50001"}]}
# TODO: maybe one day, semi real-time sync of playlists between platforms would be sick. would definitely need to get my own apple dev account for that tho :/