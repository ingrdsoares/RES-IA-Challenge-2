import os
import subprocess
import sys
from pathlib import Path


def test_worker_database_metadata_loads_in_fresh_process(client):
    script = """
from app.db import session_factory
from app.jobs.service import enqueue
factory = session_factory('postgresql+psycopg://postgres:sd_test_local@localhost:15432/sd_test')
with factory.begin() as db:
    operation = enqueue(db, 'startup', None, None, 'fresh-process', {})
    print(operation.status)
"""
    api = str(Path(__file__).resolve().parents[2])
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": api},
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "queued"
