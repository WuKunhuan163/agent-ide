"""Merge the four sources of a value and hand back one validated object.

Precedence (highest first)::

    CLI --set  >  env PDF_READER_<KEY>  >  data/config.json  >  schema default

Every module below ``config`` receives this object and never looks at a file or an
environment variable itself -- that is what makes ``config set`` effective in one
place and makes the whole pipeline testable with an injected config.
"""
from __future__ import annotations

import json
import os
from typing import Any, Iterable, Mapping

from . import store
from .schema import CONSTRAINTS, PARAMS_BY_KEY, PARAMS, Param, suggest


ENV_PREFIX = "PDF_READER_"


class ConfigError(Exception):
    """Raised for an unknown key, an unparsable value, or a violated constraint."""


# --------------------------------------------------------------------------- #
# coercion
# --------------------------------------------------------------------------- #

def env_name(key: str) -> str:
    return ENV_PREFIX + key.upper().replace(".", "_")


def coerce(param: Param, raw: Any) -> Any:
    """Turn a raw string (CLI / env / file) into the declared type."""
    if param.type == "str":
        return str(raw)
    if param.type == "int_or_null":
        if raw is None or (isinstance(raw, str) and raw.strip().lower() in ("", "null", "none")):
            return None
        raw = raw.strip() if isinstance(raw, str) else raw
    if param.type == "ints":
        if isinstance(raw, (list, tuple)):
            items = list(raw)
        else:
            text = str(raw).strip().strip("[]")
            items = [part for part in (chunk.strip() for chunk in text.split(",")) if part]
        try:
            return [int(item) for item in items]
        except (TypeError, ValueError):
            raise ConfigError(f"{param.key}: expected a list of ints, got {raw!r}") from None
    if param.type in ("int", "int_or_null"):
        if isinstance(raw, bool):
            raise ConfigError(f"{param.key}: expected an int, got a bool")
        try:
            return int(str(raw).strip())
        except (TypeError, ValueError):
            raise ConfigError(f"{param.key}: expected an int, got {raw!r}") from None
    if param.type == "float":
        try:
            return float(str(raw).strip())
        except (TypeError, ValueError):
            raise ConfigError(f"{param.key}: expected a float, got {raw!r}") from None
    raise ConfigError(f"{param.key}: unsupported declared type {param.type!r}")


def check_value(param: Param, value: Any) -> None:
    """Bounds are inclusive and, for documented ceilings, the ceiling itself.

    A sequence is checked for order whether or not it declares bounds: the rule that a
    backoff rises is a property of the sequence, and making it conditional on bounds
    meant it never ran at all.
    """
    if value is None:
        return
    if isinstance(value, list):
        if not value:
            raise ConfigError(f"{param.key}: the list is empty")
        if value != sorted(value):
            raise ConfigError(f"{param.key}: values must be non-decreasing")
        if param.bounds is not None:
            low, high = param.bounds
            if any(not (low <= item <= high) for item in value):
                raise ConfigError(f"{param.key}: every item must be within [{low}, {high}]")
        return
    if param.bounds is None:
        return
    low, high = param.bounds
    if not (low <= value <= high):
        raise ConfigError(f"{param.key}: {value} is outside [{low}, {high}]")


def unknown_key(key: str) -> ConfigError:
    hint = ", ".join(list(suggest(key))[:4])
    tail = f" -- did you mean: {hint}" if hint else ""
    return ConfigError(f"unknown parameter {key!r}{tail}")


# --------------------------------------------------------------------------- #
# the resolved object
# --------------------------------------------------------------------------- #

class _Scope:
    """Attribute access over one namespace, e.g. ``cfg.precision.split_page_limit``."""

    def __init__(self, config: "Config", scope: str) -> None:
        object.__setattr__(self, "_config", config)
        object.__setattr__(self, "_scope", scope)

    def __getattr__(self, name: str):
        return self._config.get(f"{self._scope}.{name}")

    def __repr__(self) -> str:
        keys = [p.key for p in PARAMS if p.scope == self._scope]
        return f"<scope {self._scope}: {', '.join(k.split('.')[1] for k in keys)}>"


class Config:
    """Validated values plus where each one came from."""

    def __init__(self, values: Mapping[str, Any], origins: Mapping[str, str]) -> None:
        self._values = dict(values)
        self._origins = dict(origins)

    # -- access ----------------------------------------------------------- #
    def get(self, key: str) -> Any:
        if key not in self._values:
            raise unknown_key(key)
        return self._values[key]

    def origin(self, key: str) -> str:
        return self._origins.get(key, "default")

    def is_overridden(self, key: str) -> bool:
        return self.origin(key) != "default"

    def scope(self, name: str) -> _Scope:
        return _Scope(self, name)

    @property
    def common(self) -> _Scope:
        return self.scope("common")

    @property
    def precision(self) -> _Scope:
        return self.scope("precision")

    @property
    def flash(self) -> _Scope:
        return self.scope("flash")

    def namespace(self, mode_name: str) -> _Scope:
        """The namespace that belongs to a mode -- the hook that removes ``if mode``."""
        return self.scope(mode_name)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)

    def items(self) -> Iterable[tuple[str, Any]]:
        return self._values.items()

    # -- construction ------------------------------------------------------ #
    @classmethod
    def from_sources(
        cls,
        cli_sets: Mapping[str, str] | None = None,
        env: Mapping[str, str] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> "Config":
        cli_sets = dict(cli_sets or {})
        env = dict(os.environ if env is None else env)
        overrides = dict(store.load_overrides() if overrides is None else overrides)

        values: dict[str, Any] = {}
        origins: dict[str, str] = {}
        for param in PARAMS:
            raw, origin = param.default, "default"
            if param.key in overrides:
                raw, origin = overrides[param.key], "config.json"
            env_key = env_name(param.key)
            if env_key in env:
                raw, origin = env[env_key], f"env {env_key}"
            if param.key in cli_sets:
                raw, origin = cli_sets[param.key], "--set"
            values[param.key] = coerce(param, raw)
            origins[param.key] = origin

        for key in list(cli_sets) + [
            k for k in overrides if k not in PARAMS_BY_KEY
        ]:
            if key not in PARAMS_BY_KEY:
                raise unknown_key(key)

        config = cls(values, origins)
        config.validate()
        return config

    def validate(self) -> None:
        for param in PARAMS:
            check_value(param, self._values[param.key])
        for left, op, right in CONSTRAINTS:
            if op != "<=":
                # an operator we do not implement must not pass silently: a constraint
                # that never runs is worse than no constraint at all
                raise ConfigError(f"unsupported constraint operator {op!r} in {left} {op} {right}")
            if self._values[left] is None or self._values[right] is None:
                continue
            if self._values[left] > self._values[right]:
                raise ConfigError(
                    f"constraint violated: {left} ({self._values[left]}) must be {op} "
                    f"{right} ({self._values[right]})"
                )


def resolve(cli_sets: Mapping[str, str] | None = None,
            env: Mapping[str, str] | None = None,
            overrides: Mapping[str, Any] | None = None) -> Config:
    return Config.from_sources(cli_sets=cli_sets, env=env, overrides=overrides)


def parse_set_flag(items: Iterable[str]) -> dict[str, str]:
    """Parse repeated ``--set key=value`` items."""
    out: dict[str, str] = {}
    for item in items or []:
        if "=" in item:
            key, _, value = item.partition("=")
            out[key.strip()] = value.strip()
        else:
            raise ConfigError(f"--set expects KEY=VALUE, got {item!r}")
    return out


def parse_json_value(raw: str) -> Any:
    """Used by the config command to accept JSON for list values."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw
