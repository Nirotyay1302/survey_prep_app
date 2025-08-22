import mysql.connector

def get_connection(db=None):
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="@tojo1234",  # Change this!
        database=db if db else None
    )

# Step 1: Connect without database and create the database if it doesn't exist
conn = get_connection()
cursor = conn.cursor()
cursor.execute("CREATE DATABASE IF NOT EXISTS survey_app")
cursor.close()
conn.close()

# Step 2: Connect to the new database and create the tables
conn = get_connection(db="survey_app")
cursor = conn.cursor()

# Create users table
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

# Create processing_jobs table for survey data processing
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
print("✅ Database and tables setup complete!")