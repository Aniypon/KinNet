"""Template context processors for KinNet."""

from __future__ import annotations


def ui_preferences(request) -> dict:
    """Surface the user's UI prefs (elder mode, theme) for every template.

    Stored in the session so prefs survive across pages without a database
    write. The toggle endpoints under ``/profile/ui/...`` mutate the session.
    """
    session = getattr(request, "session", None)
    elder_mode = bool(session.get("elder_mode")) if session is not None else False
    theme = (session.get("theme") if session is not None else None) or "light"
    return {
        "ui_elder_mode": elder_mode,
        "ui_theme": theme,
    }
