import argparse
from pathlib import Path
from uuid import UUID

from app.access import models as accounts  # noqa: F401
from app.companies import models as companies  # noqa: F401
from app.config import Settings
from app.db import session_factory
from app.fiscal.registry import import_rule, review_rule
from app.fiscal.schemas import RuleInput


def main():
    parser = argparse.ArgumentParser(
        description="Administração de regras; nunca revisa automaticamente"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    entry = sub.add_parser("import")
    entry.add_argument("--file", required=True, type=Path)
    review = sub.add_parser("review")
    review.add_argument("--id", required=True, type=UUID)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--evidence", required=True)
    args = parser.parse_args()
    factory = session_factory(Settings().database_url)
    try:
        with factory.begin() as db:
            rule = (
                import_rule(db, RuleInput.model_validate_json(args.file.read_bytes()))
                if args.command == "import"
                else review_rule(db, args.id, args.reviewer, args.evidence)
            )
            print(rule.id)
    finally:
        factory.kw["bind"].dispose()


if __name__ == "__main__":
    main()
