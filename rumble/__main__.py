import asyncio
import logging as logger
import typing

import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient
from rumble.logs.logger import setup_logging
from rumble.credentials.loader import EnvLoader
from rumble.utils.cogs_loader import cog_loader, cog_reloader

from rich import inspect


env_loader = EnvLoader()
setup_logging()


class RumbleReviewsBot(commands.Bot):
    def __init__(self) -> None:
        # intents = discord.Intents.all()
        intents = discord.Intents.default()
        intents.guilds = True
        self.env_loader: EnvLoader = env_loader

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
        self.mongo_client: typing.Optional[AsyncIOMotorClient] = None

    async def setup_hook(self) -> None:
        """
        Setup hook, better than putting this in on_ready event.
        """
        logger.info("Setting up the Hook!")
        await self.tree.sync()
        self.mongo_client = AsyncIOMotorClient(self.env_loader.mongodb_url)
        inspect(self.mongo_client)

        self.db = self.mongo_client["rumble_reviews"]

    async def close(self) -> None:
        """
        Close the bot and cleanup
        """
        self.mongo_client.close()
        await super().close()

    ### Bot Events
    async def on_ready(self) -> None:
        """This event runs when the bot is connected and ready to be used."""

        ## Create task to connect to the lavalink server.
        lines = "~~~" * 30

        logger.info(
            "\n%s\n%s is online in %s servers, and is ready to review movies!\n%s",
            lines,
            self.user,
            len(self.guilds),
            lines,
        )

    async def on_guild_join(self, guild: discord.Guild) -> None:
        """When Rumble joins a guild it adds that guild and a default server prefix to database"""
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

        # First, try to send message to system channel
        if (
            guild.system_channel
            and guild.system_channel.permissions_for(guild.me).send_messages
        ):
            try:
                await guild.system_channel.send(join_msg)
                return  # If successful, we don't need to do anything else
            except discord.HTTPException as exc:
                logger.exception("Failed to send message to system channel")
                raise exc

        # If we reach here, system channel is not available, let's find a suitable channel
        all_channels = [
            channel
            for channel in guild.text_channels
            if channel.permissions_for(guild.me).send_messages and not channel.is_nsfw()
        ]
        logger.info("All channels: %s", all_channels)

        if not all_channels:  # If there's no valid channels
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
            return  # After sending DM or logging error, exit function

        # If we reach here, there's at least one valid channel
        valid_channels = [
            channel
            for channel in all_channels
            if "general" in channel.name.lower() or "bot" in channel.name.lower()
        ]

        # Pick the first 'valid' channel, or if there's none, the first 'all' channel
        channel_to_send = valid_channels[0] if valid_channels else all_channels[0]
        await channel_to_send.send(join_msg)

    async def on_guild_remove(self, guild: discord.Guild):
        """
        Triggers when the Client leaves the Guild
        """
        logger.info(
            "Rumble has left %s, this guild had %s members",
            guild.name,
            guild.member_count,
        )


async def main():
    """main function"""

    async with RumbleReviewsBot() as bot:
        await cog_loader(client=bot)

        @bot.command(name="sync")
        @commands.guild_only()
        @commands.is_owner()
        async def _sync(
            ctx: commands.Context,
            guilds: commands.Greedy[discord.Object],
            spec: typing.Optional[typing.Literal["~", "*", "^"]] = None,
        ) -> None:
            """
            A normal client.command for syncing app_commands.tree

            Works like:
            !sync -> global sync
            !sync ~ -> sync current guild
            !sync * -> copies all global app commands to current guild and syncs
            !sync ^ -> clears all commands from the current guild target and syncs (removes guild commands)
            !sync id_1 id_2 -> syncs guilds with id 1 and 2
            """
            if not guilds:
                if spec == "~":
                    synced = await ctx.bot.tree.sync(guild=ctx.guild)
                elif spec == "*":
                    ctx.bot.tree.copy_global_to(guild=ctx.guild)
                    synced = await ctx.bot.tree.sync(guild=ctx.guild)
                elif spec == "^":
                    ctx.bot.tree.clear_commands(guild=ctx.guild)
                    await ctx.bot.tree.sync(guild=ctx.guild)
                    synced = []
                else:
                    synced = await ctx.bot.tree.sync()

                await ctx.send(
                    f"Synced {len(synced)} commands "
                    f"{'globally' if spec is None else 'to the current guild.'}"
                )
                return

            ret = 0
            for guild in guilds:
                try:
                    await ctx.bot.tree.sync(guild=guild)
                except discord.HTTPException:
                    pass
                else:
                    ret += 1

            await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")

        @bot.command(name="close", alias="shutdown")
        @commands.guild_only()
        @commands.is_owner()
        async def _close(
            ctx: commands.Context,
        ) -> None:
            """
            Shutdown command for Rumble
            """
            await ctx.send("Bot will shutdown soon")
            await bot.close()

        @bot.command(name="reload", alias="cogs")
        @commands.guild_only()
        @commands.is_owner()
        async def _reload(
            ctx: commands.Context,
        ) -> None:
            """
            reloads cogs for Rumble
            """
            await cog_reloader(client=bot)
            await ctx.send("Cogs are being reloaded")

        await bot.start(token=env_loader.DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
