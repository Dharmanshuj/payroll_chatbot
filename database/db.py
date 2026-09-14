import psycopg2
import os
from dotenv import load_dotenv
load_dotenv()
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASS"), # Matches the .env file
        dbname=os.getenv("DB_NAME", "company"),
        sslmode=os.getenv("DB_SSLMODE", "prefer")  # Neon requires "require"
    )