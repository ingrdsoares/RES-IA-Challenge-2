from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.config import Settings
from evaluation.adapter import InternalRagClient


def test_metadata_sem_git_registra_unavailable():
    client = InternalRagClient.__new__(InternalRagClient)
    client.settings = Settings()
    client.service = MagicMock()
    client.service.store.count.return_value = 1
    client.service.store.client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(model_dump=lambda mode: {})
    )
    client.service.models.client.list.return_value = SimpleNamespace(models=[])

    with patch("evaluation.adapter.subprocess.run", side_effect=FileNotFoundError("git")):
        assert client.metadata()["git_sha"] == "unavailable"
