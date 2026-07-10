# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Simon Ives and contributors

from functools import lru_cache

from pydantic_settings import BaseSettings


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
