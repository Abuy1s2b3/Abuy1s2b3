import os

# Telegram Bot Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')  # Get token from environment variables
CHANNEL_LINK = os.environ.get('CHANNEL_LINK', 'https://t.me/your_channel')  # Your channel invite link
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@your_channel_id')  # Your channel ID or username

# File Settings
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB max file size
ALLOWED_FORMATS = ['.jpg', '.jpeg', '.png']
TEMP_DIR = "temp"

# Create temp directory if it doesn't exist
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)
