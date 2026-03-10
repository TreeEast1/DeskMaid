"""Configuration management for DeskMaid."""

import json
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".deskmaid"
CONFIG_FILE = CONFIG_DIR / "config.json"
HISTORY_DIR = CONFIG_DIR / "history"
PROFILE_FILE = CONFIG_DIR / "profile.json"

PROVIDER_TEMPLATES = {
    "azure-openai": {
        "api_base": "https://<your-resource>.openai.azure.com",
        "api_version": "2024-12-01-preview",
        "model": "gpt-4o",
    },
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "api_version": "",
        "model": "gpt-4o",
    },
    "custom": {
        "api_base": "http://localhost:8080/v1",
        "api_version": "",
        "model": "gpt-4o",
    },
}


def ensure_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict[str, Any]:
    ensure_dirs()
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def save_config(cfg: dict[str, Any]) -> None:
    ensure_dirs()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def get_desktop_path(cfg: dict[str, Any] | None = None) -> Path:
    if cfg and cfg.get("desktop_path"):
        return Path(cfg["desktop_path"]).expanduser()
    return Path.home() / "Desktop"
