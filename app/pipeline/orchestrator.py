import logging
import time
from dotenv import load_dotenv

from app.pipeline.execution import execute
from app.pipeline.ingestion import ingest
from app.pipeline.classification import classify
from app.pipeline.planning import plan
from app.core.logging_config import setup_logging


logger = logging.getLogger(__name__)


def run_once() -> None:
    """
    Run a single end-to-end pass of the pipeline.
    """
    logger.info("Pipeline run starting")
    # Ingestion
    # ingest.run()
    # Classification
    # classify.run()
    # Planning
    plan.run()
    # Execution
    execute.run()
    logger.info("Pipeline run complete")


def run_forever(interval_seconds: int = 300) -> None:
    """
    Run the pipeline on a fixed interval until interrupted.
    """
    logger.info("Pipeline polling loop starting (interval=%ds)", interval_seconds)
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            logger.info("Pipeline polling loop interrupted; exiting")
            raise
        except Exception:
            logger.exception("Pipeline run failed; continuing after interval")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    setup_logging()
    load_dotenv()

    run_once()