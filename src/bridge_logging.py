import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union, Union


DEFAULT_LOG_PATH = Path("/tmp/xiaozhi-openclaw-bridge/logs/bridge_events.jsonl")
INTERESTING_KEYWORDS = (
    "session",
    "conversation",
    "request",
    "trace",
    "call",
    "agent",
)


def get_log_path() -> Path:
    env_path = os.environ.get("XIAOZHI_OPENCLAW_LOG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()

    try:
        from config import load_config

        configured = load_config().get("LOG_PATH")
        if configured:
            return Path(configured).expanduser().resolve()
    except Exception:
        pass

    return DEFAULT_LOG_PATH


def is_logging_enabled() -> bool:
    env_value = os.environ.get("XIAOZHI_OPENCLAW_LOG_ENABLED")
    if env_value is not None:
        return env_value.strip().lower() in {"1", "true", "yes", "on"}

    try:
        from config import load_config

        return False
    except Exception:
        return False


def parse_json_maybe(value: Union[str, dict, list, None]) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def extract_interesting_fields(payload: Any) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []

    def walk(value: Any, path: str) -> None:
        if isinstance(value, dict):
            for key, nested in value.items():
                child_path = f"{path}.{key}" if path else str(key)
                lowered = str(key).lower()
                if lowered == "id" or any(token in lowered for token in INTERESTING_KEYWORDS):
                    matches.append({"path": child_path, "value": nested})
                walk(nested, child_path)
        elif isinstance(value, list):
            for index, nested in enumerate(value):
                child_path = f"{path}[{index}]"
                walk(nested, child_path)

    walk(payload, "")
    return matches


def log_event(event_type: str, **data: Any) -> None:
    if not is_logging_enabled():
        return
    log_path = get_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        **data,
    }
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(entry, ensure_ascii=False) + "\n")


def log_json_message(event_type: str, message: Union[str, dict, list]) -> None:
    parsed = parse_json_maybe(message)
    log_event(
        event_type,
        raw=message if isinstance(message, str) else None,
        json=parsed if isinstance(parsed, (dict, list)) else None,
        interesting=extract_interesting_fields(parsed) if isinstance(parsed, (dict, list)) else [],
    )
