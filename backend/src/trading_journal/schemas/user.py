"""User-facing API schemas, layered on the FastAPI Users base models.

``UserRead`` extends the base with the two custom columns we added to the
``User`` table in Phase 2.
"""

import uuid
from datetime import datetime

from fastapi_users import schemas


class UserRead(schemas.BaseUser[uuid.UUID]):
    last_login_at: datetime | None = None
    created_at: datetime


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass
