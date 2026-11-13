"""The error raised for a config.toml that cannot be used."""

from __future__ import annotations



class ConfigError(ValueError):
    """A config.toml that cannot be used. The message names the offending key."""
