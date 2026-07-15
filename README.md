# TanaSpace

TanaSpace is an open-source personal inventory and planning app. The
current project is a Vite landing page that will later be migrated into
Django templates when the backend starts.

## Requirements

This project is intended for Ubuntu 22.04 or newer.

Install:

- Docker Engine
- Docker Compose plugin

On Ubuntu 22.04+:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Optional: allow your user to run Docker without `sudo`:

```bash
sudo usermod -aG docker "$USER"
newgrp docker
```

Check your setup:

```bash
docker --version
docker compose version
```

## Project Structure

```txt
TanaSpace/
├─ public/
├─ src/
├─ index.html
├─ package.json
├─ vite.config.js
├─ Dockerfile
├─ docker-compose.yml
├─ CONTRIBUTING.md
├─ README.md
└─ LICENSE
```

## Run With Docker Compose

From the project root:

```bash
docker compose up --build
```

Open:

```txt
http://localhost:5173
```

Stop the app:

```bash
docker compose down
```

## Run Without Docker

From the project root:

```bash
npm install
npm run dev
```

## Build

```bash
npm run build
```

## Planned Backend

The backend is not started yet. When Django is added, the current
landing page can be migrated into Django templates, with frontend assets
served through Django static files or a Vite build pipeline.
