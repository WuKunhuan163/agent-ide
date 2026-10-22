"""Configuration: the only place allowed to read config.json or the environment."""

from .resolve import Config, resolve

__all__ = ["Config", "resolve"]
