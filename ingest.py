import requests
from sqlmodel import Session
import csv
import os
import dotenv
from db import engine, Artist, Album, Song, Playlist, PlaylistTrack
from sqlalchemy.dialects.sqlite import insert

dotenv.load_dotenv()


def import_spotify_csvs():
    csv_files = [f for f in os.listdir("data/spotify") if f.endswith(".csv")]

    for csv_file in csv_files:
        csv_path = f"data/spotify/{csv_file}"
        with open(csv_path, "r") as file:
            with Session(engine) as session:
                reader = csv.DictReader(file)
                playlist = Playlist(csv_path=csv_path, apple_playlist_id=None)
                session.add(playlist)
                session.commit()

                for row in reader:
                    artist_uris = row["Artist URI(s)"].split(", ")
                    artist_name = (
                        row["Artist Name(s)"] if len(artist_uris) == 1 else None
                    )

                    artists = [
                        Artist(
                            spotify_artist_uri=artist_uri,
                            spotify_artist_name=artist_name,
                            apple_artist_id=None,
                            apple_artist_name=None,
                        )
                        for artist_uri in artist_uris
                    ]
                    session.add_all(artists)
                    session.commit()

                    album = get_or_create_spotify_album(
                        row["Album URI"], row["Album Name"], session
                    )
                    song = Song(
                        spotify_track_uri=row["Track URI"],
                        spotify_track_name=row["Track Name"],
                        apple_track_id=None,
                        apple_track_name=None,
                        artists=artists,
                        isrc=row["ISRC"].upper(),
                        album_id=album.id,
                    )
                    session.add(song)
                    session.commit()

                    playlist.playlist_tracks.append(
                        PlaylistTrack(
                            playlist_id=playlist.id,
                            song_id=song.id,
                            index=len(playlist.playlist_tracks),
                        )
                    )

                session.commit()


def get_spotify_access_token():
    return requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.getenv("SPOTIFY_CLIENT_ID"),
            "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
        },
    ).json()["access_token"]


def fill_missing_spotify_artist_names():
    with Session(engine) as session:
        artists = session.query(Artist).filter(Artist.spotify_artist_name == None).all()
        spotify_artist_uri_to_db_artist = {
            artist.spotify_artist_uri: artist for artist in artists
        }
        spotify_artist_uris: list[str] = [
            artist.spotify_artist_uri for artist in artists
        ]
        chunked_spotify_artist_uris = [
            spotify_artist_uris[i : i + 50]
            for i in range(0, len(spotify_artist_uris), 50)
        ]

        for chunk in chunked_spotify_artist_uris:
            spotify_artists = get_many_spotify_artists(chunk)

            for spotify_artist in spotify_artists["artists"]:
                db_artist = spotify_artist_uri_to_db_artist[
                    f"spotify:artist:{spotify_artist['id']}"
                ]
                db_artist.spotify_artist_name = spotify_artist["name"]
            session.commit()


def get_many_spotify_albums(album_uris: list[str]):
    # max 20
    spotify_token = get_spotify_access_token()
    res = requests.get(
        f"https://api.spotify.com/v1/albums/?ids={','.join([i.split(':')[2] for i in album_uris])}",
        headers={"Authorization": f"Bearer {spotify_token}"},
    )

    json = res.json()

    return json


def get_many_spotify_artists(artist_uris: list[str]):
    # max 50
    spotify_token = get_spotify_access_token()
    res = requests.get(
        f"https://api.spotify.com/v1/artists/?ids={','.join([i.split(':')[2] for i in artist_uris])}",
        headers={"Authorization": f"Bearer {spotify_token}"},
    )

    json = res.json()

    return json


def get_or_create_spotify_album(album_uri: str, album_name: str, session: Session):
    album: Album | None = (
        session.query(Album).filter(Album.spotify_album_uri == album_uri).first()
    )
    if album:
        return album

    album = Album(
        spotify_album_uri=album_uri,
        spotify_album_name=album_name,
        apple_album_id=None,
        apple_album_name=None,
        upc=None,
    )
    session.add(album)
    session.commit()
    return album


def fill_missing_spotify_album_upcs():
    with Session(engine) as session:
        albums = session.query(Album).filter(Album.upc == None).all()

        album_uris: list[str] = [album.spotify_album_uri for album in albums]
        album_uris_chunks = [
            album_uris[i : i + 20] for i in range(0, len(album_uris), 20)
        ]

        for i, chunk in enumerate(album_uris_chunks):
            spotify_albums = get_many_spotify_albums(chunk)

            for k, spotify_album in enumerate(spotify_albums["albums"]):
                album = albums[i * 20 + k]

                external_ids = (
                    spotify_album["external_ids"]
                    if "external_ids" in spotify_album
                    else {}
                )
                if not external_ids:
                    continue
                if "upc" not in external_ids:
                    continue
                if not external_ids["upc"]:
                    continue
                album.upc = external_ids["upc"]
            session.commit()


import_spotify_csvs()
fill_missing_spotify_artist_names()
fill_missing_spotify_album_upcs()
