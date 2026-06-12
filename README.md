# boVIE

boVIE discovers VIE/VIA (Volontariat International en Entreprise/Administration) opportunities from Business France.

The scraper is written in Python and publishes discovered offers to NATS JetStream. A TypeScript worker in `apps/worker` consumes those jobs later, deduplicates them in PostgreSQL, and can post notifications to Discord.

## Acknowledgments

- Inspired by this [TikTok](https://www.tiktok.com/@ingesclave/video/7431604779899456801)
- Uses the Business France VIE/VIA platform as data source

## Features

- Fetches VIE/VIA opportunities from Business France
- Publishes discovered offers to NATS JetStream
- Processes queued offers in a TypeScript worker
- Deduplicates processed offers with PostgreSQL
- Optionally posts processed offers to Discord

## Prerequisites

- Python 3.13 or higher
  - While it may work with earlier versions, it has only been tested with Python 3.13
- Node.js 20 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- NATS with JetStream enabled
- PostgreSQL
- Optional [Discord webhook](https://support.discord.com/hc/fr/articles/228383668-Introduction-aux-Webhooks) URL

## Installation

Install Python and TypeScript dependencies:

```sh
uv sync
pnpm install
```

## Configuration

boVIE can be configured through command-line arguments, environment variables, or a combination of both.

### Command Line Arguments

```sh
uv run python -m bovie.main --help

Options:
  --debug
  --nats-url TEXT
  --nats-stream TEXT
  --nats-subject TEXT
  --limit INTEGER
  --geozone TEXT
  --country TEXT
  --specialization TEXT
```

### Environments variables

1. Create a `.env` file in the project root directory
2. Add the following environment variables:

```sh
DATABASE_URL=postgresql://postgres:password@localhost:5432/database
NATS_URL=nats://localhost:4222
NATS_STREAM=BOVIE_JOBS
NATS_JOB_SUBJECT=jobs.discovered
NATS_CONSUMER=bovie-worker
DISCORD_WEBHOOK_URL=
BOVIE_LIMIT=25
BOVIE_REGION="north america,asia pacific,south america"
BOVIE_SPECIALIZATION="information systems,scientific and industrial computing"
```

## Usage

Start local services:

```sh
docker compose up -d
```

Run the TypeScript worker:

```sh
pnpm run worker
```

Run the Python scraper:

```sh
uv run python -m bovie.main --limit 5
```

The scraper publishes messages to JetStream. The worker acknowledges a message only after the offer has been inserted or recognized as a duplicate and optional notification work has completed.

## Development

```sh
just check
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
