# AGENTS.md

This repository contains the containerized data-publishing service for Twitch Channel Points Miner v3. Keep it small, deterministic, and safe to run unattended.

## Where to start

- CLI and supported commands: [twitch_miner_scraper/cli.py](twitch_miner_scraper/cli.py)
- Job orchestration and scheduling: [twitch_miner_scraper/app.py](twitch_miner_scraper/app.py)
- TwitchDrops.app parsing: [twitch_miner_scraper/drops.py](twitch_miner_scraper/drops.py)
- Twitch Helix badge retrieval: [twitch_miner_scraper/badges.py](twitch_miner_scraper/badges.py)
- Gist publishing: [twitch_miner_scraper/gist.py](twitch_miner_scraper/gist.py)
- Environment configuration: [twitch_miner_scraper/config.py](twitch_miner_scraper/config.py) and [.env.example](.env.example)
- Deployment and operator usage: [README.md](README.md) and [Dockerfile](Dockerfile)

## Runtime contract

- `serve` runs both recurring jobs and is the default container command.
- `run` executes both jobs once; `drops` and `badges` execute one job once.
- Drops run every 900 seconds and badges every 1200 seconds by default.
- Both jobs run immediately when `serve` starts, then follow independent schedules.
- A successful job atomically replaces its local JSON snapshot before updating its configured Gist.
- A failed scrape must not overwrite the previous local snapshot or Gist content.
- One job failing must not stop or delay future runs of the other job.
- Preserve graceful `SIGTERM` and `SIGINT` handling for container shutdown.

## Data contracts

- Treat the generated JSON as a public API consumed by Twitch Channel Points Miner.
- Preserve the top-level `version`, `generated_at`, `source`, and `counts` fields.
- Drops output must retain `indexed_games` and complete per-game reports under `games`.
- Badge output must retain the complete Helix badge sets under `sets`.
- Do not silently rename or remove fields. Increment the schema version and document migrations when making incompatible changes.
- Keep timestamps timezone-aware and serialized as UTC ISO 8601 values.
- Favor stable, source-derived identifiers over identifiers that change between runs.

## Scraping and network behavior

- Keep source-specific parsing in its existing module; do not mix publishing or scheduling into parsers.
- TwitchDrops.app may change without notice. Add or update saved-HTML parser tests when adjusting its selectors or assumptions.
- Use the shared retrying session from [twitch_miner_scraper/http.py](twitch_miner_scraper/http.py).
- Retain finite request timeouts, retry handling for transient failures, and the configurable delay between TwitchDrops.app game requests.
- Do not add browser automation or large dependencies unless the existing HTTP parser can no longer retrieve the required data.
- Never publish a partial catalog after an exception. Build and validate the complete document first.

## Configuration and secrets

- All deployment-specific values belong in environment variables.
- Never commit GitHub tokens, Twitch client secrets, OAuth tokens, client IDs tied to private deployments, Gist IDs, cookies, or captured authenticated responses.
- Keep `.env` ignored and use placeholder values in `.env.example` and documentation.
- Validate only the credentials needed by the selected job. Drops dry runs must not require Twitch or GitHub credentials.
- GitHub Gists must already exist; the service updates them but does not create or delete them.
- When no static Twitch token is configured, preserve automatic app-token refresh and the owner-only token cache under `/data`.

## Container conventions

- Preserve the non-root runtime user and writable `/data` volume.
- Keep `serve` as the image default while allowing command overrides for one-off runs.
- Avoid adding OS packages or Python dependencies unless they are required at runtime.
- Keep logs on stdout/stderr for container log collection; do not add rotating log files inside the image.

## Validation

- Install development dependencies with `python -m pip install -r requirements-dev.txt`.
- Run tests with `python -m pytest`.
- Run `python -m compileall twitch_miner_scraper` and `git diff --check` after code changes.
- Build the image with `docker build -t twitch-miner-scraper:test .` after Docker or dependency changes.
- Prefer mocked HTTP tests. Live source checks are useful before releases but must not require or expose real credentials.
- Add focused tests for configuration validation, failure preservation, response parsing, and output-contract changes.

## Working conventions

- Support Python 3.11 and newer and keep type hints compatible with that baseline.
- Keep changes focused and preserve the existing module boundaries.
- Use standard-library functionality when reasonable; the intentionally small runtime dependency set reduces container maintenance.
- Write snapshots through a temporary file followed by `os.replace`; do not replace this with a direct write.
- Update [README.md](README.md) and [.env.example](.env.example) whenever operator-facing commands or variables change.
