"""Shared auth dependencies for protected endpoints.

Phase 4's ``Account`` CRUD endpoints depend on ``current_active_user``.
"""

from trading_journal.auth.backend import fastapi_users

current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)
