from sqlmodel import SQLModel, Field, Relationship, select, Session
from sqlalchemy import create_engine


class Album(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)

    spotify_album_uri: str = Field(unique=True)
    spotify_album_name: str
    apple_album_id: str | None = Field(
        nullable=True,
    )
    apple_album_name: str | None = Field(nullable=True)
    upc: str | None = Field(nullable=True)

    songs: list["Song"] = Relationship(back_populates="album")


class SongArtistLink(SQLModel, table=True):
    song_id: int = Field(primary_key=True, foreign_key="song.id", default=None)
    artist_id: int = Field(primary_key=True, foreign_key="artist.id", default=None)


class Artist(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)

    spotify_artist_uri: str = Field(unique=True)
    spotify_artist_name: str | None = Field(nullable=True)
    apple_artist_id: str | None = Field(nullable=True)
    apple_artist_name: str | None = Field(nullable=True)

    songs: list["Song"] = Relationship(
        back_populates="artists", link_model=SongArtistLink
    )


class Song(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)

    spotify_track_uri: str = Field(unique=True)
    spotify_track_name: str | None = Field(nullable=True)
    apple_track_id: str | None = Field(nullable=True)
    apple_track_name: str | None = Field(nullable=True)
    isrc: str | None = Field(nullable=True)
    album_id: int | None = Field(nullable=True, foreign_key="album.id")

    album: "Album" = Relationship(back_populates="songs")
    artists: list["Artist"] = Relationship(
        back_populates="songs", link_model=SongArtistLink
    )
    playlist_tracks: list["PlaylistTrack"] = Relationship(back_populates="song")


class Playlist(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)

    apple_playlist_id: str | None = Field(nullable=True, default=None)
    apple_playlist_name: str | None = Field(nullable=True, default=None)
    csv_path: str | None = Field(nullable=True, default=None)

    playlist_tracks: list["PlaylistTrack"] = Relationship(back_populates="playlist")


class PlaylistTrack(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    playlist_id: int = Field(foreign_key="playlist.id", default=None)
    song_id: int = Field(foreign_key="song.id", default=None)
    index: int

    playlist: Playlist = Relationship(back_populates="playlist_tracks")
    song: Song = Relationship(back_populates="playlist_tracks")


class Config(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    apple_music_playlist_folder_id: str | None = Field(nullable=True, default=None)

    @staticmethod
    def get_or_create(session: Session):
        config = session.exec(select(Config).limit(1)).one_or_none()
        if config:
            return config

        config = Config()
        with session.begin_nested():
            session.add(config)
            session.commit()
        return config


engine = create_engine("sqlite:///data/db.sqlite3")
SQLModel.metadata.create_all(engine)
