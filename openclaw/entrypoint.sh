#!/bin/sh
# Container entrypoint for the OpenClaw gateway.
#
# Two things have to happen before the gateway starts, both consequences of the
# state directory being ephemeral on Render's free tier.
#
# 1. Anthropic auth. OpenClaw does NOT read ANTHROPIC_AUTH_TOKEN from the
#    environment for agent turns — it authenticates from a stored auth profile
#    that `openclaw models auth setup-token` normally writes interactively. That
#    file lives under the state dir, so on Render it simply does not exist and
#    every turn fails with "Authentication failed (provider returned HTTP 401)".
#    An interactive setup-token run is impossible in a container, so the profile
#    is materialised here from the env var instead.
#
# 2. Render injects $PORT and requires the process to bind it; OpenClaw reads
#    OPENCLAW_GATEWAY_PORT.
#
# The token is written to the container filesystem only. It is never baked into
# the image and never committed.

set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/app/state}"
AGENT_AUTH_DIR="$STATE_DIR/agents/main/agent"
AUTH_PROFILES="$AGENT_AUTH_DIR/auth-profiles.json"

if [ -n "$ANTHROPIC_AUTH_TOKEN" ]; then
  mkdir -p "$AGENT_AUTH_DIR"
  # printf keeps the token out of the process list and out of any log line.
  printf '{\n  "version": 1,\n  "profiles": {\n    "anthropic:default": {\n      "type": "token",\n      "provider": "anthropic",\n      "token": "%s"\n    }\n  }\n}\n' \
    "$ANTHROPIC_AUTH_TOKEN" > "$AUTH_PROFILES"
  chmod 600 "$AUTH_PROFILES"

  # The profile alone is not enough: auth-state.json is what binds the provider
  # to a profile ("lastGood"). Without it the agent reports
  # 'No API key found for provider "anthropic"' even though the profile exists.
  printf '{\n  "version": 1,\n  "lastGood": {\n    "anthropic": "anthropic:default"\n  }\n}\n' \
    > "$AGENT_AUTH_DIR/auth-state.json"

  echo "[entrypoint] wrote anthropic auth profile (${#ANTHROPIC_AUTH_TOKEN} chars) to $AUTH_PROFILES"
  echo "[entrypoint] wrote auth-state.json binding anthropic -> anthropic:default"
else
  echo "[entrypoint] WARNING: ANTHROPIC_AUTH_TOKEN is unset — agent turns will fail with HTTP 401."
fi

# GitHub credentials for the github-notify skill. The skill reads the state-dir
# dotenv first and falls back to the environment, so this is belt-and-braces —
# but it keeps the container behaving the same way the local install does.
if [ -n "$GITHUB_TOKEN" ] && [ -n "$GITHUB_REPO" ]; then
  mkdir -p "$STATE_DIR"
  printf 'GITHUB_TOKEN=%s\nGITHUB_REPO=%s\n' "$GITHUB_TOKEN" "$GITHUB_REPO" > "$STATE_DIR/.env"
  chmod 600 "$STATE_DIR/.env"
  echo "[entrypoint] wrote github credentials to $STATE_DIR/.env"
fi

export OPENCLAW_GATEWAY_PORT="${PORT:-18789}"
echo "[entrypoint] starting gateway on port $OPENCLAW_GATEWAY_PORT"

exec openclaw gateway
