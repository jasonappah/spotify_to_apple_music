from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import create_engine


class Album(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    
    spotify_album_uri: str = Field(unique=True, sa_column_kwargs=dict(sqlite_on_conflict_unique="REPLACE"))
    spotify_album_name: str
    apple_album_id: str | None = Field(nullable=True, sa_column_kwargs=dict(sqlite_on_conflict_unique="REPLACE", sqlite_on_conflict_not_null="REPLACE"))
    apple_album_name: str | None = Field(nullable=True)
    upc: str | None = Field(nullable=True)

    songs: list["Song"] = Relationship(back_populates="album")


class SongArtistLink(SQLModel, table=True):
    song_id: str = Field(primary_key=True, foreign_key="song.id")
    artist_id: str = Field(primary_key=True, foreign_key="artist.id")


class Artist(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    
    spotify_artist_uri: str = Field(unique=True, sa_column_kwargs=dict(sqlite_on_conflict_unique="REPLACE"))
    spotify_artist_name: str | None = Field(nullable=True)
    apple_artist_id: str | None = Field(nullable=True)
    apple_artist_name: str | None = Field(nullable=True)
    
    songs: list["Song"] = Relationship(back_populates="artists", link_model=SongArtistLink)


class Song(SQLModel, table=True):
    id: int | None = Field(primary_key=True, default=None)
    
    spotify_track_uri: str = Field(unique=True, sa_column_kwargs=dict(sqlite_on_conflict_unique="REPLACE"))
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
    
    apple_playlist_id: str | None = Field(nullable=True)
    apple_playlist_name: str | None = Field(nullable=True)
    csv_path: str | None

    playlist_tracks: list["PlaylistTrack"] = Relationship(back_populates="playlist")


class PlaylistTrack(SQLModel, table=True):
    playlist_id: str = Field(primary_key=True, foreign_key="playlist.id")
    song_id: str = Field(primary_key=True, foreign_key="song.id")
    index: int = Field(primary_key=True)

    playlist: Playlist = Relationship(back_populates="playlist_tracks")
    song: Song = Relationship(back_populates="playlist_tracks")


engine = create_engine("sqlite:///data/db.sqlite3")
SQLModel.metadata.create_all(engine)
