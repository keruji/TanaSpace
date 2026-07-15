# Contributing to TanaSpace

Thanks for helping improve TanaSpace.

## Development Setup

This project targets Ubuntu 22.04 or newer.

Use Docker Compose for the recommended local setup:

```bash
docker compose up --build
```

The frontend will be available at:

```txt
http://localhost:5173
```

## Project Areas

- `src/` contains the current Vite JavaScript and CSS.
- `public/` contains static public assets.
- Django backend files are planned for a future phase.

## Before Opening a Pull Request

Run the frontend build:

```bash
npm run build
```

Keep changes focused and include a short explanation of what changed and
why.
