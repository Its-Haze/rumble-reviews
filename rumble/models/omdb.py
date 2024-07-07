"""
This module contains dataclasses to represent data from the OMDB API.
"""

import typing as t
from dataclasses import dataclass


@dataclass
class OmdbSearch:
    """
    A class to represent a search result from the OMDB API.
    """

    title: str
    year: str
    imdb_id: str
    poster: str
    type: str

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "OmdbSearch":
        """
        Create an instance of OmdbSearch from a dictionary.

        Args:
            data (dict): The dictionary to create the instance from.

        Returns:
            An instance of OmdbSearch.
        """
        return cls(
            title=data["Title"],
            year=data["Year"],
            imdb_id=data["imdbID"],
            poster=data["Poster"],
            type=data["Type"],
        )


@dataclass
class OmdbMovie:
    """
    A class to represent a movie from the OMDB API.
    """

    title: str
    year: str
    rated: str
    released: str
    runtime: str
    genre: str
    director: str
    writer: str
    actors: str
    plot: str

    # metadata
    box_office: str = ""
    poster: str = ""
    imdb_rating: str = ""
    imdb_votes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, t.Any]) -> "OmdbMovie":
        """
        Create an instance of OmdbMovie from a dictionary.

        Args:
            data (dict): The dictionary to create the instance from.

        Returns:
            An instance of OmdbMovie.
        """
        return cls(
            title=data["Title"],
            year=data["Year"],
            rated=data["Rated"],
            released=data["Released"],
            runtime=data["Runtime"],
            genre=data["Genre"],
            director=data["Director"],
            writer=data["Writer"],
            actors=data["Actors"],
            plot=data["Plot"],
            box_office=data.get("BoxOffice", ""),
            poster=data.get("Poster", ""),
            imdb_rating=data.get("imdbRating", ""),
            imdb_votes=data.get("imdbVotes", ""),
        )
