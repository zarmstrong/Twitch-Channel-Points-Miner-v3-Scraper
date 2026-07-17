FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OUTPUT_DIR=/data

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY pyproject.toml ./
COPY twitch_miner_scraper ./twitch_miner_scraper
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 scraper \
    && mkdir -p /data \
    && chown scraper:scraper /data

USER scraper
VOLUME ["/data"]
ENTRYPOINT ["twitch-miner-scraper"]
CMD ["serve"]
