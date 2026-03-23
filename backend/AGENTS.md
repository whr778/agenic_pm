# Backend Agent Guide

## Purpose

This folder contains the FastAPI backend for the Project Management MVP.

## Current scope (Part 2 scaffold)

- FastAPI app entry: app/main.py.
- Static scaffold page: static/index.html served at /.
- Health endpoint: GET /health.
- Example API endpoint: GET /api/hello.
- OPENROUTER_API_KEY is read from environment and only exposed as a boolean configured flag.
- Tests live in tests/ and use FastAPI TestClient with pytest.

## Runtime and dependency management

- Python dependencies are defined in pyproject.toml.
- Docker image uses uv in-container for dependency installation.
- Container serves the app with uvicorn on port 8000.

## Guardrails

- Keep backend logic simple and explicit.
- Do not expose secrets in responses or logs.
- Add tests with each behavior change.
- Prefer clear schema and service layers as features expand.