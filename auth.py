import streamlit as st
import bcrypt
from utils.db_mysql import get_connection, create_tables
from mysql.connector import Error

# --- Password Helpers ---
def hash_password(password: str) -> str:
	"""Hash a password using bcrypt and return utf-8 string."""
	return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode('utf-8')

def check_password(password: str, hashed_str: str) -> bool:
	"""Check a password against a utf-8 hashed string."""
	return bcrypt.checkpw(password.encode(), hashed_str.encode('utf-8'))

# --- Database Helpers ---
def create_users_table():
	"""Ensure users table exists with unified schema."""
	try:
		create_tables()
	except Error as e:
		st.sidebar.error(f"Database error: {e}")

def user_exists(username: str, email: str) -> bool:
	"""Check if a user with given username or email exists."""
	try:
		conn = get_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT 1 FROM users WHERE username=%s OR email=%s", (username, email))
		exists = cursor.fetchone() is not None
		cursor.close()
		conn.close()
		return exists
	except Error as e:
		st.sidebar.error(f"Error checking user: {e}")
		return True

def save_user(username: str, email: str, password: str):
	"""Save new user to DB."""
	hashed_pw = hash_password(password)
	try:
		conn = get_connection()
		cursor = conn.cursor()
		cursor.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)", (username, email, hashed_pw, 'user'))
		conn.commit()
		cursor.close()
		conn.close()
	except Error as e:
		st.sidebar.error(f"Error saving user: {e}")

def authenticate_user(username: str, password: str) -> bool:
	"""Check if username/password is valid."""
	try:
		conn = get_connection()
		cursor = conn.cursor()
		cursor.execute("SELECT password FROM users WHERE username=%s", (username,))
		result = cursor.fetchone()
		cursor.close()
		conn.close()
		if result:
			stored_hash = result[0]
			return check_password(password, stored_hash)
		return False
	except Error as e:
		st.sidebar.error(f"Error logging in: {e}")
		return False

# --- Main Auth Function ---
def login_signup():
	st.sidebar.header("Login / Signup")
	mode = st.sidebar.radio("Choose mode", ["Login", "Signup"])
	username = st.sidebar.text_input("Username")
	password = st.sidebar.text_input("Password", type="password")

	create_users_table()  # Ensure tables exist

	if mode == "Signup":
		email = st.sidebar.text_input("Email")
		if st.sidebar.button("Create Account"):
			if username and password and email:
				if user_exists(username, email):
					st.sidebar.error("Username or email already exists.")
				else:
					save_user(username, email, password)
					st.sidebar.success("Account created! Please login.")
			else:
				st.sidebar.warning("Please enter username, email and password.")

	elif mode == "Login":
		if st.sidebar.button("Login"):
			if authenticate_user(username, password):
				st.session_state['logged_in'] = True
				st.session_state['username'] = username
				st.sidebar.success(f"Welcome, {username}!")
			else:
				st.sidebar.error("Invalid credentials.")

	return st.session_state.get('logged_in', False)
