"""
This is the main file for the bot, it will be used to run the bot.
"""

import asyncio
import logging as logger
import typing

import asyncpg
import discord
from discord.ext import commands

from rumble.credentials.loader import EnvLoader
from rumble.logs.logger import setup_logging
from rumble.utils.cogs_loader import cog_loader, cog_reloader

env_loader = EnvLoader()
setup_logging()


class RumbleReviewsBot(commands.Bot):
    """A class to represent the RumbleReviewsBot."""

    def __init__(self) -> None:
        """Initialize the RumbleReviewsBot."""
        intents = discord.Intents.all()
        intents.message_content = True
        intents.guilds = True
        self.env_loader: EnvLoader = env_loader
        self.pg_pool: asyncpg.Pool | None = None
        command_prefix = "$$$"
        help_command = None
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="Movies/TV Shows",
        )

        super().__init__(
            intents=intents,
            command_prefix=command_prefix,
            help_command=help_command,
            activity=activity,
        )

    async def setup_hook(self) -> None:
        """
        Setup hook, better than putting this in on_ready event.
        """
        logger.info("Setting up the Hook!")
        await self.tree.sync()
        self.pg_pool = await asyncpg.create_pool(  # type: ignore
            self.env_loader.DATABASE_URL
        )

    async def close(self) -> None:
        """
        Close the bot and cleanup
        """
        logger.info("Closing the bot")
        await self.pg_pool.close()  # type: ignore
        await super().close()

    async def on_ready(self) -> None:
        """This event runs when the bot is connected and ready to be used."""
        lines = "~~~" * 30
        logger.info(
            "\n%s\n%s is online in %s servers, and is ready to review movies!\n%s",
            lines,
            self.user,
            len(self.guilds),
            lines,
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """This event runs when the bot joins a new guild."""
        join_msg = (
            "Rumble, your personal Movie rater is here!\n\n"
            "Ready to review some movies? Start by using my slash commands. Simply type ``/review`` followed by a movie title, show title or direct IMDB link to get started.\n\n"
            "Looking for more? Just type ``/`` and choose Rumble, to explore all the commands.\n\n"
        )
        logger.info(
            "Rumble has joined %s, this guild has %s members",
            guild.name,
            guild.member_count,
        )

        if (
            guild.system_channel
            and guild.system_channel.permissions_for(guild.me).send_messages
        ):
            try:
                await guild.system_channel.send(join_msg)
                return
            except discord.HTTPException as exc:
                logger.exception("Failed to send message to system channel")
                raise exc

        all_channels = [
            channel
            for channel in guild.text_channels
            if channel.permissions_for(guild.me).send_messages and not channel.is_nsfw()
        ]
        logger.info("All channels: %s", all_channels)

        if not all_channels:
            try:
                if not isinstance(guild.owner, discord.Member):
                    logger.error("Guild owner is not a member")
                    return

                await guild.owner.send(
                    "Thanks for inviting Rumble.\n\n"
                    f"It seems like I can't send messages in {guild.name}.\n"
                    "Please give permissions to send messages in text channels.\n"
                    "Otherwise i am kinda useless :(\n\n\n"
                    "When i have permission to send messages in text channels, "
                    "try to use the ``/`` and select me to see what i can do :)"
                )
            except discord.Forbidden:
                logger.error("Guild owner has disabled DM's" * 10)
            return

        valid_channels = [
            channel
            for channel in all_channels
            if "general" in channel.name.lower() or "bot" in channel.name.lower()
        ]

        channel_to_send = valid_channels[0] if valid_channels else all_channels[0]
        await channel_to_send.send(join_msg)

    async def on_guild_remove(self, guild: discord.Guild):
        """This event runs when the bot leaves a guild."""
        logger.info(
            "Rumble has left %s, this guild had %s members",
            guild.name,
            guild.member_count,
        )


async def main() -> None:
    """Run the bot."""
    async with RumbleReviewsBot() as bot:
        await cog_loader(client=bot)

        @bot.command(name="sync")
        @commands.guild_only()
        @commands.is_owner()
        async def _(
            ctx: commands.Context,  # type: ignore
            guilds: commands.Greedy[discord.Object],
            spec: typing.Optional[typing.Literal["~", "*", "^"]] = None,
        ) -> None:
            """Sync the tree to the current guild or globally."""
            logger.info("Syncing the tree")
            if not guilds:
                if spec == "~":
                    synced = await bot.tree.sync(guild=ctx.guild)
                elif spec == "*":
                    bot.tree.copy_global_to(guild=ctx.guild)  # type: ignore
                    synced = await bot.tree.sync(guild=ctx.guild)
                elif spec == "^":
                    bot.tree.clear_commands(guild=ctx.guild)
                    await bot.tree.sync(guild=ctx.guild)
                    synced = []
                else:
                    synced = await bot.tree.sync()

                await ctx.send(
                    f"Synced {len(synced)} commands "
                    f"{'globally' if spec is None else 'to the current guild.'}"
                )
                return

            ret = 0
            for guild in guilds:
                try:
                    await bot.tree.sync(guild=guild)
                except discord.HTTPException:
                    pass
                else:
                    ret += 1

            await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

        @bot.command(name="close", alias="shutdown")
        @commands.guild_only()
        @commands.is_owner()
        async def _(
            ctx: commands.Context,  # type: ignore
        ) -> None:
            """Close the bot."""
            await ctx.send("Bot will shutdown soon")
            await bot.close()

        @bot.command(name="reload", alias="cogs")
        @commands.guild_only()
        @commands.is_owner()
        async def _(
            ctx: commands.Context,  # type: ignore
        ) -> None:
            """Reload the cogs."""
            await cog_reloader(client=bot)
            await ctx.send("Cogs are being reloaded")

        await bot.start(token=env_loader.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
