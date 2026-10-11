"""Effective configuration: engine defaults, instance pulse.config.yaml, PULSE__ env overrides."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import ValidationError
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from pulseai.models.config import PulseConfig
from pulseai.registry.loader import RegistryError, load_registry
from pulseai.schemas import validate_document

CONFIG_REGISTRY = "config"
CONFIG_SCHEMA = "config.schema.json"
ENV_PREFIX = "PULSE__"
ENV_DELIMITER = "__"


class ConfigError(Exception):
    """The configuration cannot be loaded or is invalid."""


class PulseSettings(BaseSettings, PulseConfig):  # pyright: ignore[reportIncompatibleVariableOverride]
    """PulseConfig whose values can be overridden with PULSE__SECTION__KEY environment variables."""

    model_config = SettingsConfigDict(
        env_prefix=ENV_PREFIX, env_nested_delimiter=ENV_DELIMITER, extra="forbid"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (env_settings, init_settings)


def load_config(instance_dir: Path | None = None) -> PulseConfig:
    try:
        merged = load_registry(CONFIG_REGISTRY, instance_dir).data
    except RegistryError as exc:
        raise ConfigError(str(exc)) from None
    try:
        settings = PulseSettings(**merged)
    except ValidationError as exc:
        lines = [
            f"  - {'/'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in exc.errors()
        ]
        msg = "environment overrides are invalid\n" + "\n".join(lines)
        raise ConfigError(msg) from None
    # exclude_unset: optional fields the generated model defaults to None must not become explicit
    # nulls (the schema forbids them), while provided nulls such as site.url stay.
    effective = settings.model_dump(mode="json", exclude_unset=True)
    errors = validate_document(effective, CONFIG_SCHEMA)
    if errors:
        msg = "configuration is invalid after environment overrides\n" + "\n".join(
            f"  - {e}" for e in errors
        )
        raise ConfigError(msg)
    return PulseConfig.model_validate(effective)


def unknown_env_overrides(environ: Mapping[str, str] | None = None) -> list[str]:
    """PULSE__ variables whose first segment is not a top-level config key (likely typos)."""
    env = os.environ if environ is None else environ
    known = set(PulseConfig.model_fields)
    unknown = [
        name
        for name in env
        if name.startswith(ENV_PREFIX)
        and name.removeprefix(ENV_PREFIX).split(ENV_DELIMITER, 1)[0].lower() not in known
    ]
    return sorted(unknown)
