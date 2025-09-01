# NFT Telegram Bot

A comprehensive NFT-focused Telegram bot built with Python using the `python-telegram-bot` library. This bot provides real-time NFT collection data, price tracking, rankings, and alert management.

## Features

### Core NFT Commands
- **`/price <collection>`** - Get real-time floor price and collection statistics
- **`/rankings`** - View top NFT collections by 24h volume
- **`/alerts`** - Manage price alerts for NFT collections

**Note:** The `/top_sales` command is temporarily deactivated.

### Additional Features
- **Real-time Data**: Integration with NFTPriceFloor API for live NFT data
- **Pagination Support**: Browse through extensive NFT rankings with next/previous buttons
- **Error Handling**: Comprehensive error handling and logging
- **Clean Code**: PEP 8 compliant code with proper documentation
- **Async Support**: Built with async/await for better performance
- **Outbound Linking**: Direct links to OpenSea collections

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- A Telegram Bot Token from [@BotFather](https://t.me/botfather)

### Installation

1. **Clone or download this project**

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure your bot token**:
   - Open `bot.py`
   - Replace the BOT_TOKEN with your actual bot token from BotFather

5. **Run the bot**:
   ```bash
   python bot.py
   ```

## Usage

Once the bot is running, you can interact with it on Telegram:

### Basic Commands
- `/start` - Get a welcome message
- `/help` - View available commands and usage instructions

### NFT Commands
- `/price cryptopunks` - Get CryptoPunks floor price and stats
- `/price bored-ape-yacht-club` - Get BAYC collection data
- `/rankings` - View top 10 NFT collections by volume
- `/alerts` - View alert management options
- `/alerts add cryptopunks 50` - Set price alert for CryptoPunks at 50 ETH
- `/alerts list` - View your active alerts
- `/alerts remove <id>` - Remove a specific alert
- `/top_sales` - View recent high-value NFT sales

## Project Structure

```
telegram_bot/
├── bot.py              # Main bot implementation with NFT commands
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Dependencies

- `python-telegram-bot==20.3` - Telegram Bot API wrapper
- `aiohttp==3.9.1` - Async HTTP client for API requests

## API Integration

### NFTPriceFloor API
The bot integrates with NFTPriceFloor API via RapidAPI using specific endpoints:
- **`/projects/{slug}`** - Detailed project data for /price command
- **`/projects-v2`** - Collection rankings for /rankings command  
- **`/projects/top-sales`** - Recent sales data for /top_sales command

Provides:
- Real-time floor prices in ETH
- Market capitalization data
- Trading volume statistics
- Collection supply information
- Top NFT sales data

**Rate Limits:** Based on RapidAPI subscription tier
**Data Updates:** Real-time data from multiple NFT marketplaces

### Features by Command

#### `/price` Command
- Searches for NFT collections by name
- Displays floor price in ETH and USD
- Shows 24h volume and market cap
- Provides direct OpenSea links

#### `/rankings` Command
- Lists top 10 NFT collections by market cap with pagination
- Shows volume in formatted currency
- Displays floor price changes
- Click "Next 10 Collections" to see more results
- Updates hourly

#### `/alerts` Command
- Price alert management system
- Add/remove/list functionality
- Demo implementation with expansion ready

#### `/top_sales` Command
- Shows recent high-value NFT sales from NFTPriceFloor API
- Displays sale price in ETH and USD
- Shows buyer wallet addresses (truncated for privacy)
- Includes sale timestamps when available
- Real-time data from multiple marketplaces

## Development

### Code Style

This project follows PEP 8 guidelines. The code includes:

- Proper docstrings for all functions
- Type hints where appropriate
- Comprehensive error handling
- Structured logging
- Async/await patterns for API calls

### Adding New Commands

To add a new NFT command:

1. Create an async function for your command handler
2. Add API integration if needed
3. Add the handler to the application in the `main()` function
4. Update the help text in the `help_command()` function

### API Rate Limiting

The bot implements proper error handling for API rate limits and failures. Consider implementing caching for production use.

## Troubleshooting

### Common Issues

1. **"Invalid token" error**: Make sure you've correctly set your bot token
2. **Import errors**: Ensure all dependencies are installed in your virtual environment
3. **API errors**: Check internet connection and API availability
4. **Permission errors**: Make sure the bot has necessary permissions in your Telegram chat

### Logs

The bot logs important events and errors. Check the console output for debugging information including:
- API request status
- User command usage
- Error details

## Future Enhancements

- Database integration for persistent alerts
- Real-time sales data from multiple marketplaces
- Portfolio tracking functionality
- Advanced analytics and charts
- Multi-chain NFT support

## License

This project is open source and available under the MIT License.