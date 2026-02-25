#!/bin/bash
# Start the game and write the outputs unbuffered to `__debug/out.log` for later inspection.

timeout 5s .venv/bin/python -u barproj/cli.py 2>&1 | tee __debug/out.log
