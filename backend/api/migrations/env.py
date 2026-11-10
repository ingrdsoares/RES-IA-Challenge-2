from alembic import context
from app.access import models  # noqa: F401
from app.companies import models as company_models  # noqa: F401
from app.config import Settings
from app.db import Base
from sqlalchemy import create_engine

url = Settings().database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
