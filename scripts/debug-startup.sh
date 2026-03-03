#!/usr/bin/env bash
#
# Start the game and write the outputs unbuffered to `__debug/out.log` for later inspection.

timeout 8s uv run planetfall 2>&1 | tee __debug/out.log
