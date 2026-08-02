"""Phone notification helpers for Waukeen Crafting Assistant."""

from __future__ import annotations

import json
import secrets
import urllib.request


DEFAULT_NTFY_SERVER = "https://ntfy.sh"


def generate_ntfy_topic() -> str:
    """Return a hard-to-guess topic name suitable for the public ntfy service."""
    return f"wca-{secrets.token_urlsafe(18).replace('_', '-')}"


def normalize_ntfy_server(server: str) -> str:
    value = (server or DEFAULT_NTFY_SERVER).strip().rstrip("/")
    if not value.lower().startswith(("https://", "http://")):
        value = f"https://{value}"
    return value


def ntfy_subscription_url(server: str, topic: str) -> str:
    return f"{normalize_ntfy_server(server)}/{topic.strip()}"


def publish_ntfy(
    server: str,
    topic: str,
    title: str,
    message: str,
    *,
    priority: int = 3,
    timeout: float = 6.0,
    opener=urllib.request.urlopen,
) -> None:
    """Publish one JSON notification to an ntfy server."""
    topic = (topic or "").strip()
    if not topic:
        raise ValueError("ntfy topic is empty")
    payload = json.dumps(
        {
            "topic": topic,
            "title": str(title or "WCA"),
            "message": str(message or "Craft stopped."),
            "priority": max(1, min(5, int(priority))),
            "tags": ["white_check_mark"] if priority <= 3 else ["warning"],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        normalize_ntfy_server(server) + "/",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with opener(request, timeout=timeout) as response:
        status = int(getattr(response, "status", 200))
        if status < 200 or status >= 300:
            raise RuntimeError(f"ntfy returned HTTP {status}")

