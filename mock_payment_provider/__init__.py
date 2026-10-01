"""Small, deterministic mock payment provider used by local development/tests.

The package intentionally has no dependency on the ordering application's
database or models.  Import :data:`app` for an ASGI application, or use
``create_app`` in tests when an isolated provider state is useful.
"""

from .app import app, create_app

__all__ = ["app", "create_app"]
