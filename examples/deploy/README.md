# Deploying `flightdeck serve` (reference)

FlightDeck stays **local-first**: this directory is **optional** packaging for demos, staging, or a **trusted** private network. Read **[SECURITY.md](../../SECURITY.md)** before exposing HTTP beyond loopback.

## Docker image

Build (from this directory):

```bash
docker build -t flightdeck-serve:local .
```

The image installs **`flightdeck-ai`** from PyPI and runs **`flightdeck serve`** on **`0.0.0.0`** using port **`8765`** by default. On platforms that set **`PORT`** (for example **Railway**), **`entrypoint.sh`** binds to **`$PORT`** instead.

**`entrypoint.sh`** creates a default **`flightdeck.yaml`** in `/workspace` on first start (`flightdeck init`) if the mounted volume is empty.

## Compose (loopback bind on the host)

```bash
cd examples/deploy
docker compose up --build
```

- **UI + API:** `http://127.0.0.1:8765/` (static UI + `/v1/*`).
- **Health:** `GET http://127.0.0.1:8765/health`.
- **Compose healthcheck:** `docker-compose.yml` probes **`/health`** so orchestrators can mark the service ready (see `healthcheck:` in that file).
- **Data:** named Docker volume **`fd_workspace`** (SQLite under **`.flightdeck/`** inside the volume). Remove with `docker compose down -v` when you want a clean ledger.

### SQLite backups

FlightDeck stores the ledger in **`.flightdeck/flightdeck.db`** under the workspace root. For a **hot copy** while the server is stopped or idle, run from the workspace directory:

```bash
flightdeck doctor --backup ./backups/flightdeck-$(date -u +%Y%m%dT%H%M%SZ).db
```

Inside the Compose stack, **`exec`** into the running container with **`/workspace`** as cwd (same layout as local **`flightdeck init`**), or run a one-shot sidecar that mounts the same volume and invokes **`flightdeck doctor --backup /workspace/backups/snapshot.db`**. Schedule with **cron** or your platform scheduler; keep backups off the primary volume when possible.

### Optional mutation token

Set **`FLIGHTDECK_LOCAL_API_TOKEN`** in your environment before `docker compose up` (or in an `.env` file beside `docker-compose.yml`). Clients must send **`Authorization: Bearer …`** for **ledger writes**: **`POST /v1/promote*`**, **`POST /v1/rollback`**, and **`POST /v1/events`**. With no token configured, those routes accept only **loopback** callers. **`POST /v1/diff`** stays unauthenticated (read-only); still treat network placement as a trust boundary.

## Railway

[Railway](https://railway.app/) often suits **small demos**; pricing and free allowances change — confirm **[Railway pricing](https://railway.com/pricing)** before relying on **`$0/month`** long term.

### Deploy from this repo

1. Create a **new project** → **Deploy from GitHub** (or **`railway init`** / **`railway link`** with the [CLI](https://docs.railway.app/guides/cli)).
2. Set the service **root directory** to **`examples/deploy`** so Railway builds **`Dockerfile`** and picks up **`railway.toml`** (config-as-code).  
   If the dashboard root cannot be a subdirectory, set [**`RAILWAY_DOCKERFILE_PATH`**](https://docs.railway.app/guides/dockerfiles) (service variable) to **`examples/deploy/Dockerfile`** and point **config as code** at **`examples/deploy/railway.toml`** per [config-as-code](https://docs.railway.app/guides/config-as-code).
3. **Networking:** enable **Public Networking** and **Generate Domain** (HTTPS). Railway routes traffic to the **`PORT`** your process listens on; **`entrypoint.sh`** uses **`PORT`** automatically.
4. **Variables (recommended for any public URL):** add **`FLIGHTDECK_LOCAL_API_TOKEN`** (random secret). The stock PyPI image does **not** embed that token in the browser bundle — use **read-only UI** (`VITE_FLIGHTDECK_UI_READ_ONLY=true` in a **custom image build**) or rebuild static assets with **`VITE_FLIGHTDECK_LOCAL_API_TOKEN`** so the UI can authenticate when **`read_auth`** is bearer-gated — see **`docs/web-ui.md`** and **[SECURITY.md](../../SECURITY.md)**.
5. **Persistent SQLite (optional):** add a [Railway volume](https://docs.railway.app/guides/volumes) mounted at **`/workspace`** so redeploys keep **`.flightdeck/`**. Without a volume, the ledger may reset when the container is recreated.

CLI sketch (from **`examples/deploy`** after **`railway link`**):

```bash
railway login
cd examples/deploy
railway variable set FLIGHTDECK_LOCAL_API_TOKEN="$(openssl rand -hex 24)"
railway up
railway domain   # generate .railway.app URL if needed
```

## Helm (optional single-replica chart)

A minimal chart lives under **`chart/flightdeck/`**. It runs one replica of **`flightdeck serve`** with an **`emptyDir`** workspace (ephemeral); for a persistent ledger, replace the volume in **`templates/deployment.yaml`** with a PVC or mount your own image init.

```bash
docker build -t flightdeck-serve:local .
helm install fd ./chart/flightdeck --namespace flightdeck --create-namespace
```

Tune **`values.yaml`** (`image`, `resources`, `service.type`) for your cluster.

### Bind-mounting a host workspace

To reuse an existing directory that already contains **`flightdeck.yaml`** and **`.flightdeck/`**, replace the `volumes` entry with:

```yaml
volumes:
  - /path/on/host/my-workspace:/workspace
```

Use an absolute path on Linux/macOS; on Windows Docker Desktop, use a path Docker can mount.

## Process supervision

Compose sets a **`healthcheck`** on **`/health`** plus **`restart: unless-stopped`** on the service; for systemd/Kubernetes, reuse the same image and run **`/entrypoint.sh`** (or invoke **`flightdeck serve`** directly with a prepared workspace directory).

## Operator checklist

- **Logs:** `docker compose logs -f flightdeck` (or your platform log stream) when debugging ingest or policy failures.
- **State:** one **`flightdeck serve`** instance per workspace SQLite file; do not run two writers against the same volume.
- **Upgrades:** rebuild the image on semver bumps; keep **`/workspace`** mounted so the ledger survives container recreation.

## Related

- **[examples/integration/README.md](../integration/README.md)** — emit `RunEvent` traffic into a running server.
- **[examples/ci/README.md](../ci/README.md)** — CI policy gates without `serve`; **approval-gated promote** script [promote_with_approval.sh](../ci/promote_with_approval.sh) and workflow samples.
- **[SECURITY.md](../../SECURITY.md)** — trust boundaries before exposing **`/v1/*`** beyond loopback.
