"""Credentials Loader"""

import os
from dataclasses import dataclass
from typing import Optional

import dotenv

dotenv.load_dotenv(dotenv_path=".env")  ## Load enviroment variables.


@dataclass
class EnvLoader:  # pylint:disable=too-many-instance-attributes
    """
    Class for loading environments
    """

    # Bot Info
    DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", default="")

    DATABASE_URL: str = os.getenv("DATABASE_URL", default="")
    APPLICATION_ID: str = os.getenv("APPLICATION_ID", default="")

    OMDB_API_KEY: str = os.getenv("OMDB_API_KEY", default="")

    def __post_init__(self) -> None:
        """
        Post init method
        """
        assert self.DISCORD_BOT_TOKEN, "DISCORD_BOT_TOKEN is not set"
        assert self.DATABASE_URL, "DATABASE_URL is not set"
        assert self.APPLICATION_ID, "APPLICATION_ID is not set"
        assert self.OMDB_API_KEY, "OMDB_API_KEY is not set"
