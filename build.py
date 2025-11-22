import json
from datetime import datetime
from pathlib import Path

import dotenv

from pridexyz.builder import Builder
from pridexyz.color import convert_hex_to_rgb
from pridexyz.logger import get_logger
from pridexyz.tooltip.build import TooltipBuilder

logger = get_logger(__name__)


def main():
    start_time = datetime.now()
    logger.info("Starting build task")

    # Paths and environment
    src_dir = Path('src')
    build_dir = Path('build')
    build_user = dotenv.get_key('.env', 'BUILD_USER') or "Unknown"

    try:
        # Load colors
        colors_path = src_dir / 'colors.json'
        logger.info(f"Loading colors from {colors_path}")
        with open(colors_path, 'r') as colors_file:
            colors = json.load(colors_file)

        # Load metadata
        meta_path = src_dir / 'meta.json'
        logger.info(f"Loading metadata from {meta_path}")
        with open(meta_path, 'r') as meta_file:
            meta = json.load(meta_file)

    except Exception as e:
        logger.error(f"Failed to load configuration files: {e}", exc_info=True)
        return

    builders = Builder.create_builders(logger, src_dir, build_dir, build_user, meta, [
        TooltipBuilder
    ])

    district_pack_count = 0
    for palette_name, palette in colors.items():
        palette_name: str = palette_name.split("/")[0]
        logger.info(f"Processing palette '{palette_name}'")
        palette_colors = [convert_hex_to_rgb(c) for c in palette['colors']]
        logger.debug(f"\tConverted palette colors: {palette_colors}")

        for builder in builders:
            district_pack_count += builder.build(palette, palette_name, palette_colors)

    logger.info(f"Total packs built: {district_pack_count}")
    logger.info(f"Done: build task completed in {int((datetime.now() - start_time).total_seconds() * 1000)}ms.")


if __name__ == '__main__':
    main()
