# Bovie

A Discord bot that helps you discover VIE/VIA (Volontariat International en Entreprise/Administration) opportunities from Business France. The bot automatically fetches new positions and posts them to a designated Discord channel.

## Acknowledgments

- Inspired by a TikTok video from [@ingesclave](https://www.tiktok.com/@ingesclave/video/7431604779899456801)
- Uses the Business France VIE/VIA platform as data source

## Features

- Automatically fetches new VIE/VIA opportunities
- Posts updates to a designated Discord channel
- CLI tool for both bot operation and manual offer checking
<!-- - Customizable polling interval (default: 30 minutes) -->
<!-- - Beautiful Discord embeds for each job posting -->

## Prerequisites

- Python 3.13 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- A Discord bot token
- A Discord channel ID where the bot will post opportunities

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/Reidaa/bovie
    cd bovie
    ```

2. Install dependencies using [uv](https://github.com/astral-sh/uv):

    ```bash
    uv install
    ```

## Configuration

1. Create a `.env` file in the project root directory
2. Add the following environment variables:

```sh
# Your Discord bot token
BOVIE_DISCORD_TOKEN=your_token_here

# Maximum number of offers to fetch in each cycle
BOVIE_OFFER_MAX=10

# The Discord channel ID where the bot will post opportunities
BOVIE_DISCORD_CHANNEL=your_channel_id_here
```

## Usage

### Running the Discord Bot

To start the Discord bot that automatically posts new opportunities:

```bash
uv run python bovie.py bot
```

### Manual Offer Check

To manually check and display the latest offers in your terminal:

```bash
uv run python bovie.py pull --limit 5  # Adjust number as needed
```

### Available Commands

- `bot`: Start the Discord bot
  - `--limit`: Maximum number of offers to display (default: 50)
  - `--token`: Your Discord bot token
  - `--channel`: The channel ID where the bot will post
- `pull`: Manually check for new offers
  - `--limit`: Maximum number of offers to display (default: 1)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Troubleshooting

### Common Issues

1. "Missing required environment variables"
   - Make sure you've created the `.env` file with all required variables
   - Check that the variables are spelled correctly

2. "Could not find channel"
   - Verify that your bot has access to the specified channel
   - Double-check the channel ID in your `.env` file

3. "Failed to fetch offers"
   - Check your internet connection
   - The Business France website might be temporarily unavailable
