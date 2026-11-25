import argparse
from pathlib import Path

from app.legal.ingest import ingest_file
from app.legal.schemas import IngestMetadata


def main():
    parser = argparse.ArgumentParser(description="Ingestão administrativa de normas")
    parser.add_argument("command", choices=["ingest", "build-hybrid", "activate-hybrid"])
    parser.add_argument("--file", required=False, type=Path)
    parser.add_argument("--metadata", required=False, type=Path)
    parser.add_argument("--key", required=False, help="Chave idempotente da operação")
    parser.add_argument("--generation", help="ID da geração híbrida pronta")
    args = parser.parse_args()
    if args.command != "ingest":
        from uuid import UUID

        from qdrant_client import QdrantClient

        from app.config import Settings
        from app.db import session_factory
        from app.legal.hybrid import activate_generation, build_generation
        from app.legal.ingest import storage_from_settings
        from app.models import LocalModels

        settings = Settings()
        factory = session_factory(settings.database_url)
        index = QdrantClient(url=str(settings.qdrant_url), timeout=settings.qdrant_timeout)
        model = LocalModels(settings)
        try:
            with factory.begin() as db:
                if args.command == "build-hybrid":
                    generation = build_generation(
                        db,
                        index,
                        storage_from_settings(settings),
                        model.embed_document,
                        settings.embedding_dimensions,
                    )
                    print(generation.id)
                else:
                    if not args.generation:
                        parser.error("--generation é obrigatório")
                    activate_generation(db, index, UUID(args.generation))
                    print(args.generation)
        finally:
            index.close()
            model.close()
            factory.kw["bind"].dispose()
        return
    if not args.file or not args.metadata or not args.key:
        parser.error("ingest exige --file, --metadata e --key")
    metadata = IngestMetadata.model_validate_json(args.metadata.read_bytes())
    version_id = ingest_file(args.file, metadata, args.key)
    print(version_id)


if __name__ == "__main__":
    main()
