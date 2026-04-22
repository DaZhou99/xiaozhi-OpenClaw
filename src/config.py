from typing import Union, Dict, Optional
import json
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_ENV_VAR = "XIAOZHI_OPENCLAW_CONFIG"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"

DEFAULT_CONFIG = {
    "MCP_ENDPOINT": "wss://api.xiaozhi.me/mcp/?token=replace-me",
    "OPENCLAW_URL": "http://127.0.0.1:18789",
    "HOOK_TOKEN": "replace-me",
    "HOOK_NAME": "XiaoZhi",
    "AGENT_ID": "",
    "SESSION_KEY": "",
    "WAKE_MODE": "now",
    "DELIVER": True,
    "CHANNEL": "last",
    "TO": "",
    "MODEL": "",
    "THINKING": "",
    "TIMEOUT_SECONDS": 120,
    "USE_SOCKS_PROXY": True,
    "LOG_ENABLED": False,
    "LOG_PATH": str(PROJECT_ROOT / "logs" / "bridge_events.jsonl"),
}

ENV_OVERRIDE_MAP = {
    "MCP_ENDPOINT": "MCP_ENDPOINT",
    "OPENCLAW_URL": "OPENCLAW_URL",
    "HOOK_TOKEN": "HOOK_TOKEN",
    "HOOK_NAME": "HOOK_NAME",
    "AGENT_ID": "AGENT_ID",
    "SESSION_KEY": "SESSION_KEY",
    "WAKE_MODE": "WAKE_MODE",
    "CHANNEL": "CHANNEL",
    "TO": "TO",
    "MODEL": "MODEL",
    "THINKING": "THINKING",
    "TIMEOUT_SECONDS": "TIMEOUT_SECONDS",
    "USE_SOCKS_PROXY": "USE_SOCKS_PROXY",
    "LOG_ENABLED": "LOG_ENABLED",
    "LOG_PATH": "LOG_PATH",
}


def get_config_path() -> Path:
    raw_path = os.environ.get(CONFIG_ENV_VAR)
    if not raw_path:
        return DEFAULT_CONFIG_PATH
    return Path(raw_path).expanduser().resolve()


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _coerce_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_config(config: Union[dict, None]) -> dict:
    merged = {**DEFAULT_CONFIG, **(config or {})}
    for key, env_name in ENV_OVERRIDE_MAP.items():
        env_value = os.environ.get(env_name)
        if env_value not in (None, ""):
            merged[key] = env_value

    deliver_env = os.environ.get("DELIVER")
    if deliver_env not in (None, ""):
        merged["DELIVER"] = _coerce_bool(deliver_env)
    else:
        merged["DELIVER"] = _coerce_bool(merged.get("DELIVER", True))

    merged["TIMEOUT_SECONDS"] = _coerce_int(
        merged.get("TIMEOUT_SECONDS"),
        DEFAULT_CONFIG["TIMEOUT_SECONDS"],
    )
    merged["USE_SOCKS_PROXY"] = _coerce_bool(merged.get("USE_SOCKS_PROXY", True))
    merged["LOG_ENABLED"] = _coerce_bool(merged.get("LOG_ENABLED", False))
    return merged


def load_config() -> dict:
    config_path = get_config_path()
    if not config_path.exists():
        return normalize_config({})

    with config_path.open("r", encoding="utf-8") as file:
        loaded = json.load(file)
    return normalize_config(loaded)


def save_config(config: dict) -> Path:
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    normalized = normalize_config(config)
    with config_path.open("w", encoding="utf-8") as file:
        json.dump(normalized, file, ensure_ascii=False, indent=2)
    return config_path


def validate_config(config: dict) -> list[str]:
    errors = []
    if not config.get("MCP_ENDPOINT") or "replace-me" in config["MCP_ENDPOINT"]:
        errors.append("MCP_ENDPOINT 未配置")
    if not config.get("OPENCLAW_URL"):
        errors.append("OPENCLAW_URL 未配置")
    if not config.get("HOOK_TOKEN") or config["HOOK_TOKEN"] == "replace-me":
        errors.append("HOOK_TOKEN 未配置")
    if config.get("WAKE_MODE") not in {"now", "next-heartbeat"}:
        errors.append("WAKE_MODE 只能是 now 或 next-heartbeat")
    if config.get("TIMEOUT_SECONDS", 0) <= 0:
        errors.append("TIMEOUT_SECONDS 必须大于 0")
    return errors
