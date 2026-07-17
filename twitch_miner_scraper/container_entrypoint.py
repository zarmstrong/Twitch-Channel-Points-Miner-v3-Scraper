"""Prepare container storage, drop root privileges, and execute the CLI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SCRAPER_UID = 10001
SCRAPER_GID = 10001


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("container entrypoint requires a command")

    command = sys.argv[1:]
    if command[0] in {"serve", "run", "drops", "badges"}:
        command.insert(0, "twitch-miner-scraper")

    if os.geteuid() == 0:
        output_dir = Path(os.getenv("TCPMS_OUTPUT_DIR", "/data"))
        output_dir.mkdir(parents=True, exist_ok=True)
        os.chown(output_dir, SCRAPER_UID, SCRAPER_GID)
        os.setgroups([])
        os.setgid(SCRAPER_GID)
        os.setuid(SCRAPER_UID)

    os.execvp(command[0], command)


if __name__ == "__main__":
    main()
