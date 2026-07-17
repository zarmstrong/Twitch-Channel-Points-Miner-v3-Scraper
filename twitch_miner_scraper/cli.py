"""Command-line interface."""

from __future__ import annotations

import argparse
import logging

from .app import Application
from .config import Settings

LOG = logging.getLogger(__name__)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Scrape Twitch Drops and badge catalogs into GitHub Gists")
    result.add_argument("command", nargs="?", choices=("serve", "run", "drops", "badges"), default="serve")
    result.add_argument("--no-upload", action="store_true", help="write local snapshots without updating Gists")
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    try:
        settings = Settings.from_env()
        logging.basicConfig(
            level=getattr(logging, settings.log_level),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        LOG.debug(
            "Configuration loaded: command=%s upload=%s output_dir=%s",
            args.command,
            not args.no_upload,
            settings.output_dir,
        )
        app = Application(settings, upload=not args.no_upload)
        if args.command == "serve":
            app.serve()
            return 0
        if args.command == "run":
            return 0 if app.run_all() else 1
        app.run_job(args.command)
        return 0
    except (ValueError, OSError) as error:
        if not logging.getLogger().handlers:
            logging.basicConfig(
                level=logging.ERROR,
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            )
        LOG.error("%s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
