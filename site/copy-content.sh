#!/usr/bin/env bash
# Copies docs/ content from another ref (default: origin/main) into
# site/src/content/docs, ready for `npm run dev` / `npm run build`.
#
# Usage: ./copy-content.sh [ref]
set -euo pipefail

REF="${1:-origin/main}"
SITE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONTENT_DIR="$SITE_DIR/src/content/docs"
REPO_ROOT="$(git -C "$SITE_DIR" rev-parse --show-toplevel)"

git -C "$REPO_ROOT" fetch origin --quiet 2>/dev/null || true

rm -rf "$CONTENT_DIR"
mkdir -p "$CONTENT_DIR"
git -C "$REPO_ROOT" archive "$REF" -- docs | tar -x -C "$CONTENT_DIR" --strip-components=1

echo "Copied docs/ from '$REF' into $CONTENT_DIR"
