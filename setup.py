# setup.py
import os
from utils.db_mysql import create_database, create_tables, get_connection
from dotenv import load_dotenv
from mysql.connector import Error

def main():
    load_dotenv()
    print("🔍 Checking MySQL connection...")

    try:
        # Test connection (without DB creation)
        conn = get_connection(create_db_if_missing=False)
        if conn.is_connected():
            print(f"✅ Connected to MySQL server at {os.getenv('DB_HOST')}")
            conn.close()
    except Error:
        print("⚠ Could not connect to the database. Trying to create it...")
        create_database()

    print("📦 Creating tables if missing...")
    create_tables()

    print("🎉 Setup complete! You can now run:")
    print("    streamlit run app.py")

if __name__ == "__main__":
    main()
