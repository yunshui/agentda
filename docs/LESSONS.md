# Lessons Learned

## Architecture & Design

1. **RSA encryption for tokens** — Using asymmetric encryption for tokens means the proxy/client cannot read the user identity. This is a good security boundary. The token is opaque to anyone but the MCP Core that holds the private key.

2. **Service naming** — Original names (`backend_api`, `mcp_remote`) were ambiguous about their role. Renaming to `api-core`, `mcp-core`, `agent-core` provides clearer semantic boundaries.

3. **API prefix consistency** — All services should use consistent URL prefixes (`/api/`, `/mcp/`, `/agent/`) to allow middleware filtering and reverse proxy configuration.

4. **Log directory structure** — Centralized `/data/logs/<service>/` per-service log directories are cleaner than a single shared log directory, especially in Docker environments with volume mounts.

## Logging

1. **MCP path skip in access log** — The MCP middleware needs its own access logging at tool-name granularity (not just URL path). The `skip_path_prefix` parameter on `AccessLogMiddleware` enables this pattern.

2. **Access log naming** — Separating access log names from app log names (`api-acc` vs `api-core`) allows different retention policies and easier parsing.

3. **Log directory as parameter** — Making `log_dir` a parameter of `setup_logging()` (instead of a global constant) allows each service to specify its own log path without modifying shared code.

## Docker

1. **Multi-stage builds** — Using a builder stage for pip install and a final stage for runtime reduces image size significantly (no build tools in final image).

2. **Service dependency management** — Docker Compose `depends_on` ensures startup order, but services should also handle the case where dependencies aren't ready yet (retry logic).

3. **Volume mounts for logs** — Mounting host directories at `/data/logs/<service>/` makes logs accessible outside containers without needing `docker cp`.

## Security

1. **Token lifetime** — 15-minute access tokens balance security (short window if compromised) with usability (infrequent refreshes). 7-day refresh tokens with revocation support provide a recovery mechanism.

2. **RLS at API level** — Implementing row-level security at the API layer (not just the data layer) provides defense in depth.

3. **No user_id from caller** — MCP tools never accept user_id from the caller. This prevents identity spoofing even if a client tries to pass another user's ID.
