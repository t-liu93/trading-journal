import sys
from pathlib import Path

from sqlmodel import create_engine

project_parent = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_parent))

import settings  # noqa: E402
from trading_journal import db_migration  # noqa: E402

db_engine = create_engine(settings.settings.database_url, echo=True)
db_migration.run_migrations(db_engine)
