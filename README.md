# Twitch Channel Points Miner v3 Scraper

A small container service that publishes two machine-readable JSON catalogs:

- active and upcoming campaigns from [twitchdrops.app](https://twitchdrops.app/), every 15 minutes;
- Twitch global chat badges from Helix, every 20 minutes.

Each successful job first writes an atomic snapshot under `/data`, then updates its configured GitHub Gist. Failed jobs are logged and leave the prior snapshot and Gist intact. The two schedules are independent and run immediately when the container starts.

## Configuration

Copy `.env.example` to `.env` and set:

- `GITHUB_TOKEN`: a GitHub token allowed to update both Gists;
- `DROPS_GIST_ID` and `BADGES_GIST_ID`: existing Gist IDs;
- `TWITCH_CLIENT_ID` and `TWITCH_OAUTH_TOKEN`: credentials accepted by the Twitch Helix API.

The Gists must already exist. The service updates `twitch-drops.json` and `twitch-badges.json` by default; filenames and intervals can be changed with the optional variables documented in `.env.example`. Do not commit `.env`.

## Build the image

```bash
docker build -t twitch-miner-scraper .
```

## Run continuously

The standard container starts both schedules immediately and stores the latest
snapshots in a named Docker volume:

```bash
docker volume create twitch-miner-scraper-data
docker run -d \
  --name twitch-miner-scraper \
  --restart unless-stopped \
  --env-file .env \
  --mount source=twitch-miner-scraper-data,target=/data \
  twitch-miner-scraper
```

Follow its logs or stop and remove it with:

```bash
docker logs -f twitch-miner-scraper
docker stop twitch-miner-scraper
docker rm twitch-miner-scraper
```

Removing the container does not remove the named data volume.

## One-off runs

Run both jobs once:

```bash
docker run --rm \
  --env-file .env \
  --mount source=twitch-miner-scraper-data,target=/data \
  twitch-miner-scraper run
```

Run only one source:

```bash
docker run --rm --env-file .env \
  --mount source=twitch-miner-scraper-data,target=/data \
  twitch-miner-scraper drops
docker run --rm --env-file .env \
  --mount source=twitch-miner-scraper-data,target=/data \
  twitch-miner-scraper badges
```

For a local dry run that writes JSON without touching GitHub:

```bash
mkdir -p data
docker run --rm \
  --user "$(id -u):$(id -g)" \
  --env-file .env \
  --mount type=bind,source="$PWD/data",target=/data \
  twitch-miner-scraper drops --no-upload
```

The same commands work without Docker after installing the project:

```bash
python -m pip install -e .
python -m twitch_miner_scraper run
```

## Output contract

Both documents have `version`, `generated_at`, `source`, and `counts` fields. Drops output includes the TwitchDrops.app front-page index and per-game campaign/drop reports. Badge output retains the complete Helix badge-set response under `sets`. Consumers should reject unsupported major `version` values and may use the previous Gist revision if a publisher run fails.

## Tests

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```
