# OpenClaw gateway — container image for Render (free tier).
#
# Build context is the repo root:
#   docker build -f openclaw/Dockerfile -t openclaw-gateway .

FROM node:22-slim

# ca-certificates for TLS to api.anthropic.com / api.telegram.org / api.github.com.
# curl is used by the healthcheck. git lets skills clone if they ever need to.
RUN apt-get update \
# python3 runs the github-notify skill's check.py, which does the new/seen diffing.
    && apt-get install -y --no-install-recommends ca-certificates curl git python3 \
    && rm -rf /var/lib/apt/lists/*

# Debian ships python3 with no `python` alias. The github-notify skill invokes
# `python`, which is what exists on the Windows dev machine, so alias it here
# rather than making the skill branch on platform.
RUN ln -sf /usr/bin/python3 /usr/bin/python

RUN npm install -g openclaw

WORKDIR /app

# Config template and custom skills. Secrets come from env at runtime, never baked in.
COPY openclaw/openclaw.json /app/openclaw.json

# Skills go INSIDE the workspace, at workspace/skills/<name>/, so the container
# layout is identical to the local install (~/.openclaw/workspace/skills/<name>/).
# They used to land in /app/skills, which meant the workspace-relative path in
# SKILL.md resolved to a file that existed locally but not here — the skill then
# reported "files not found" on the deployed instance only. One layout, one path.
COPY openclaw/skills /app/workspace/skills

# Chela's persona — IDENTITY.md / SOUL.md / USER.md. These live in the agent
# workspace, which OpenClaw would otherwise place under the (ephemeral) state dir,
# so the agent would come up with no personality after every redeploy. Baking them
# into the image at a path outside /app/state makes the persona survive restarts.
# The workspace stays writable, so the agent can still evolve these files at
# runtime — those runtime edits are what gets lost on redeploy, not the base files.
COPY openclaw/workspace /app/workspace

ENV OPENCLAW_CONFIG_PATH=/app/openclaw.json \
    OPENCLAW_STATE_DIR=/app/state \
    NODE_ENV=production

# NOTE: /app/state is container-local. On Render's free tier there is no persistent
# disk, so memory, schedules and channel pairings are LOST on every restart and
# redeploy. Accepted for the lab demo; re-seed reminders shortly beforehand.
# To fix properly, attach a Render disk and point OPENCLAW_STATE_DIR at it.
RUN mkdir -p /app/state

EXPOSE 18789

# The entrypoint materialises the Anthropic auth profile from ANTHROPIC_AUTH_TOKEN
# (OpenClaw will not authenticate agent turns from the env var alone) and maps
# Render's $PORT onto OPENCLAW_GATEWAY_PORT before starting the gateway.
#
# Binding to 0.0.0.0 is handled by gateway.bind="lan" in openclaw.json — NOT by
# container auto-detection, which does not fire on Render.
COPY openclaw/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

CMD ["/app/entrypoint.sh"]
