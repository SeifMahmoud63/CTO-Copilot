# CTO-Copilot

- Web App: http://localhost:8000/
- API Docs (Swagger): http://localhost:8000/docs
- Health API: http://localhost:8000/api/health
- Pull Requests API: http://localhost:8000/api/prs

## Database migrations (Alembic)

The MySQL schema (`pull_requests`, `engineers`) is versioned with Alembic.
The app container applies `alembic upgrade head` automatically on startup,
so a normal `docker compose up` is enough to keep the schema up to date.
The commands below are for when **you change the models** or need to
inspect/migrate manually.

All commands run from the repo root. Talking to the MySQL container from
your own terminal requires overriding the host/port (see "Why the
`MYSQL_HOST` override?" below).

### 1. After changing `app/models/*`, generate a migration

```powershell
python -m alembic revision --autogenerate -m "short description of the change"
```

Always open the generated file in `alembic/versions/` and review it
before applying — autogenerate detects column/table diffs, not data moves.

### 2. Apply migrations to the docker MySQL

```powershell
$env:MYSQL_HOST="127.0.0.1"; $env:MYSQL_PORT="3307"; python -m alembic upgrade head
```

### 3. Check migration status

```powershell
$env:MYSQL_HOST="127.0.0.1"; $env:MYSQL_PORT="3307"; python -m alembic current
$env:MYSQL_HOST="127.0.0.1"; $env:MYSQL_PORT="3307"; python -m alembic history
```

### 4. Existing database that already matches the models (stamp, don't run)

If a database was created/migrated outside Alembic but its schema already
matches `head`, mark it without executing anything:

```powershell
$env:MYSQL_HOST="127.0.0.1"; $env:MYSQL_PORT="3307"; python -m alembic stamp head
```

### 5. Run the migration unit tests (SQLite, no MySQL needed)

```powershell
python -m pytest tests/ -v
```

### 6. Rebuild the app container after backend changes

```powershell
docker compose build cto-copilot; docker compose up -d cto-copilot
```

(The image ships `alembic.ini` + `alembic/`, so startup migrations keep
working after a rebuild.)

### Why the `MYSQL_HOST` override?

`MYSQL_HOST=mysql` in `.env` is a **Docker-network hostname** — it only
resolves *inside* the compose network, which is exactly what the app
container needs (`mysql:3306`). Your Windows terminal lives *outside*
that network, so `mysql` doesn't resolve there. Overriding with
`127.0.0.1:3307` (the port published to your machine in
`docker-compose.yml`) just points the CLI at the same server through the
public door. This is standard Docker behavior, not a bug — nothing needs
fixing, and `.env` stays as is for the containers.
