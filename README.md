# deupoly

Self-hosted multiplayer board game inspired by Monopoly with an authoritative FastAPI backend.

## Stack

- Python 3.12
- FastAPI + Starlette WebSocket
- Pydantic
- Redis / PostgreSQL containers for runtime infrastructure
- Docker / docker-compose
- nginx reverse proxy

## Project structure

```text
app/
  api/           HTTP + WebSocket routes
  core/          board definitions, domain engine, exceptions
  models/        Pydantic domain/api/ws models
  services/      game session manager and connection registry
  main.py        FastAPI application
static/
  index.html     MVP client for manual testing
nginx/
  nginx.conf     reverse proxy with WebSocket upgrade
Dockerfile
docker-compose.yml
requirements.txt
```

## MVP features

- game creation and lobby join
- authoritative turn flow on the server
- 40-tile board
- dice rolling and movement
- tile resolution
- property purchase
- rent collection
- basic auction system
- event deck
- jail / audit / tax / jackpot cells
- Redis cache for hot state
- PostgreSQL snapshots for restart recovery
- realtime state sync over WebSocket

## Quick start

### Local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

### Docker

```bash
docker compose up --build
```

Open [http://localhost](http://localhost).

Bootstrap admin credentials are configured through backend environment variables:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

In the provided `docker-compose.yml` they are set to a placeholder pair and should be changed before production deploy.

`nginx` is also attached to the external Docker network `proxy`, so this network must already exist on the host:

```bash
docker network create proxy
```

For Portainer or any host that already has a reverse proxy on ports `80/443`, do not publish the stack's own `nginx` to the host. In this setup `nginx` is reachable only inside Docker networks (`app` + external `proxy`), and the existing reverse proxy should route traffic to it over the `proxy` network.

### Make targets

```bash
make up
make logs
make down
make test
```

Available shortcuts:

- `make up` - build and start the full docker stack in background
- `make down` - stop the stack
- `make restart` - rebuild and restart the stack
- `make logs` - stream docker logs
- `make ps` - show container status
- `make build` - rebuild images
- `make test` - run tests quietly
- `make test-verbose` - run tests with full pytest output
- `make install` - install Python dependencies locally
- `make run` - run FastAPI locally with auto-reload

## Tests

```bash
PYTHONDONTWRITEBYTECODE=1 pytest
```

## Minimal API

### HTTP

- `GET /api/health`
- `POST /api/auth/register`
- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `GET /api/games`
- `POST /api/games`
- `GET /api/games/{game_id}`
- `POST /api/games/{game_id}/players`
- `POST /api/games/{game_id}/start`
- `DELETE /api/games/{game_id}` (admin)
- `GET /api/admin/users` (admin)
- `POST /api/admin/users` (admin)

### WebSocket

- `WS /api/ws/games/{game_id}` with auth session cookie

Client commands:

- `roll_dice`
- `buy_property`
- `decline_property`
- `start_auction`
- `place_bid`
- `pass_auction`
- `leave_jail`
- `end_turn`

Server events:

- `game_state_update`
- `dice_result`
- `auction_update`
- `turn_change`
- `info`
- `error`

## Notes

- The server is authoritative: the client only sends intents, never resolves game rules locally.
- Runtime state is cached in Redis and snapshotted into PostgreSQL after every mutating action.
- Users have persistent accounts, session cookies, visible table list, and rating counters: total games, active paused games, wins, losses.
- Finished games are automatically removed once the last connected player leaves the table; final results remain in rating history.
- WebSocket connections still live in-process, so horizontal scaling would require a shared pub/sub layer for fan-out.
- GitHub Actions runs tests on `main` and `dev`; a successful `main` push is then synchronized automatically into `dev`.
- nginx config is baked into its own image, which avoids Portainer bind-mount issues with single config files.
