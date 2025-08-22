from typing import Optional, Tuple
import bcrypt
from database.db_handler import get_connection


def find_user_by_username(username: str) -> Optional[Tuple]:
	conn = get_connection()
	cursor = conn.cursor(dictionary=True)
	cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
	user = cursor.fetchone()
	cursor.close()
	conn.close()
	return user


def create_user(username: str, email: str, password: str, role: str = 'user') -> None:
	hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
	conn = get_connection()
	cursor = conn.cursor()
	cursor.execute(
		"INSERT INTO users (username, email, password, role) VALUES (%s,%s,%s,%s)",
		(username, email, hashed, role)
	)
	conn.commit()
	cursor.close()
	conn.close()
