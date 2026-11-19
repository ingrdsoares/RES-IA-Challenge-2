import logging

from evaluation.cli import main
from evaluation.topologias import fabrica

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
raise SystemExit(main(client_factory=fabrica()))
