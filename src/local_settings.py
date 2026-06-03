from __future__ import annotations

from pathlib import Path


ENV_FILE_NAME = ".env.local"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    return key.strip(), value.strip().strip('"').strip("'")


def load_local_env(project_root: Path) -> dict[str, str]:
    path = project_root / ENV_FILE_NAME
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(line)
        if parsed:
            values[parsed[0]] = parsed[1]
    return values


def save_local_env(project_root: Path, values: dict[str, str]) -> Path:
    path = project_root / ENV_FILE_NAME
    existing = load_local_env(project_root)
    existing.update({key: value for key, value in values.items() if value is not None})
    lines = [
        "# Local AI Decision Data Agent settings. Do not commit this file.",
        f"LLM_PROVIDER={existing.get('LLM_PROVIDER', '')}",
        f"LLM_BASE_URL={existing.get('LLM_BASE_URL', '')}",
        f"LLM_MODEL={existing.get('LLM_MODEL', '')}",
        f"LLM_API_KEY={existing.get('LLM_API_KEY', '')}",
        f"LLM_ENABLED={existing.get('LLM_ENABLED', 'false')}",
        f"WEB_SEARCH_ENABLED={existing.get('WEB_SEARCH_ENABLED', 'false')}",
        f"WEB_SEARCH_PROVIDER={existing.get('WEB_SEARCH_PROVIDER', 'DuckDuckGo')}",
        f"WEB_SEARCH_API_KEY={existing.get('WEB_SEARCH_API_KEY', '')}",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
