"""
Configuration module for Deg Bot
Loads environment variables and provides configuration constants
"""
import os
from dotenv import load_dotenv
import pytz

# Load environment variables
load_dotenv()

# Discord Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', 0))
COACH_ROLE_ID = int(os.getenv('COACH_ROLE_ID', 0))
STUDENT_ROLE_ID = int(os.getenv('STUDENT_ROLE_ID', 0))
TICKET_CATEGORY_ID = int(os.getenv('TICKET_CATEGORY_ID', 0))
ANNOUNCEMENT_CHANNEL_ID = int(os.getenv('ANNOUNCEMENT_CHANNEL_ID', 0))
FEEDBACK_CHANNEL_ID = int(os.getenv('FEEDBACK_CHANNEL_ID', 0))
LOG_CHANNEL_ID = int(os.getenv('LOG_CHANNEL_ID', 0))

# Google Calendar Configuration
GOOGLE_CALENDAR_ID = os.getenv('GOOGLE_CALENDAR_ID')
GOOGLE_CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', './credentials.json')

# Bot Settings
BOOKING_SLOT_DURATION = int(os.getenv('BOOKING_SLOT_DURATION', 60))
TIMEZONE = pytz.timezone(os.getenv('TIMEZONE', 'Europe/Paris'))
FREE_COACHING_DURATION = int(os.getenv('FREE_COACHING_DURATION', 60))
PAID_COACHING_DURATION = int(os.getenv('PAID_COACHING_DURATION', 60))
REMINDER_24H_ENABLED = os.getenv('REMINDER_24H_ENABLED', 'true').lower() == 'true'
REMINDER_1H_ENABLED = os.getenv('REMINDER_1H_ENABLED', 'true').lower() == 'true'

# Database Configuration
DATABASE_URL = 'sqlite:///deg_bot.db'

# Bot Constants
BOT_PREFIX = '/'
BOT_COLOR = 0x5865F2  # Discord Blurple
SUCCESS_COLOR = 0x57F287  # Green
ERROR_COLOR = 0xED4245  # Red
WARNING_COLOR = 0xFEE75C  # Yellow

# Ticket Settings
TICKET_NAME_FORMAT = "ticket-{username}-{number}"
TICKET_AUTO_CLOSE_MINUTES = 30

# Booking Types
BOOKING_TYPE_FREE = "gratuit"
BOOKING_TYPE_PAID = "payant"

# Booking Status
STATUS_CONFIRMED = "confirmed"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"
STATUS_NO_SHOW = "no_show"

# Validation
def validate_config():
    """Validate that all required configuration is set"""
    errors = []

    if not DISCORD_TOKEN:
        errors.append("DISCORD_TOKEN is not set")
    if not GUILD_ID:
        errors.append("GUILD_ID is not set")
    if not GOOGLE_CALENDAR_ID:
        errors.append("GOOGLE_CALENDAR_ID is not set")

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"- {e}" for e in errors))

if __name__ == "__main__":
    try:
        validate_config()
        print("Configuration is valid!")
    except ValueError as e:
        print(e)
