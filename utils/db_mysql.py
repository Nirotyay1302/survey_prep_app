import mysql.connector
from mysql.connector import errorcode, Error
from dotenv import load_dotenv
import os
from urllib.parse import urlparse

# Load environment variables
load_dotenv()

# Check if DATABASE_URL is available (Railway style)
DATABASE_URL = os.getenv("DATABASE_URL")

# Debug: Print all environment variables
print(f"DEBUG: All environment variables:")
for key, value in os.environ.items():
    if 'DB' in key or 'DATABASE' in key or 'MYSQL' in key:
        print(f"DEBUG: {key} = {value}")

print(f"DEBUG: DATABASE_URL = {DATABASE_URL}")

# TEMPORARY: Force Railway connection if DATABASE_URL is not set
if not DATABASE_URL:
    DATABASE_URL = "mysql://root:iRupakyOogdPMNvyfMWsWkmBFTJbFdRi@shinkansen.proxy.rlwy.net:47372/railway"
    print(f"DEBUG: Using hardcoded Railway connection as fallback")

if DATABASE_URL:
    # Parse DATABASE_URL (mysql://user:pass@host:port/db)
    parsed = urlparse(DATABASE_URL)
    DB_HOST = parsed.hostname
    DB_PORT = parsed.port or 3306
    DB_USER = parsed.username
    DB_PASS = parsed.password
    DB_NAME = parsed.path.lstrip('/')
    DB_SSL_DISABLED = False  # Railway handles SSL
    DB_SSL_CA = None
    print(f"DEBUG: Parsed from DATABASE_URL - Host: {DB_HOST}, Port: {DB_PORT}, User: {DB_USER}, DB: {DB_NAME}")
else:
    # Fallback to individual environment variables
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASS = os.getenv("DB_PASS", "")  # set via .env; avoid hardcoded default
    DB_NAME = os.getenv("DB_NAME", "survey_app")
    DB_SSL_DISABLED = os.getenv("DB_SSL_DISABLED", "false").lower() in ("1", "true", "yes")
    DB_SSL_CA = os.getenv("DB_SSL_CA")  # optional absolute path to CA cert if provider requires
    print(f"DEBUG: Using individual variables - Host: {DB_HOST}, Port: {DB_PORT}, User: {DB_USER}, DB: {DB_NAME}")

# --- Connection ---
def get_connection(create_db_if_missing=True):
    """Get MySQL connection, optionally creating DB if missing."""
    try:
        # Debug: Print connection parameters
        print(f"DEBUG: Attempting to connect to MySQL")
        print(f"DEBUG: DATABASE_URL exists: {bool(DATABASE_URL)}")
        print(f"DEBUG: DB_HOST: {DB_HOST}")
        print(f"DEBUG: DB_PORT: {DB_PORT}")
        print(f"DEBUG: DB_USER: {DB_USER}")
        print(f"DEBUG: DB_NAME: {DB_NAME}")
        
        connect_kwargs = {
            "host": DB_HOST,
            "port": DB_PORT,
            "user": DB_USER,
            "password": DB_PASS,
            "database": DB_NAME,
            "connection_timeout": 10,
        }
        # Optional SSL config for managed MySQL providers
        if not DB_SSL_DISABLED and DB_SSL_CA:
            connect_kwargs["ssl_ca"] = DB_SSL_CA
            connect_kwargs["ssl_verify_cert"] = True
        conn = mysql.connector.connect(**connect_kwargs)
        return conn
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_BAD_DB_ERROR and create_db_if_missing:
            create_database()
            return get_connection(create_db_if_missing=False)
        else:
            raise

# --- Database & Tables ---
def create_database():
    """Create the database if it doesn't exist."""
    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS
    )
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
    conn.commit()
    cursor.close()
    conn.close()
    create_tables()

def create_tables():
    """Create all required tables."""
    conn = get_connection(create_db_if_missing=False)
    cursor = conn.cursor()

    # Table for storing user accounts
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) UNIQUE,
            email VARCHAR(255) UNIQUE,
            password VARCHAR(255),
            role ENUM('user','admin') DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Table for storing processing jobs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processing_jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100),
            uploaded_filename VARCHAR(255),
            rows_before INT,
            rows_after INT,
            impute_method VARCHAR(50),
            outlier_method VARCHAR(50),
            weight_col VARCHAR(100),
            violations_count INT DEFAULT 0,
            display_name VARCHAR(255),
            is_saved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()

# --- Status Report ---
def check_environment_status():
    """Return a dictionary of environment and DB status."""
    status = {
        "env_file": os.path.exists(".env"),
        "db_connected": False,
        "users_table": False,
        "processing_jobs_table": False,
        "error": None
    }

    # Check DB connection
    try:
        conn = get_connection()
        status["db_connected"] = True

        # Check tables
        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'users'")
        status["users_table"] = cursor.fetchone() is not None

        cursor.execute("SHOW TABLES LIKE 'processing_jobs'")
        status["processing_jobs_table"] = cursor.fetchone() is not None

        cursor.close()
        conn.close()
    except Error as e:
        status["error"] = str(e)

    return status

# --- Processing Jobs Functions ---
def save_job(username, uploaded_filename, rows_before, rows_after, 
             impute_method, outlier_method, weight_col, violations_count=0):
    """Save a new processing job."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO processing_jobs 
        (username, uploaded_filename, rows_before, rows_after, 
         impute_method, outlier_method, weight_col, violations_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (username, uploaded_filename, rows_before, rows_after, 
          impute_method, outlier_method, weight_col, violations_count))
    conn.commit()
    job_id = cursor.lastrowid
    cursor.close()
    conn.close()
    return job_id

def get_user_jobs(username):
    """Get all jobs for a user."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM processing_jobs 
        WHERE username = %s 
        ORDER BY created_at DESC
    """, (username,))
    jobs = cursor.fetchall()
    cursor.close()
    conn.close()
    return jobs

def get_job_by_id(job_id):
    """Get a specific job by ID."""
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM processing_jobs WHERE id = %s", (job_id,))
    job = cursor.fetchone()
    cursor.close()
    conn.close()
    return job

def delete_job_by_id(job_id, username):
    """Delete a job by ID (only if owned by user)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM processing_jobs 
        WHERE id = %s AND username = %s
    """, (job_id, username))
    deleted = cursor.rowcount > 0
    conn.commit()
    cursor.close()
    conn.close()
    return deleted
