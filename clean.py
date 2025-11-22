import shutil
from datetime import datetime
from pathlib import Path

from pridexyz.logger import get_logger

logger = get_logger(__name__)


def main():
    start_time = datetime.now()
    logger.info("Starting clean task")

    # Paths and environment
    build = Path('build')

    if build.is_dir():
        try:
            shutil.rmtree(build)
            logger.info(f"Removed existing build directory at {build}")
        except Exception as e:
            logger.error(f"Failed to remove build directory: {e}", exc_info=True)
            return
    else:
        logger.info(f"No existing build directory found at {build}, nothing to remove.")

    logger.info(f"Done: clean task completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms.")


if __name__ == '__main__':
    main()

