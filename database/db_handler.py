import os
import mysql.connector
from mysql.connector import errorcode
from mysql.connector.pooling import MySQLConnectionPool
from mysql.connector import errors as mysql_errors
import bcrypt

from config import DB_HOST, DB_USER, DB_PASS, DB_NAME, ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD


_POOL = None
_POOL_NAME = "survey_pool"
_POOL_SIZE = int(os.environ.get("DB_POOL_SIZE", "25"))


def _init_pool():
	global _POOL
	_POOL = MySQLConnectionPool(
		pool_name=_POOL_NAME,
		pool_size=_POOL_SIZE,
		host=DB_HOST,
		user=DB_USER,
		password=DB_PASS,
		database=DB_NAME,
		pool_reset_session=True,
		connection_timeout=10
	)


def _direct_connect():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        connection_timeout=10
    )


def get_connection(create_db_if_missing: bool = True) -> mysql.connector.MySQLConnection:
    global _POOL
    # Optional escape hatch to disable pooling via env
    if os.environ.get("DB_POOL_DISABLED", "1") == "1":
        return _direct_connect()

    try:
        if _POOL is None:
            _init_pool()
        return _POOL.get_connection()
    except Exception as err:
        # If pool is exhausted/closed or any pooling issue, retry by reinitializing
        message = str(err).lower()
        if isinstance(err, (mysql_errors.PoolError,)) or "pool" in message:
            try:
                _init_pool()
                return _POOL.get_connection()
            except Exception:
                return _direct_connect()
        # Handle missing DB
        if isinstance(err, mysql.connector.Error) and getattr(err, "errno", None) == errorcode.ER_BAD_DB_ERROR and create_db_if_missing:
            _create_database()
            return get_connection(create_db_if_missing=False)
        raise


def _create_database():
	conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS)
	cursor = conn.cursor()
	cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME}")
	conn.commit()
	cursor.close()
	conn.close()
	create_tables()


def _column_exists(cursor, table: str, column: str) -> bool:
	cursor.execute("SHOW COLUMNS FROM %s LIKE %s", (table, column))
	return cursor.fetchone() is not None


def _index_exists(cursor, table: str, index_name: str) -> bool:
	cursor.execute("SHOW INDEX FROM %s WHERE Key_name=%s", (table, index_name))
	result = cursor.fetchone()
	return result is not None


def create_tables():
	"""Create all required tables if they don't exist."""
	conn = None
	cursor = None
	try:
		conn = get_connection()
		cursor = conn.cursor(buffered=True)
		
		# Users table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS users (
				id INT AUTO_INCREMENT PRIMARY KEY,
				username VARCHAR(100) UNIQUE NOT NULL,
				email VARCHAR(255) UNIQUE NOT NULL,
				password VARCHAR(255) NOT NULL,
				role ENUM('user', 'admin') DEFAULT 'user',
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
			)
		""")
		
		# Audit logs table
		cursor.execute("""
			CREATE TABLE IF NOT EXISTS audit_logs (
				id INT AUTO_INCREMENT PRIMARY KEY,
				username VARCHAR(100) NOT NULL,
				uploaded_filename VARCHAR(255),
				params_json TEXT,
				rows_before INT,
				rows_after INT,
				violations_count INT DEFAULT 0,
				created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
				stored_path VARCHAR(512),
				is_saved BOOLEAN DEFAULT FALSE,
				display_name VARCHAR(255)
			)
		""")
		
		# Check if display_name column exists, add if missing
		cursor.execute("SHOW COLUMNS FROM audit_logs LIKE 'display_name'")
		result = cursor.fetchone()
		if not result:
			cursor.execute("ALTER TABLE audit_logs ADD COLUMN display_name VARCHAR(255)")
			print("Added display_name column to audit_logs table")
		
		# Check if is_saved column exists, add if missing
		cursor.execute("SHOW COLUMNS FROM audit_logs LIKE 'is_saved'")
		result = cursor.fetchone()
		if not result:
			cursor.execute("ALTER TABLE audit_logs ADD COLUMN is_saved BOOLEAN DEFAULT FALSE")
			print("Added is_saved column to audit_logs table")
		
		# Create indexes for better performance
		cursor.execute("SHOW INDEX FROM audit_logs WHERE Key_name = 'idx_audit_user_time'")
		result = cursor.fetchone()
		if not result:
			cursor.execute("CREATE INDEX idx_audit_user_time ON audit_logs(username, created_at)")
			print("Created index idx_audit_user_time")
		
		cursor.execute("SHOW INDEX FROM audit_logs WHERE Key_name = 'idx_audit_time'")
		result = cursor.fetchone()
		if not result:
			cursor.execute("CREATE INDEX idx_audit_time ON audit_logs(created_at)")
			print("Created index idx_audit_time")
		
		cursor.execute("SHOW INDEX FROM audit_logs WHERE Key_name = 'idx_audit_saved'")
		result = cursor.fetchone()
		if not result:
			cursor.execute("CREATE INDEX idx_audit_saved ON audit_logs(is_saved)")
			print("Created index idx_audit_saved")
		
		conn.commit()
		print("Tables created/updated successfully")
		return True
		
	except Exception as e:
		print(f"Error creating tables: {e}")
		return False
	finally:
		try:
			if cursor:
				cursor.close()
		except Exception:
			pass
		try:
			if conn:
				conn.close()
		except Exception:
			pass


def bootstrap_admin():
	"""Ensure a default admin exists."""
	conn = None
	cursor = None
	try:
		conn = get_connection()
		cursor = conn.cursor(buffered=True)
		cursor.execute("SELECT id FROM users WHERE username=%s", (ADMIN_USERNAME,))
		exists = cursor.fetchone()
		if not exists:
			hashed = bcrypt.hashpw(ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
			cursor.execute(
				"INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
				(ADMIN_USERNAME, ADMIN_EMAIL, hashed, 'admin')
			)
			conn.commit()
			print(f"Created admin user: {ADMIN_USERNAME}")
		else:
			print(f"Admin user {ADMIN_USERNAME} already exists")
	except Exception as e:
		print(f"Error bootstrapping admin: {e}")
	finally:
		try:
			if cursor:
				cursor.close()
		except Exception:
			pass
		try:
			if conn:
				conn.close()
		except Exception:
			pass
