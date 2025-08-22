import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Flask secret key
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24))

# Database configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "survey_app")

# Admin bootstrap (optional)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
