# Bovie

A python script that helps you discover VIE/VIA (Volontariat International en Entreprise/Administration) opportunities from Business France.

The script automatically fetches new positions and posts them using a Discord webhook.

## Acknowledgments

- Inspired by this [TikTok](https://www.tiktok.com/@ingesclave/video/7431604779899456801)
- Uses the Business France VIE/VIA platform as data source

## Features

- Automatically fetches new VIE/VIA opportunities
- Posts updates to Discord via webhook
- File or in-memory storage options
- Continuous mode
  - Customizable polling interval (default: 60 seconds)
- CLI interface for manual checks
<!-- - Beautiful Discord embeds for each job posting -->

## Prerequisites

- Python 3.13 or higher
  - While it may work with earlier versions, it has only been tested with Python 3.13
- [uv](https://github.com/astral-sh/uv) package manager
- [Discord webhook](https://support.discord.com/hc/fr/articles/228383668-Introduction-aux-Webhooks) URL

## Installation

Install dependencies using [uv](https://github.com/astral-sh/uv):

```sh
uv install
```

## Configuration

Bovie can be configured through command-line arguments, environment variables, or a combination of both.

### Command Line Arguments

```sh
Usage: bovie.py bot [OPTIONS]

Options:
  --webhook-url TEXT              Discord webhook URL
  --limit INTEGER                 Maximum number of offers to fetch (default: 25)
  --storage-type [memory|file]    Storage backend to use: 'file' or 'memory' (default: file)
  --continuous BOOLEAN            Run in continuous mode, checking for new offers periodically (default: False)
  --sleep-duration INTEGER RANGE  Interval between checks in continuous mode, in seconds (default: 60)  [x>=1]
  --help                          Show this message and exit.
```

```sh
Usage: bovie.py pull [OPTIONS]

Options:
  --limit INTEGER  Maximum offers to fetch (default: 25)
  --help           Show this message and exit.
```

### Environments variables

1. Create a `.env` file in the project root directory
2. Add the following environment variables:

#### Bot

```sh
# Required
DISCORD_WEBHOOK_URL=your_webhook_url_here

# Optional
BOVIE_OFFER_MAX=50          # Max offers to fetch (default: 50)
BOVIE_STORAGE_TYPE=file     # Storage type: file|memory (default: file)
BOVIE_CONTINUOUS=false      # Run continuously (default: false)
BOVIE_SLEEP_DURATION=60     # Sleep duration in seconds (default: 60 seconds)
```

#### Pull

```sh
# Optional
BOVIE_OFFER_MAX=50          # Max offers to fetch (default: 50)
```

## Usage

### Running the Discord Bot

To start the Discord bot that automatically posts new opportunities:

```bash
uv run python bovie.py bot
```

or use the docker image

```sh
docker pull ghcr.io/reidaa/bovie:latest
```

### Manual Offer Check

To manually check and display the latest offers in your terminal:

```bash
uv run python bovie.py pull --limit 5  # Adjust number as needed
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Troubleshooting

### Common Issues

1. Storage issues
    - Try --storage-type memory if file storage fails
    - Check write permissions in project directory
