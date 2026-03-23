# Project Management MVP

## Run (Docker)

Use the platform script from the repository root:

- macOS: `./scripts/start-mac.sh`
- Linux: `./scripts/start-linux.sh`
- Windows (PowerShell): `./scripts/start-windows.ps1`

Stop with the matching stop script in `scripts/`.

## Troubleshooting: Docker Hub EOF on startup

If startup fails with Docker errors like `failed to resolve source metadata` or `EOF` when pulling `node:22-alpine` or `python:3.12-slim`, Docker Hub is temporarily unreachable from your machine.

When network is available, pre-pull the base images and retry:

```bash
docker pull node:22-alpine
docker pull python:3.12-slim
./scripts/start-mac.sh
```

The start scripts already retry builds and can fall back to local-only builds if those base images are cached locally.
