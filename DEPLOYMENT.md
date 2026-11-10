# Deploy with Docker Compose

The production Compose stack serves HTTPS through Nginx. Nginx limits requests before they reach Django, serves static files, and passes application requests to Gunicorn. PostgreSQL and Gunicorn are private to the Compose network.

## Prepare

1. Point your domain's DNS at the server and obtain a trusted TLS certificate. Put its `fullchain.pem` and `privkey.pem` in a directory readable by Docker.
2. Copy `.env.production.example` to `.env.production`. Set `DJANGO_ALLOWED_HOSTS` to your domain (comma separated if needed), `TLS_CERT_DIR` to the absolute certificate directory, and generate unique secrets for `DJANGO_SECRET_KEY` and `POSTGRES_PASSWORD`. For example, run `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` separately for each value. Keep `.env.production` private.
3. Allow inbound TCP port 443 in your firewall. Certificate renewal is your responsibility; restart the proxy after renewing a certificate.

Start the production stack:

```sh
docker compose --env-file .env.production -p tanaspace_prod -f compose.production.yml up -d --build
```

View status and logs:

```sh
docker compose --env-file .env.production -p tanaspace_prod -f compose.production.yml ps
docker compose --env-file .env.production -p tanaspace_prod -f compose.production.yml logs -f app proxy
```

Rebuild after changes with the same `up -d --build` command. The production image builds Tailwind and Vite assets; it does not run the development frontend watcher. The app migrates the database and collects static files at startup. The demo cleanup loop runs every five minutes.

This stack uses its own PostgreSQL volume. It does not copy data from the development stack. Back up the production database and certificate files separately.

## Limits

Nginx applies these limits per client IP, returning HTTP 429 when exceeded:

| Traffic | Sustained rate | Immediate burst |
| --- | ---: | ---: |
| All requests | 5 per second | 15 |
| POST, PUT, PATCH, DELETE | 30 per minute | 5 |
| Demo creation | 2 per minute | 1 |

It also allows at most 10 simultaneous requests per IP and 100 overall, rejects request bodies over 16 KiB with HTTP 413, and applies short client timeouts. Django caps each account at 20 types and 100 items, allows 25 active demo accounts by default, and removes demo accounts after one hour.

These are practical limits for a small deployment, not a guarantee against a distributed attack. They assume clients connect directly to this Nginx service. If you later add a CDN or another reverse proxy, configure trusted client IP forwarding before relying on the per IP limits. Multiple proxy replicas would each keep independent counters.
