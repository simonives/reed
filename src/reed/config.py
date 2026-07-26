# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING, Any

from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from .graph import GraphService


class Settings(BaseSettings):
    api_key: str = ""
    data_path: str = "/data/reed.kuzu"
    frontend_path: str = "/app/frontend/dist"
    poll_default_interval: int = 60  # minutes
    derived_edge_interval: int = 360  # minutes (6 hours)
    topic_backend: str = "yake"  # yake | spacy | llm
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_prefix": "REED_"}


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Runtime-editable config (PATCH /api/v1/config), stored in Kuzu. Environment
# settings provide the defaults; stored values override them.

# The reading font stacks the Appearance UI offers. The stored config value is
# the raw CSS stack (consistent with the other appearance vars), validated
# against this allowlist so only known-safe stacks reach :root.
FONT_FAMILY_STACKS = frozenset(
    {
        "system-ui, sans-serif",
        "'Segoe UI', Roboto, system-ui, sans-serif",
        "Georgia, 'Times New Roman', serif",
        "ui-monospace, 'SF Mono', Menlo, monospace",
    }
)

CONFIG_DEFAULTS = {
    "reader_mode_enabled": True,
    "default_theme": "system",
    "items_per_page": 50,
    "mark_read_on_open": True,
    "accent_color": "#3b82f6",
    "font_size_base": 16,
    "reading_width": 760,
    "line_height": 1.65,
    "font_family_reading": "system-ui, sans-serif",
    "similarity_window_days": 90,
    "similarity_score_threshold": 0.1,
}


def effective_config(graph: GraphService) -> dict[str, Any]:
    stored = graph.get_config_values()
    defaults: dict[str, Any] = {
        "default_poll_interval_minutes": get_settings().poll_default_interval,
        **CONFIG_DEFAULTS,
    }
    return {key: stored.get(key, default) for key, default in defaults.items()}


def effective_feed_settings(feed: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Resolve per-feed overrides against global config.

    The poller and the API serialiser both use this, so what the API reports
    as effective_* is always what the poller actually applies.
    """
    interval = feed.get("poll_interval_minutes")
    reader_mode = feed.get("reader_mode_enabled")
    return {
        "poll_interval_minutes": (
            int(str(interval))
            if interval is not None
            else int(config["default_poll_interval_minutes"])
        ),
        "reader_mode_enabled": (
            bool(reader_mode) if reader_mode is not None else bool(config["reader_mode_enabled"])
        ),
    }
