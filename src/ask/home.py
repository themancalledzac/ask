"""Locates the ask home directory, which holds config.toml and index.db."""

import os
from pathlib import Path


def ask_home() -> Path:
    """Return $ASK_HOME, else ~/.config/ask, creating it if missing."""
    env = os.environ.get("ASK_HOME")
    home = Path(env) if env else Path.home() / ".config" / "ask"
    home.mkdir(parents=True, exist_ok=True)
    return home
