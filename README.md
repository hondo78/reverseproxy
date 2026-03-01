# Reverse Proxy Manager

A self-hosted Nginx reverse proxy with a web-based management UI, built-in Certificate Authority, and access logging. Runs as a Docker Compose stack.

## Features

- **Route Management** — Create host-based (`app.example.com`) or path-based (`/api/`) proxy routes through the web UI
- **Built-in Certificate Authority** — Generate a root CA and issue SSL certificates for your domains without external dependencies
- **Health Checks** — Automatic periodic monitoring of all backend services (TCP/HTTP)
- **Access Logging** — Persistent Nginx proxy logs and manager logs with filtering by time, IP, method, and path
- **Web UI** — Modern dark-themed dashboard to manage everything from the browser
- **Docker Native** — Nginx config generation, validation (`nginx -t`), and reload happen automatically via Docker socket

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Docker Compose                                  │
│                                                  │
│  ┌───────────┐    ┌───────────────────────────┐  │
│  │   Nginx   │    │  Manager (FastAPI)         │  │
│  │  :80/:443 │◄───│  :8080                     │  │
│  │           │    │  ├─ REST API               │  │
│  │  Reverse  │    │  ├─ Web UI                 │  │
│  │  Proxy    │    │  ├─ CA Management          │  │
│  └───────────┘    │  ├─ Health Checks          │  │
│                   │  └─ SQLite DB              │  │
│                   └───────────────────────────┘  │
│                                                  │
│  Volumes: nginx-config, certs, ca, db, logs      │
└──────────────────────────────────────────────────┘
```

A detailed architecture diagram is available as [architecture.drawio](architecture.drawio).

## Quick Start

```bash
git clone https://github.com/hondo78/reverseproxy.git
cd reverseproxy
cp .env.example .env   # or create your own .env (see Configuration)
docker compose up --build -d
```

Open `http://localhost:8080` (or your configured `MANAGER_PORT`) to access the web UI.

## Configuration

All settings are managed through the `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `MANAGER_PORT` | `8080` | Port for the management web UI |
| `HTTP_PORT` | `80` | Nginx HTTP port |
| `HTTPS_PORT` | `443` | Nginx HTTPS port |
| `CA_COMMON_NAME` | `Reverse Proxy CA` | Name of the root Certificate Authority |
| `CA_VALIDITY_YEARS` | `10` | Root CA certificate validity |
| `CERT_VALIDITY_DAYS` | `365` | Default validity for issued certificates |
| `HEALTH_CHECK_INTERVAL` | `30` | Seconds between backend health checks |
| `DB_PATH` | `/data/db/proxy.db` | SQLite database path inside the container |

Example `.env`:

```env
MANAGER_PORT=8888
HTTP_PORT=80
HTTPS_PORT=443
CA_COMMON_NAME=My Company CA
HEALTH_CHECK_INTERVAL=30
```

## Usage

### Managing Routes

1. Open the **Routes** tab in the web UI
2. Click **+ Add Route**
3. Choose the route type:
   - **Host-based**: Routes traffic by domain name (e.g. `app.example.com`)
   - **Path-based**: Routes traffic by URL path (e.g. `/api/`)
4. Enter the target host (IP or hostname) and port of your backend service
5. Optionally enable SSL and select a certificate
6. Save — Nginx config is automatically generated, validated, and reloaded

### SSL Certificates

1. Go to the **Certificates** tab
2. Click **Initialize CA** to create a root Certificate Authority (one-time setup)
3. Download the CA certificate and install it in your browser/system to trust it
4. Click **+ Issue Certificate** to create certificates for your domains
5. Assign certificates to routes by enabling SSL on a route and selecting the certificate

### Access Logs

The **Logs** tab provides two views:

- **Proxy** — All traffic flowing through the Nginx reverse proxy to your backends
- **Manager** — Requests to the management API and web UI

Filter logs by:
- Time range (from/to)
- Client IP
- HTTP method
- Host or path

Logs are persisted to disk and survive container restarts.

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/routes` | `GET` | List all routes |
| `/api/routes` | `POST` | Create a new route |
| `/api/routes/{id}` | `GET` | Get route details |
| `/api/routes/{id}` | `PUT` | Update a route |
| `/api/routes/{id}` | `DELETE` | Delete a route |
| `/api/routes/{id}/toggle` | `POST` | Enable/disable a route |
| `/api/ca` | `GET` | Get active CA info |
| `/api/ca/init` | `POST` | Initialize the Certificate Authority |
| `/api/ca/download` | `GET` | Download CA certificate (PEM) |
| `/api/certificates` | `GET` | List all certificates |
| `/api/certificates/issue` | `POST` | Issue a new certificate |
| `/api/certificates/{id}` | `DELETE` | Delete a certificate |
| `/api/certificates/{id}/download` | `GET` | Download certificate (PEM) |
| `/api/health` | `GET` | Health status of all backends |
| `/api/logs/proxy` | `GET` | Nginx proxy access logs |
| `/api/logs/manager` | `GET` | Manager access logs |

Log endpoints support query parameters: `limit`, `ip`, `method`, `path`, `time_from`, `time_to`.

## Project Structure

```
reverseproxy/
├── docker-compose.yml          # Service definitions
├── .env                        # Configuration
├── nginx/
│   ├── Dockerfile
│   ├── nginx.conf              # Base config with JSON access logging
│   └── entrypoint.sh           # Auto-generates default SSL cert
├── manager/
│   ├── Dockerfile              # Python 3.12 + Docker CLI
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py             # FastAPI application
│   │   ├── config.py           # Environment configuration
│   │   ├── database.py         # SQLAlchemy async models
│   │   ├── models.py           # Pydantic schemas
│   │   ├── middleware.py        # Access logging middleware
│   │   ├── routers/            # API endpoints
│   │   ├── services/           # Business logic (CA, Nginx, Health)
│   │   └── static/             # Web UI (HTML/CSS/JS)
│   └── templates/
│       └── nginx_route.conf.j2 # Nginx config template
└── architecture.drawio         # Architecture diagram
```

## Tech Stack

- **Proxy**: Nginx 1.27 (Alpine)
- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), aiosqlite
- **Certificates**: cryptography (Python)
- **Config Templating**: Jinja2
- **Frontend**: Vanilla HTML/CSS/JS (no frameworks)
- **Infrastructure**: Docker Compose

## Docker Volumes

| Volume | Purpose |
|--------|---------|
| `nginx-config` | Generated Nginx route configurations |
| `certs-data` | SSL certificates (shared between Nginx and Manager) |
| `ca-data` | Certificate Authority keys |
| `db-data` | SQLite database |
| `log-data` | Access logs (shared between Nginx and Manager) |

## License

MIT
