import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from qdrant_client import QdrantClient


def test_ingest_publish_and_retry_are_idempotent(client, tmp_path):
    from app.jobs.models import Operation
    from app.legal.ingest import ingest_file, process_version
    from app.legal.models import NormVersion
    from app.legal.schemas import IngestMetadata
    from app.storage import ObjectStorage
    from sqlalchemy import select

    storage = ObjectStorage(
        "http://localhost:19000", "http://localhost:19000", "sd_test_user", "sd_test_password"
    )
    path = tmp_path / "law.md"
    path.write_text("Art. 1º Regra de teste.\n\nArt. 2º Segunda regra.")
    metadata = IngestMetadata(
        document_key="law",
        title="Lei de teste",
        authority="Teste",
        norm_type="lei",
        version_label="v1",
        official_url="https://example.org/law",
    )
    with client.app.state.db_factory() as db:
        first = ingest_file(path, metadata, "ingest-law", db=db, storage=storage)
        db.commit()
        second = ingest_file(path, metadata, "ingest-law", db=db, storage=storage)
        assert first == second
        version = db.get(NormVersion, first)
        assert version.status == "received"
        assert len(list(db.scalars(select(Operation)))) == 1
        index = QdrantClient(":memory:")
        process_version(db, version, storage, index, lambda text: [1.0, 0.0], dimensions=2)
        db.commit()
        assert version.status == "ready"
        assert len(version.anchors) == 2
        process_version(db, version, storage, index, lambda text: [1.0, 0.0], dimensions=2)
        assert index.count("legal_versions_v1").count == 2
        path.write_text("Different content")
        with pytest.raises(HTTPException) as error:
            ingest_file(path, metadata, "different", db=db, storage=storage)
        assert error.value.status_code == 409
        index.close()


def test_failed_index_never_publishes(client, tmp_path):
    from app.legal.ingest import ingest_file, process_version
    from app.legal.models import NormVersion
    from app.legal.schemas import IngestMetadata
    from app.storage import ObjectStorage

    storage = ObjectStorage(
        "http://localhost:19000", "http://localhost:19000", "sd_test_user", "sd_test_password"
    )
    path = tmp_path / "law.md"
    path.write_text("Art. 1 Test")
    metadata = IngestMetadata(
        document_key="law",
        title="Test",
        authority="Test",
        norm_type="lei",
        version_label="v1",
        official_url="https://example.org",
    )
    with client.app.state.db_factory() as db:
        version_id = ingest_file(path, metadata, str(uuid4()), db=db, storage=storage)
        db.commit()
        version = db.get(NormVersion, version_id)

        def unavailable(text):
            raise RuntimeError("model down")

        with pytest.raises(RuntimeError):
            process_version(
                db, version, storage, QdrantClient(":memory:"), unavailable, dimensions=2
            )
        assert version.status != "ready"


@pytest.mark.integration
@pytest.mark.skipif(not os.getenv("QDRANT_TEST_URL"), reason="requires QDRANT_TEST_URL")
def test_real_qdrant_version_payload(client):
    from app.legal.index import index_version
    from app.legal.models import NormVersion
    from app.legal.normalize import normalize

    collection = "test_legal_" + uuid4().hex
    index = QdrantClient(url=os.environ["QDRANT_TEST_URL"])
    version = NormVersion(id=uuid4(), document_id=uuid4(), title="Test")
    try:
        document = normalize(b"Art. 1 Test", "text/markdown")
        index_version(index, version, document, lambda text: [1.0, 0.0], 2, collection)
        points, _ = index.scroll(collection)
        assert points[0].payload["version_id"] == str(version.id)
        assert points[0].payload["anchor_id"] == document.sections[0].anchor_id
    finally:
        if index.collection_exists(collection):
            index.delete_collection(collection)
        index.close()
