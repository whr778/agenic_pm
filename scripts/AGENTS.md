# Scripts Agent Guide

## Purpose

This folder contains platform-specific start and stop scripts for local Docker runtime.

## Scripts

- start-mac.sh: build image and run container on macOS.
- stop-mac.sh: stop and remove container on macOS.
- start-linux.sh: build image and run container on Linux.
- stop-linux.sh: stop and remove container on Linux.
- start-windows.ps1: build image and run container on Windows (PowerShell).
- stop-windows.ps1: stop and remove container on Windows (PowerShell).

## Runtime assumptions

- Docker is installed and available in PATH.
- Root .env exists and includes OPENROUTER_API_KEY.
- Container name is pm-mvp.
- App is exposed at http://localhost:8000.

## Build resilience behavior

- Start scripts retry Docker image builds to handle transient registry/network failures.
- If remote pulls keep failing, start scripts attempt a local-only build with pull disabled.
- Local-only fallback requires base images to already exist locally:
- node:22-alpine
- python:3.12-slim
- If those images are missing, scripts exit with a clear message instructing how to pre-pull them.

## Guardrails

- Keep scripts idempotent where possible (remove existing container before starting).
- Avoid destructive Docker cleanup beyond the project container.