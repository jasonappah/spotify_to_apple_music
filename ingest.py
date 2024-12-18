import requests
from sqlmodel import Session, select
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

                for row in reader:
                    artist_uris = row["Artist URI(s)"].split(", ")

                    # In the Exportify CSVs, artist names are comma-delimited in one column,
                    # but we can't safely assume that splitting that column on commas will get
                    # you the correct artist names since names can contain commas. Artist URIs
                    # are also comma delmited and have a standard format that doesn't contain
                    # commas, so we split that to determine how many artists are on the track,
                    # then if there's only one artist, we use the name from the CSV. Otherwise,
                    # we just hope the other artists have solo songs elsewhere in the CSV or the
                    # database. Later we backfill artist names from Spotify using the artist URIs.
                    artist_name = (
                        row["Artist Name(s)"] if len(artist_uris) == 1 else None
                    )

                    insert_artists_stmt = insert(Artist).values(
                        [
                            {
                                "spotify_artist_uri": artist_uri,
                                "spotify_artist_name": artist_name,
                                "apple_artist_id": None,
                                "apple_artist_name": None,
                            }
                            for artist_uri in artist_uris
                        ]
                    )

                    if artist_name:
                        insert_artists_stmt = insert_artists_stmt.on_conflict_do_update(
                            index_elements=["spotify_artist_uri"],
                            set_={
                                "spotify_artist_name": artist_name,
                            }
                            if artist_name
                            else {},
                        )
                    else:
                        insert_artists_stmt = insert_artists_stmt.on_conflict_do_update(
                            index_elements=["spotify_artist_uri"],
                            set_={
                                "spotify_artist_uri": insert_artists_stmt.excluded.spotify_artist_uri
                            },
                        )
                    insert_artists_stmt = insert_artists_stmt.returning(Artist)
                    artists = [a for (a,) in session.execute(insert_artists_stmt).all()]
                    assert len(artists) > 0

                    album = get_or_create_spotify_album(
                        row["Album URI"], row["Album Name"], session
                    )

                    insert_song_stmt = (
                        insert(Song)
                        .values(
                            {
                                "spotify_track_uri": row["Track URI"],
                                "spotify_track_name": row["Track Name"],
                                "isrc": row["ISRC"].upper(),
                                "album_id": album.id,
                            }
                        )
                        .on_conflict_do_update(
                            index_elements=["spotify_track_uri"],
                            set_={
                                "spotify_track_name": row["Track Name"],
                            },
                        )
                        .returning(Song)
                    )
                    (song,) = session.execute(insert_song_stmt).one()

                    song.artists = artists
                    playlist.playlist_tracks.append(
                        PlaylistTrack(
                            playlist=playlist,
                            song=song,
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
        artists = session.exec(
            select(Artist).where(Artist.spotify_artist_name == None)
        ).all()
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
    insert_album_stmt = (
        insert(Album)
        .values(
            {
                "spotify_album_uri": album_uri,
                "spotify_album_name": album_name,
            }
        )
        .on_conflict_do_update(
            index_elements=["spotify_album_uri"],
            set_={
                "spotify_album_name": album_name,
            },
        )
        .returning(Album)
    )
    (album,) = session.execute(insert_album_stmt).one()

    return album


def fill_missing_spotify_album_upcs():
    with Session(engine) as session:
        albums = session.exec(select(Album).where(Album.upc == None)).all()

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
