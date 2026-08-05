#!/bin/bash
# run.sh — launches aiFinance using the project's virtual environment.
# Run from the project root: bash run.sh

cd "$(dirname "$0")"
exec venv/bin/python src/main.py "$@"
