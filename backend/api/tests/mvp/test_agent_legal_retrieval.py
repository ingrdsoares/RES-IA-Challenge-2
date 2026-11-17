from datetime import date

import pytest
from qdrant_client import QdrantClient


def test_hybrid_generation_requires_matching_catalog_and_can_be_activated(client):
    from app.assistant.tools import retrieve_legal
    from app.legal.hybrid import activate_generation, active_collection, build_generation
    from app.legal.models import Norm, NormVersion
    from app.legal.normalize import normalize

    index = QdrantClient(":memory:")
    doc = normalize(b"Art. 1 A biblioteca conserva documentos por assunto.", "text/markdown")

    class Storage:
        def get(self, key, private=False):
            return doc.model_dump_json().encode()

    factory = client.app.state.db_factory
    with factory.begin() as db:
        norm = Norm(document_key="hybrid-test")
        db.add(norm)
        db.flush()
        version = NormVersion(
            document_id=norm.id,
            version_label="demo",
            title="Biblioteca",
            authority="Teste",
            jurisdiction="BR",
            norm_type="lei",
            subjects=[],
            official_url="https://example.org/law",
            effective_from=date(2020, 1, 1),
            checksum="a" * 64,
            metadata_hash="b" * 64,
            original_key="original.md",
            json_key="doc.json",
            media_type="text/markdown",
            status="ready",
            anchors=[s.anchor_id for s in doc.sections],
        )
        db.add(version)
        db.flush()
        generation = build_generation(db, index, Storage(), lambda text: [1.0, 0.0], 2)
        assert active_collection(db) is None
        activate_generation(db, index, generation.id)
        assert active_collection(db) == generation.collection
        passages = retrieve_legal(
            db,
            index,
            "biblioteca",
            {"company": {"state": "DF"}, "period": "2026-10"},
            lambda text: [1.0, 0.0],
            5,
            0,
            hybrid_collection=generation.collection,
        )
        assert len(passages) == 1
        assert passages[0]["anchor_id"] == doc.sections[0].anchor_id
        assert passages[0]["retrieval_strategy"] == "hybrid"
        version.checksum = "b" * 64
        db.flush()
        assert active_collection(db) is None
    index.close()


def test_generation_rejects_json_with_anchors_not_in_catalog(client):
    from app.legal.hybrid import build_generation
    from app.legal.models import Norm, NormVersion
    from app.legal.normalize import normalize

    factory = client.app.state.db_factory
    # Reuse the fixture of the valid-generation test through a standalone document.
    doc = normalize(b"Art. 1 Texto.", "text/markdown")

    class Storage:
        def get(self, key, private=False):
            return doc.model_dump_json().encode()

    index = QdrantClient(":memory:")
    with factory.begin() as db:
        norm = Norm(document_key="bad-anchors")
        db.add(norm)
        db.flush()
        db.add(
            NormVersion(
                document_id=norm.id,
                version_label="v1",
                title="Teste",
                authority="Teste",
                jurisdiction="BR",
                norm_type="teste",
                subjects=[],
                official_url="https://example.org/test",
                effective_from=date(2020, 1, 1),
                checksum="a" * 64,
                metadata_hash="b" * 64,
                original_key="original.md",
                json_key="doc.json",
                media_type="text/markdown",
                status="ready",
                anchors=["fake"],
            )
        )
        db.flush()
        with pytest.raises(ValueError):
            build_generation(db, index, Storage(), lambda text: [1.0, 0.0], 2)
    index.close()
