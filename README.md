# Twitch Channel Points Miner v3 Scraper

A small container service that publishes two machine-readable JSON catalogs:

- active and upcoming campaigns from [twitchdrops.app](https://twitchdrops.app/), every 15 minutes;
- Twitch global chat badges from Helix, every 20 minutes.

Each successful job first writes an atomic snapshot under `/data`, then updates its configured GitHub Gist. Failed jobs are logged and leave the prior snapshot and Gist intact. The two schedules are independent and run immediately when the container starts.

## Configuration

Copy `.env.example` to `.env` and set:

- `TCPMS_GITHUB_TOKEN`: a GitHub token allowed to update both Gists;
- `TCPMS_DROPS_GIST_ID` and `TCPMS_BADGES_GIST_ID`: existing Gist IDs;
- `TCPMS_TWITCH_CLIENT_ID` and `TCPMS_TWITCH_CLIENT_SECRET`: Twitch application credentials used to obtain an app access token automatically.

Every application variable uses the `TCPMS_` prefix to avoid collisions with
other containers on the same Docker host. The Gists must already exist. The
service updates `twitch-drops.json` and `twitch-badges.json` by default;
filenames and intervals can be changed with the optional variables documented
in `.env.example`. Do not commit `.env`.

The automatically obtained Twitch token is stored as
`/data/twitch-app-token.json` with owner-only permissions. The scraper reuses it
until five minutes before expiry, then obtains and stores a replacement. Set
`TCPMS_TWITCH_OAUTH_TOKEN` only if you prefer to provide and renew a token
yourself; when set, it takes precedence and is not written to disk.

### GitHub token permissions

The recommended credential is a fine-grained personal access token owned by
the same GitHub account that owns the configured Gists. It needs only:

- **User permissions → Gists: Read and write**

No repository or organization permissions are required. The scraper uses the
token only to call GitHub's `PATCH /gists/{gist_id}` endpoint for the two
existing Gists; it does not create or delete Gists.

If you use a personal access token (classic), grant only the `gist` scope.
Configure either token type as `TCPMS_GITHUB_TOKEN`, give it an appropriate
expiration date, and rotate it before it expires. See GitHub's
[Gist endpoint permissions](https://docs.github.com/en/rest/gists/gists#update-a-gist)
for the current requirements.

## Build the image

```bash
docker build -t twitch-miner-scraper .
```

## Docker Compose

If you prefer Docker Compose, create a local `compose.yaml` beside the
Dockerfile with the following contents:

```yaml
services:
  scraper:
    build: .
    image: twitch-miner-scraper
    container_name: twitch-miner-scraper
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - scraper-data:/data

volumes:
  scraper-data:
```

Build and start the scheduled service, then follow its logs:

```bash
docker compose up -d --build
docker compose logs -f scraper
```

Run both jobs once, or run one source independently:

```bash
docker compose run --rm scraper run
docker compose run --rm scraper drops
docker compose run --rm scraper badges
```

Stop the service without deleting its persistent data volume:

```bash
docker compose down
```

The Compose file is intentionally deployment-local so operators can adjust
container names, networks, labels, and volume configuration without changing
the application repository.

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
