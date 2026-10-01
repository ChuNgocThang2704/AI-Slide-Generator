# Azure deployment

Host: `datn@20.196.66.24`; directory: `/opt/demodoan`.
Website: `http://20.196.66.24/` (Nginx serves the built frontend and proxies `/api/` to the gateway).

```sh
cd /opt/demodoan
sudo docker compose -f docker-compose.yml -f docker-compose.azure.yml up -d
sudo docker compose -f docker-compose.yml -f docker-compose.azure.yml ps
sudo docker compose -f docker-compose.yml -f docker-compose.azure.yml logs -f --tail 100 ai-service ai-worker document-service
```

Build frontend with `VITE_API_BASE_URL=/api` and `VITE_AI_IMAGES_SAME_ORIGIN=true` before uploading `front-end/dist`.
Nginx proxies `/outputs/images/` to the AI API so browser image URLs do not depend on internal Docker hostnames.
For backend updates, run Compose with `--parallel 1 up -d --build` on this 8 GB host.
The Azure override limits Java heap/container memory and binds database ports to loopback.
Docker is enabled on boot; containers use `restart: unless-stopped`.

This deployment initializes new databases; it does not migrate existing local data.
AI provider settings are loaded from `ai-service/backend/.env`; model availability is independent of container health.
After changing that file, recreate both AI services with the Compose command above.
Port 80 is externally reachable. Port 5173 is also published by Docker but requires an Azure network rule if needed.

## AI gateway (9Router) and image serving

- `9router` (image pinned by digest in `docker-compose.azure.yml`) is the OpenAI-compatible gateway the AI
  service calls first (`VLLM_API_BASE_URL=http://9router:20128`, key in `NINE_ROUTER_API_KEY`, model in
  `NINE_ROUTER_MODEL`). Gemini called directly stays as the last resort.
  The 9router container publishes no port. Its dashboard is reached through port 20128 of the frontend nginx,
  which asks for a second password first (`docker/9router.htpasswd`, mounted read-only; it is created on the
  server and never committed: `printf "user:%s\n" "$(openssl passwd -apr1 'password')" > docker/9router.htpasswd`).
  To link a provider account (Google OAuth) use a tunnel on the same port number,
  `ssh -L 20128:localhost:20128 datn@<host>`, and browse `http://localhost:20128`: the dashboard hardcodes
  `http://localhost:20128/callback` as the OAuth return address, so a different local port, or the server's
  address, breaks the last step.
- **Restart `api-gateway` after recreating a Java service** (`document-service`, `template-service`, ...). The gateway
  resolves a service name once and keeps the container address it got, so after the service is recreated with a new
  address every request to it fails with 500 (`Connection refused: document-service/172.18.x.x`) until the gateway
  is restarted: `docker compose ... restart api-gateway`.
- `ai-service` and `ai-worker` are **separate images**: rebuild both after changing `ai-service/`.
- nginx resolves `ai-service` / `api-gateway` through Docker's DNS (`resolver 127.0.0.11`), so recreating those
  containers no longer leaves nginx pointing at a stale address (which showed up as 502 on `/outputs/images/`).
- The host has a 2 GB swapfile (`/swapfile`, enabled in `/etc/fstab`).
