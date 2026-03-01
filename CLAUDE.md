# Reverse Proxy Manager

## Projektübersicht
Nginx-basierter Reverse Proxy mit Web-UI zur Verwaltung von Routen und eigener Certificate Authority (CA). Läuft als Docker-Compose-Setup.

## Architektur
- **Nginx** (`:83`/`:4433`) - Reverse Proxy
- **Manager** (`:8888`) - FastAPI-Backend mit Web-UI, REST-API, CA-Management, SQLite-DB
- Kommunikation: Manager generiert Nginx-Configs in shared Volume, Reload via `docker exec`

## Befehle
```bash
# Starten
docker compose up --build

# Nur neu bauen
docker compose build

# Stoppen
docker compose down

# Logs
docker compose logs -f manager
docker compose logs -f nginx
```

## Projektstruktur
```
reverseproxy/
├── docker-compose.yml
├── .env                          # Ports + CA-Konfiguration
├── nginx/
│   ├── Dockerfile
│   ├── nginx.conf                # Basis-Config mit Default-Server
│   └── entrypoint.sh             # Generiert Default-SSL-Cert beim Start
├── manager/
│   ├── Dockerfile                # Python 3.12-slim + docker.io
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py               # FastAPI Entry, Lifespan-Events
│   │   ├── config.py             # Env-Variablen
│   │   ├── database.py           # SQLAlchemy Async Models
│   │   ├── models.py             # Pydantic Schemas
│   │   ├── routers/
│   │   │   ├── routes.py         # CRUD /api/routes
│   │   │   ├── certificates.py   # /api/ca + /api/certificates
│   │   │   └── health.py         # /api/health
│   │   ├── services/
│   │   │   ├── nginx.py          # Config-Generierung + Reload
│   │   │   ├── ca.py             # CA-Erstellung + Zertifikat-Ausstellung
│   │   │   └── healthcheck.py    # Periodischer Backend-Check
│   │   └── static/               # Web-UI (HTML/CSS/JS)
│   └── templates/
│       └── nginx_route.conf.j2   # Jinja2-Template für Nginx-Routen
└── data/                         # Persistente Daten (Docker Volumes)
```

## Volume-Mapping (wichtig!)
| Volume | Manager-Mount | Nginx-Mount |
|--------|--------------|-------------|
| `certs-data` | `/data/certs` | `/etc/nginx/certs` (ro) |
| `nginx-config` | `/etc/nginx/conf.d` | `/etc/nginx/conf.d` |

Templates verwenden `NGINX_CERTS_DIR` (`/etc/nginx/certs`) für Cert-Pfade in generierten Configs.

## API-Endpoints
- `GET/POST /api/routes` - Routen CRUD
- `GET/PUT/DELETE /api/routes/{id}` - Einzelne Route
- `POST /api/routes/{id}/toggle` - Aktivieren/Deaktivieren
- `GET/POST /api/ca/init` - CA verwalten
- `GET /api/ca/download` - CA-Zertifikat herunterladen
- `POST /api/certificates/issue` - Zertifikat ausstellen
- `GET /api/certificates` - Zertifikate auflisten
- `GET /api/health` - Backend-Health-Status

## Tech-Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy (async), aiosqlite, Jinja2, cryptography
- **Frontend**: Vanilla HTML/CSS/JS (kein Framework), Dark Theme
- **Infra**: Docker Compose, Nginx 1.27-alpine

## Konfiguration
Ports und CA-Parameter werden über `.env` konfiguriert. Aktuelle Werte:
- Manager: `8888`, HTTP: `83`, HTTPS: `4433`

## Konventionen
- Deutsche Kommentare in Konfigurationsdateien, englischer Code
- Kein externes CSS/JS-Framework in der Web-UI
- Alle Python-Dateien nutzen async/await Pattern
