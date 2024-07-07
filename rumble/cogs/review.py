from typing import Any
import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from rumble.__main__ import RumbleReviewsBot


class Review(commands.Cog):
    def __init__(self, bot: RumbleReviewsBot) -> None:
        self.bot = bot

    async def fetch_movie_imdb_data(self, query: str) -> Any | None:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"http://www.omdbapi.com/?s={query}&apikey={self.bot.env_loader.OMDB_API_KEY}"
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data["Response"] == "True":
                        return data["Search"][0]
                return None

    @app_commands.command(name="review", description="Review a movie or tv show.")
    async def review(self, interaction: discord.Interaction, name: str) -> None:
        """
        /review
        """
        await interaction.response.defer()
        guild_id = interaction.guild.id
        server_name = interaction.guild.name
        imdb_data = await self.fetch_movie_imdb_data(name)
        if not imdb_data:
            await interaction.followup.send("Movie not found.")
            return

        imdb_id = imdb_data["imdbID"]
        imdb_link = f"https://www.imdb.com/title/{imdb_id}/"
        movie_name = imdb_data["Title"]

        await self.bot.db.movie_reviews.update_one(
            {"guild_id": guild_id, "imdb_id": imdb_id},
            {
                "$set": {
                    "server_name": server_name,
                    "movie_name": movie_name,
                    "imdb_link": imdb_link,
                }
            },
            upsert=True,
        )

        await interaction.followup.send(
            f"Added/Updated review for {movie_name}: {imdb_link}"
        )

    @app_commands.command(
        name="list_reviews",
        description="List all movie reviews for this server.",
    )
    async def list_reviews(self, interaction: discord.Interaction) -> None:
        guild_id = interaction.guild.id
        rows = await self.bot.db.movie_reviews.find({"guild_id": guild_id}).to_list(
            length=None
        )
        if not rows:
            await interaction.response.send_message("No reviews found for this server.")
            return

        response = "\n".join(
            [f"{row['movie_name']}: {row['imdb_link']}" for row in rows]
        )
        await interaction.response.send_message(response)


async def setup(bot: RumbleReviewsBot) -> None:
    """
    Setup the cog.
    """
    await bot.add_cog(Review(bot))
