#!/usr/bin/env bash
# Package the committed project (no .env, no virtualenvs) for upload as a private Kaggle dataset.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p dist
git archive --format=zip --prefix=chipff-bench/ -o dist/chipff-bench.zip HEAD
echo "wrote dist/chipff-bench.zip ($(du -h dist/chipff-bench.zip | cut -f1)) from commit $(git rev-parse --short HEAD)"
