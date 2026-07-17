#!/usr/bin/env python3
"""Interactively validate credentials and create the scraper .env file."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
TWITCH_APPS_URL = "https://dev.twitch.tv/console/apps"
GITHUB_TOKENS_URL = "https://github.com/settings/personal-access-tokens/new"


def request_json(request: Request, timeout: float = 30) -> tuple[dict, object]:
    with urlopen(request, timeout=timeout) as response:
        return json.load(response), response.headers


def validate_twitch(client_id: str, client_secret: str) -> None:
    body = urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "client_credentials",
        }
    ).encode()
    payload, _ = request_json(
        Request(
            TWITCH_TOKEN_URL,
            data=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "TCPMS-Setup/1.0",
            },
            method="POST",
        )
    )
    if not payload.get("access_token") or not payload.get("expires_in"):
        raise ValueError("Twitch did not return a valid app access token")


def validate_github(token: str, gist_ids: list[str]) -> None:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TCPMS-Setup/1.0",
    }
    user, _ = request_json(Request("https://api.github.com/user", headers=headers))
    if not user.get("login"):
        raise ValueError("GitHub did not identify the token owner")
    for gist_id in gist_ids:
        gist, _ = request_json(
            Request(f"https://api.github.com/gists/{gist_id}", headers=headers)
        )
        if gist.get("id") != gist_id:
            raise ValueError(f"GitHub returned an unexpected Gist for {gist_id}")
        owner = (gist.get("owner") or {}).get("login")
        if owner and owner.casefold() != user["login"].casefold():
            raise ValueError(
                f"Gist {gist_id} is owned by {owner}, not token owner {user['login']}"
            )


def env_text(values: dict[str, str]) -> str:
    for name, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"{name} cannot contain a newline")
    return "".join(f"{name}={value}\n" for name, value in values.items())


def write_env(path: Path, values: dict[str, str]) -> None:
    write_env_text(path, env_text(values))


def write_env_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


def merge_env_text(existing: str, updates: dict[str, str]) -> str:
    env_text(updates)
    remaining = dict(updates)
    lines = []
    for line in existing.splitlines():
        name, separator, _ = line.partition("=")
        if separator and name in remaining:
            lines.append(f"{name}={remaining.pop(name)}")
        else:
            lines.append(line)
    if lines and lines[-1]:
        lines.append("")
    lines.extend(f"{name}={value}" for name, value in remaining.items())
    return "\n".join(lines) + "\n"


def required(prompt: str, secret: bool = False) -> str:
    read = getpass.getpass if secret else input
    while True:
        value = read(prompt).strip()
        if value:
            return value
        print("A value is required.", file=sys.stderr)


def confirm_overwrite(path: Path) -> bool:
    if not path.exists():
        return True
    answer = input(f"{path} already exists. Replace it? [y/N] ").strip().casefold()
    return answer in {"y", "yes"}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=Path(".env"), help="output path (default: .env)"
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="write values without contacting Twitch or GitHub",
    )
    providers = parser.add_mutually_exclusive_group()
    providers.add_argument(
        "--github-only", action="store_true", help="configure only GitHub variables"
    )
    providers.add_argument(
        "--twitch-only", action="store_true", help="configure only Twitch variables"
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    partial = args.github_only or args.twitch_only
    if not partial and not confirm_overwrite(args.output):
        print("Configuration was not changed.")
        return 1

    values = {}
    if not args.github_only:
        print("\nTwitch application credentials")
        print(f"Create or manage an application at: {TWITCH_APPS_URL}")
        twitch_client_id = required("Twitch Client ID: ")
        twitch_client_secret = required("Twitch Client Secret: ", secret=True)
        values.update(
            {
                "TCPMS_TWITCH_CLIENT_ID": twitch_client_id,
                "TCPMS_TWITCH_CLIENT_SECRET": twitch_client_secret,
                "TCPMS_TWITCH_OAUTH_TOKEN": "",
            }
        )

    if not args.twitch_only:
        print("\nGitHub Gist publishing")
        print(f"Create a fine-grained token at: {GITHUB_TOKENS_URL}")
        print("Grant User permissions -> Gists: Read and write.")
        github_token = required("GitHub token: ", secret=True)
        drops_gist_id = required("Drops Gist ID: ")
        badges_gist_id = required("Badges Gist ID: ")
        values.update(
            {
                "TCPMS_GITHUB_TOKEN": github_token,
                "TCPMS_DROPS_GIST_ID": drops_gist_id,
                "TCPMS_BADGES_GIST_ID": badges_gist_id,
            }
        )

    if not args.skip_validation and not args.github_only:
        print("\nValidating Twitch credentials...")
        validate_twitch(twitch_client_id, twitch_client_secret)
    if not args.skip_validation and not args.twitch_only:
        print("Validating GitHub token and Gists...")
        validate_github(github_token, [drops_gist_id, badges_gist_id])

    if not partial:
        values.update(
            {
                "TCPMS_DROPS_INTERVAL_SECONDS": "900",
                "TCPMS_BADGES_INTERVAL_SECONDS": "1200",
                "TCPMS_LOG_LEVEL": "INFO",
            }
        )
        write_env(args.output, values)
    else:
        existing = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        write_env_text(args.output, merge_env_text(existing, values))
    print(f"\nWrote {args.output} with owner-only permissions.")
    print("Start the service with: docker compose up -d --build --force-recreate")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError, OSError, ValueError) as error:
        print(f"Setup failed: {error}", file=sys.stderr)
        raise SystemExit(2)
