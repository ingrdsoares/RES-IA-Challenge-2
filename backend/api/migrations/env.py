from alembic import context
from app.access import models  # noqa: F401
from app.assistant import models as assistant_models  # noqa: F401
from app.companies import models as company_models  # noqa: F401
from app.config import Settings
from app.db import Base
from app.evidence import models as evidence_models  # noqa: F401
from app.jobs import models as job_models  # noqa: F401
from app.legal import models as legal_models  # noqa: F401
from app.tasks import models as task_models  # noqa: F401
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
