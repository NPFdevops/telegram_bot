# Heroku Deployment Guide

This guide will help you deploy the NFT Telegram Bot to Heroku cloud platform.

## Prerequisites

1. **Heroku Account**: Sign up at [heroku.com](https://heroku.com)
2. **Heroku CLI**: Install from [devcenter.heroku.com/articles/heroku-cli](https://devcenter.heroku.com/articles/heroku-cli)
3. **Git**: Ensure Git is installed on your system
4. **Telegram Bot Token**: Get from [@BotFather](https://t.me/botfather)
5. **NFTPriceFloor API Key**: Get from [RapidAPI](https://rapidapi.com/)

## Quick Deploy

### Option 1: Deploy to Heroku Button

[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://heroku.com/deploy)

### Option 2: Manual Deployment

1. **Clone and prepare the repository**:
   ```bash
   git clone <your-repo-url>
   cd telegram_bot
   ```

2. **Login to Heroku**:
   ```bash
   heroku login
   ```

3. **Create a new Heroku app**:
   ```bash
   heroku create your-bot-name
   ```

4. **Set environment variables**:
   ```bash
   heroku config:set BOT_TOKEN="your_telegram_bot_token"
   heroku config:set NFTPF_API_KEY="your_nftpf_api_key"
   heroku config:set HEROKU_APP_NAME="your-bot-name"
   ```

5. **Deploy the application**:
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push heroku main
   ```

6. **Scale the worker dyno**:
   ```bash
   heroku ps:scale worker=1
   ```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `BOT_TOKEN` | Yes | Your Telegram bot token from @BotFather |
| `NFTPF_API_KEY` | Yes | Your NFTPriceFloor API key from RapidAPI |
| `HEROKU_APP_NAME` | Yes | Your Heroku app name (for webhook URL) |
| `NFTPF_API_HOST` | No | NFTPriceFloor API host (default: nftpf-api-v0.p.rapidapi.com) |
| `OPENSEA_API_URL` | No | OpenSea API URL (default: https://api.opensea.io/api/v1) |

## Configuration Files

The following files are configured for Heroku deployment:

- **`Procfile`**: Defines how to start the application
- **`runtime.txt`**: Specifies Python version
- **`requirements.txt`**: Lists Python dependencies
- **`app.json`**: Heroku app metadata and configuration
- **`.env.example`**: Template for environment variables

## Webhook vs Polling

The bot automatically detects the deployment environment:

- **Heroku (Webhook Mode)**: When `HEROKU_APP_NAME` is set, the bot uses webhooks for better performance and reliability
- **Local (Polling Mode)**: When `HEROKU_APP_NAME` is not set, the bot uses polling for development

## Scaling Options

### Free Tier (Eco Dynos)
```bash
heroku ps:scale worker=1
```

### Paid Tiers
```bash
# Basic dyno
heroku ps:type worker=basic

# Standard dyno
heroku ps:type worker=standard-1x
```

## Monitoring and Logs

### View logs
```bash
heroku logs --tail
```

### Check dyno status
```bash
heroku ps
```

### Monitor app metrics
```bash
heroku open
```

## Troubleshooting

### Common Issues

1. **Bot not responding**:
   - Check if worker dyno is running: `heroku ps`
   - Verify environment variables: `heroku config`
   - Check logs: `heroku logs --tail`

2. **Environment variable errors**:
   ```bash
   heroku config:set VARIABLE_NAME="value"
   ```

3. **Deployment failures**:
   - Ensure all files are committed to Git
   - Check Python version compatibility
   - Verify requirements.txt syntax

4. **Webhook issues**:
   - Ensure `HEROKU_APP_NAME` matches your actual app name
   - Check if app is accessible via HTTPS

### Debug Commands

```bash
# Check app info
heroku info

# View configuration
heroku config

# Restart app
heroku restart

# Run one-off commands
heroku run python --version
```

## Security Best Practices

1. **Never commit sensitive data**:
   - Add `.env` to `.gitignore`
   - Use environment variables for all secrets

2. **Regularly rotate API keys**:
   - Update bot token if compromised
   - Regenerate API keys periodically

3. **Monitor usage**:
   - Check Heroku metrics dashboard
   - Monitor API usage limits

## Cost Optimization

1. **Use Eco dynos** for development and low-traffic bots
2. **Monitor dyno hours** to stay within free tier limits
3. **Consider upgrading** for production use with high traffic

## Support

If you encounter issues:

1. Check the [Heroku documentation](https://devcenter.heroku.com/)
2. Review bot logs for error messages
3. Verify all environment variables are set correctly
4. Ensure your Telegram bot token is valid

## Next Steps

After successful deployment:

1. Test all bot commands
2. Set up monitoring and alerts
3. Configure any additional features
4. Share your bot with users

Your NFT Telegram Bot is now running on Heroku! 🚀