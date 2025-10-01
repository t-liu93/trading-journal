from sqlmodel import create_engine

import settings
from trading_journal import db_migration

db_engine = create_engine(settings.settings.database_url, echo=True)
db_migration.run_migrations(db_engine)
