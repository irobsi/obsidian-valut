import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set in the .env file! Please add it.")

ALLOWED_USER_IDS = [7747086163, 1994789266, 6605229065]

PAGE_SIZE = 10
SEARCH_PAGE_SIZE = 10
