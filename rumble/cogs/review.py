"""
This module contains the Review cog for the RumbleReviewsBot.
"""

import datetime
import logging as logger
from typing import Any, List, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from rumble.__main__ import RumbleReviewsBot
from rumble.models.omdb import OmdbMovie, OmdbSearch


class ReviewSelect(discord.ui.Select):  # type: ignore
    """A class to represent a select menu for reviewing a movie."""

    def __init__(self, bot: RumbleReviewsBot, movie_id: str, movie_name: str) -> None:
        """Initialize the ReviewSelect class."""
        self.bot = bot
        self.movie_id = movie_id
        self.movie_name = movie_name

        options = [
            discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 11)
        ]

        super().__init__(
            placeholder="Rate the movie", min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        """Callback for the select menu."""
        score = int(self.values[0])
        user = interaction.user
        guild_id = interaction.guild.id  # type: ignore
        user_id = user.id
        user_name = user.display_name
        review_time = datetime.datetime.utcnow()

        async with self.bot.pg_pool.acquire() as conn:  # type: ignore
            await conn.execute(  # type: ignore
                """
                INSERT INTO movie_reviews (guild_id, user_id, user_name, movie_id, movie_name, review_score, review_time)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (guild_id, user_id, movie_id) DO UPDATE
                SET review_score = EXCLUDED.review_score, review_time = EXCLUDED.review_time
                """,
                guild_id,
                user_id,
                user_name,
                self.movie_id,
                self.movie_name,
                score,
                review_time,
            )

        await interaction.response.send_message(
            f"Thank you for your review of {score}/10!", ephemeral=True
        )


class ReviewView(discord.ui.View):
    """A class to represent a view for reviewing a movie."""

    def __init__(self, bot: RumbleReviewsBot, movie_id: str, movie_name: str) -> None:
        """Initialize the ReviewView class."""
        super().__init__(timeout=None)
        self.add_item(ReviewSelect(bot, movie_id, movie_name))


class Review(commands.Cog):
    """A class to represent the Review cog."""

    def __init__(self, bot: RumbleReviewsBot) -> None:
        """Initialize the Review cog."""
        self.bot = bot

    async def fetch_movie_imdb_data(self, query: str) -> Optional[List[dict[str, Any]]]:
        """
        Fetch movie data from the OMDB API.

        Args:
            query (str): The query to search for.

        Returns:
            Optional[List[dict[str, Any]]]: The search results from the OMDB API.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://www.omdbapi.com/?s={query}&apikey={self.bot.env_loader.OMDB_API_KEY}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["Response"] == "True":
                        return data["Search"]
                return None

    async def fetch_movie_imdb_data_by_imdb_id(
        self, imdb_id: str
    ) -> Optional[dict[str, Any]]:
        """
        Fetch movie data from the OMDB API by IMDB ID.

        Args:
            imdb_id (str): The IMDB ID to search for.

        Returns:
            Optional[dict[str, Any]]: The movie data from the OMDB API.
        """
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://www.omdbapi.com/?i={imdb_id}&apikey={self.bot.env_loader.OMDB_API_KEY}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["Response"] == "True":
                        return data
                return None

    @app_commands.command(name="review", description="Review a movie or tv show.")
    @app_commands.describe(name="Search by the name of the show.")
    async def review(self, interaction: discord.Interaction, *, name: str) -> None:
        """
        Review a movie or tv show.

        Args:
            name (str): The name of the movie or tv show to review.

        Returns:
            None
        """
        imdb_id = name
        logger.info("Reviewing IMDB movie: %s", imdb_id)
        await interaction.response.defer()

        imdb_data = await self.fetch_movie_imdb_data_by_imdb_id(imdb_id)

        if not imdb_data:
            await interaction.followup.send("Movie not found.")
            return

        movie_data = OmdbMovie.from_dict(imdb_data)
        movie_name = movie_data.title

        embed = discord.Embed(
            title=f"Review: {movie_data.title}",
            description=f"{movie_data.plot[:200]}",
            color=discord.Color.green(),
        )
        embed.set_thumbnail(url=movie_data.poster)
        embed.add_field(name="Actors", value=movie_data.actors)
        embed.add_field(name="Genre", value=movie_data.genre)
        embed.add_field(name="Released", value=movie_data.released)
        embed.add_field(name="Runtime", value=movie_data.runtime)
        embed.add_field(name="IMDB Rating", value=movie_data.imdb_rating)
        embed.add_field(name="IMDB Votes", value=movie_data.imdb_votes)
        embed.add_field(name="Box Office", value=movie_data.box_office)

        view = ReviewView(self.bot, imdb_id, movie_name)
        await interaction.followup.send(embed=embed, view=view)

    @review.autocomplete("name")
    async def play_autocomplete(
        self, _: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """
        Autocomplete for the review command.

        Args:
            interaction (discord.Interaction): The interaction.
            current (str): The current string.

        Returns:
            List[app_commands.Choice[str]]: The list of choices.
        """
        limit: int = 5

        if current.strip() == "":
            return [
                app_commands.Choice(
                    name="Start typing in the name of your movie/show!",
                    value="",
                ),
            ]

        query_searched = await self.fetch_movie_imdb_data(current.lower())

        if query_searched is None:
            return [
                app_commands.Choice(
                    name="No results found, write a movie/show that exists in IMDB",
                    value="",
                )
            ]

        formatted_search_results: List[OmdbSearch] = [
            OmdbSearch.from_dict(x) for x in query_searched
        ]

        return [
            app_commands.Choice(
                name=f"{result.title} - ({result.year})", value=result.imdb_id
            )
            for result in formatted_search_results[:limit]
        ]

    @app_commands.command(
        name="list_reviews",
        description="List all movie reviews for this server.",
    )
    async def list_reviews(self, interaction: discord.Interaction) -> None:
        """
        List all movie reviews for this server.

        Args:
            interaction (discord.Interaction): The interaction.

        Returns:
            None
        """
        guild_id = interaction.guild.id  # type: ignore
        async with self.bot.pg_pool.acquire() as conn:  # type: ignore

            rows = await conn.fetch(  # type: ignore
                """
                SELECT movie_id, movie_name, AVG(review_score) as avg_score, COUNT(review_score) as num_reviews
                FROM movie_reviews
                WHERE guild_id = $1
                GROUP BY movie_id, movie_name
                ORDER BY avg_score DESC
                """,
                guild_id,
            )

            if not rows:
                await interaction.response.send_message(
                    "No reviews found for this server."
                )
                return

            movies: list[tuple[OmdbMovie, str, str]] = []
            for row in rows:  # type: ignore
                movie_data = await self.fetch_movie_imdb_data_by_imdb_id(
                    row["movie_id"]  # type: ignore
                )
                if movie_data:
                    movie_info = OmdbMovie.from_dict(movie_data)
                    movies.append((movie_info, row["avg_score"], row["num_reviews"]))  # type: ignore

            embed = discord.Embed(
                title="Movies Reviewed in this Server",
                color=discord.Color.blue(),
            )

            for movie, avg_score, num_reviews in movies:
                embed.add_field(
                    name=f"{movie.title} ({movie.year})",
                    value=f"- Average Score: {avg_score:.1f}\n- Reviews: {num_reviews}\n- IMDB Rating: {movie.imdb_rating}",
                    inline=False,
                )

            await interaction.response.send_message(embed=embed)

    @app_commands.command(
        name="get_reviewed_movie_stats",
        description="Get detailed stats of a reviewed movie.",
    )
    @app_commands.describe(name="Search for the name of the reviewed movie.")
    async def get_reviewed_movie_stats(
        self, interaction: discord.Interaction, *, name: str
    ) -> None:
        """
        Get detailed stats of a reviewed movie.

        Args:
            name (str): The name of the movie to search for.
        """
        guild_id = interaction.guild.id  # type: ignore

        async with self.bot.pg_pool.acquire() as conn:  # type: ignore
            rows = await conn.fetch(  # type: ignore
                """
                SELECT user_id, user_name, review_score, review_time, movie_id, movie_name
                FROM movie_reviews
                WHERE guild_id = $1 AND movie_name ILIKE $2
                ORDER BY review_time ASC
                """,
                guild_id,
                name,
            )

            if not rows:
                await interaction.response.send_message(
                    "No reviews found for this movie in this server."
                )
                return

            imdb_id: str = rows[0]["movie_id"]  # type: ignore

            imdb_data = await self.fetch_movie_imdb_data_by_imdb_id(imdb_id)  # type: ignore
            if not imdb_data:
                await interaction.response.send_message("Movie not found.")
                return

            movie_data = OmdbMovie.from_dict(imdb_data)

            embed = discord.Embed(
                title=f"Reviews for {movie_data.title} ({movie_data.year})",
                color=discord.Color.blue(),
            )
            embed.set_thumbnail(url=movie_data.poster)

            for row in rows:  # type: ignore
                user = self.bot.get_user(row["user_id"])  # type: ignore
                if user:
                    user_name = user.name
                    user_avatar = (
                        user.avatar.url if user.avatar else user.default_avatar.url
                    )
                else:
                    user_name = row["user_name"]  # type: ignore
                    user_avatar = None

                review_time = row["review_time"].strftime("%Y-%m-%d %H:%M:%S")  # type: ignore
                embed.add_field(
                    name=f"{user_name} ({review_time})",
                    value=f"Score: {row['review_score']}",
                    inline=False,
                )
                if user_avatar:
                    embed.set_thumbnail(url=user_avatar)

            await interaction.response.send_message(embed=embed)

    @get_reviewed_movie_stats.autocomplete("name")
    async def autocomplete_reviewed_movie(
        self, interaction: discord.Interaction, current: str
    ) -> List[app_commands.Choice[str]]:
        """
        Autocomplete for the get_reviewed_movie_stats command.

        Args:
            interaction (discord.Interaction): The interaction.
            current (str): The current string.

        Returns:
            List[app_commands.Choice[str]]: The list of choices.
        """
        guild_id = interaction.guild.id  # type: ignore

        async with self.bot.pg_pool.acquire() as conn:  # type: ignore
            rows = await conn.fetch(  # type: ignore
                """
                SELECT DISTINCT movie_name
                FROM movie_reviews
                WHERE guild_id = $1 AND movie_name ILIKE $2
                LIMIT 5
                """,
                guild_id,
                f"%{current}%",
            )

            if not rows:
                return [
                    app_commands.Choice(
                        name="No matching reviewed movies found.", value=""
                    )
                ]

            choices: list[app_commands.Choice[str]] = [
                app_commands.Choice(name=row["movie_name"], value=row["movie_name"])  # type: ignore
                for row in rows  # type: ignore
            ]

            return choices


async def setup(bot: RumbleReviewsBot) -> None:
    """Add the Review cog to the bot."""
    await bot.add_cog(Review(bot))
