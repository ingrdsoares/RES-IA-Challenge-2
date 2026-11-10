import argparse
from pathlib import Path

from app.legal.ingest import ingest_file
from app.legal.schemas import IngestMetadata


def main():
    parser = argparse.ArgumentParser(description="Ingestão administrativa de normas")
    parser.add_argument("command", choices=["ingest"])
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--metadata", required=True, type=Path)
    parser.add_argument("--key", required=True, help="Chave idempotente da operação")
    args = parser.parse_args()
    metadata = IngestMetadata.model_validate_json(args.metadata.read_bytes())
    version_id = ingest_file(args.file, metadata, args.key)
    print(version_id)


if __name__ == "__main__":
    main()
