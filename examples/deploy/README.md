# Deploying `flightdeck serve` (reference)

FlightDeck stays **local-first**: this directory is **optional** packaging for demos, staging, or a **trusted** private network. Read **[SECURITY.md](../../SECURITY.md)** before exposing HTTP beyond loopback.

## Docker image

Build (from this directory):

```bash
docker build -t flightdeck-serve:local .
```

The image installs **`flightdeck-ai`** from PyPI and runs **`flightdeck serve`** on **`0.0.0.0:8765`** inside the container.

**`entrypoint.sh`** creates a default **`flightdeck.yaml`** in `/workspace` on first start (`flightdeck init`) if the mounted volume is empty.

## Compose (loopback bind on the host)

```bash
cd examples/deploy
docker compose up --build
```

- **UI + API:** `http://127.0.0.1:8765/` (static UI + `/v1/*`).
- **Health:** `GET http://127.0.0.1:8765/health`.
- **Data:** named Docker volume **`fd_workspace`** (SQLite under **`.flightdeck/`** inside the volume). Remove with `docker compose down -v` when you want a clean ledger.

### Optional mutation token

Set **`FLIGHTDECK_LOCAL_API_TOKEN`** in your environment before `docker compose up` (or in an `.env` file beside `docker-compose.yml`). Clients must send **`Authorization: Bearer …`** for **`POST /v1/promote`** and **`POST /v1/rollback`**. Ingest and diff are **not** behind this Bearer gate by default—treat network placement accordingly.

### Bind-mounting a host workspace

To reuse an existing directory that already contains **`flightdeck.yaml`** and **`.flightdeck/`**, replace the `volumes` entry with:

```yaml
volumes:
  - /path/on/host/my-workspace:/workspace
```

Use an absolute path on Linux/macOS; on Windows Docker Desktop, use a path Docker can mount.

## Process supervision

Compose provides restart policies; for systemd/Kubernetes, reuse the same image and run **`/entrypoint.sh`** (or invoke **`flightdeck serve`** directly with a prepared workspace directory).

## Related

- **[examples/integration/README.md](../integration/README.md)** — emit `RunEvent` traffic into a running server.
- **[examples/ci/README.md](../ci/README.md)** — CI policy gates without `serve`.
