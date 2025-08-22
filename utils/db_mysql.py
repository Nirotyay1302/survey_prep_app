import mysql.connector
from mysql.connector import errorcode, Error
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")  # set via .env; avoid hardcoded default
DB_NAME = os.getenv("DB_NAME", "survey_app")

# --- Connection ---
def get_connection(create_db_if_missing=True):
    """Get MySQL connection, optionally creating DB if missing."""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME
        )
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
