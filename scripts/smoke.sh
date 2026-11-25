#!/usr/bin/env bash
# Environment + provider smoke test wrapper (lands in M1: tizita smoke).
exec uv run tizita smoke "$@"
