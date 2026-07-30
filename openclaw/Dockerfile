# OpenClaw gateway — container image for Render (free tier).
#
# Build context is the repo root:
#   docker build -f openclaw/Dockerfile -t openclaw-gateway .

FROM node:22-slim

# ca-certificates for TLS to api.anthropic.com / api.telegram.org / api.github.com.
# curl is used by the healthcheck. git lets skills clone if they ever need to.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN npm install -g openclaw

WORKDIR /app

# Config template and custom skills. Secrets come from env at runtime, never baked in.
COPY openclaw/openclaw.json /app/openclaw.json
COPY openclaw/skills /app/skills

ENV OPENCLAW_CONFIG_PATH=/app/openclaw.json \
    OPENCLAW_STATE_DIR=/app/state \
    NODE_ENV=production

# NOTE: /app/state is container-local. On Render's free tier there is no persistent
# disk, so memory, schedules and channel pairings are LOST on every restart and
# redeploy. Accepted for the lab demo; re-seed reminders shortly beforehand.
# To fix properly, attach a Render disk and point OPENCLAW_STATE_DIR at it.
RUN mkdir -p /app/state

EXPOSE 18789

# Render injects $PORT and requires the process to bind it. OpenClaw reads
# OPENCLAW_GATEWAY_PORT, so translate one to the other and fall back to the
# default when running locally. Bind resolves to 0.0.0.0 automatically because
# OpenClaw detects the container environment.
CMD ["sh", "-c", "export OPENCLAW_GATEWAY_PORT=\"${PORT:-18789}\" && exec openclaw gateway"]
