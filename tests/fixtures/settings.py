"""Run tests with specific runtime settings."""

import app_settings
from app_settings import RuntimeSettings


def use_settings(**groups: dict[str, object]) -> RuntimeSettings:
    """E.g. use_settings(email={"auto_replies": False}); reset after each test by conftest."""
    base = app_settings.defaults()
    updated = base.model_copy(
        update={
            name: getattr(base, name).model_copy(update=values) for name, values in groups.items()
        }
    )
    app_settings.override(updated)
    return updated
