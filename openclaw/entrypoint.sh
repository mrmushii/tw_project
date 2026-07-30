#!/bin/sh
# Container entrypoint for the OpenClaw gateway.
#
# Two things have to happen before the gateway starts, both consequences of the
# state directory being ephemeral on Render's free tier.
#
# 1. Anthropic auth. OpenClaw recognises exactly two env vars for this provider:
#
#        CORE_PROVIDER_AUTH_ENV_VAR_CANDIDATES = {
#          anthropic: ["ANTHROPIC_OAUTH_TOKEN", "ANTHROPIC_API_KEY"], ...
#
#    ANTHROPIC_AUTH_TOKEN — the name the local .env and render.yaml use, and the
#    name the Anthropic SDK itself accepts — is NOT among them, so setting it
#    alone produces "No API key found for provider anthropic" on every turn.
#    A Claude Pro subscription token (sk-ant-oat01-...) is an OAuth credential,
#    so it belongs in ANTHROPIC_OAUTH_TOKEN. This maps one to the other.
#
#    Writing auth-profiles.json / auth-state.json by hand does NOT work on this
#    version: the agent authenticates from openclaw-agent.sqlite, and static JSON
#    profiles written into the agent dir are ignored. Tried, verified, abandoned.
#
# 2. Render injects $PORT and requires the process to bind it; OpenClaw reads
#    OPENCLAW_GATEWAY_PORT.
#
# Credentials stay in the process environment and the container filesystem only.
# Nothing is baked into the image and nothing is committed.

set -e

STATE_DIR="${OPENCLAW_STATE_DIR:-/app/state}"

if [ -z "$ANTHROPIC_OAUTH_TOKEN" ] && [ -n "$ANTHROPIC_AUTH_TOKEN" ]; then
  export ANTHROPIC_OAUTH_TOKEN="$ANTHROPIC_AUTH_TOKEN"
  echo "[entrypoint] mapped ANTHROPIC_AUTH_TOKEN -> ANTHROPIC_OAUTH_TOKEN (${#ANTHROPIC_OAUTH_TOKEN} chars)"
fi

if [ -z "$ANTHROPIC_OAUTH_TOKEN" ] && [ -z "$ANTHROPIC_API_KEY" ]; then
  echo "[entrypoint] WARNING: no Anthropic credential found — agent turns will fail."
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
