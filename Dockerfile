FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    HOME=/home/app \
    YTMCP_WHISPER_DEVICE=cpu \
    YTMCP_WHISPER_COMPUTE_TYPE=int8

RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir '.[whisper]' \
    && mkdir -p /home/app/.cache \
    && chown -R app:app /home/app/.cache

USER app
ENTRYPOINT ["youtube-transcript-mcp"]
CMD ["serve"]
