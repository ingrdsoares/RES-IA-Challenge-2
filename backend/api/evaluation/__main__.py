import logging
from evaluation.cli import main
logging.basicConfig(level=logging.INFO,format='%(levelname)s %(message)s')
raise SystemExit(main())
