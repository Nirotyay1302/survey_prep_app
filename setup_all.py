import os
import subprocess
import sys
import venv

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
REQUIREMENTS_FILE = os.path.join(PROJECT_DIR, "requirements.txt")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")

def run_command(cmd, cwd=None):
    """Run a shell command and stream output."""
    print(f"\n💻 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, shell=True if os.name == "nt" else False)
    if result.returncode != 0:
        print(f"❌ Command failed: {' '.join(cmd)}")
        sys.exit(result.returncode)

def create_virtualenv():
    """Create virtual environment if missing."""
    if not os.path.exists(VENV_DIR):
        print("📦 Creating virtual environment...")
        venv.create(VENV_DIR, with_pip=True)
    else:
        print("✅ Virtual environment already exists.")

def check_or_create_env():
    """Check if .env exists, if not, create it interactively."""
    if os.path.exists(ENV_FILE):
        print("✅ .env file found. Using existing configuration.")
        return
    
    print("⚙ First-time setup: Let's configure your MySQL connection.")
    db_host = input("MySQL Host [localhost]: ") or "localhost"
    db_user = input("MySQL User [root]: ") or "root"
    db_pass = input("MySQL Password: ")
    db_name = input("Database Name [survey_app]: ") or "survey_app"

    with open(ENV_FILE, "w") as f:
        f.write(f"DB_HOST={db_host}\n")
        f.write(f"DB_USER={db_user}\n")
        f.write(f"DB_PASS={db_pass}\n")
        f.write(f"DB_NAME={db_name}\n")
    
    print("✅ .env file created successfully.")

def install_requirements():
    """Remove old packages and install frozen versions."""
    if not os.path.exists(REQUIREMENTS_FILE):
        print("❌ requirements.txt not found!")
        sys.exit(1)

    pip_path = os.path.join(VENV_DIR, "Scripts", "pip.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "pip")

    print("🧹 Removing old packages...")
    freeze_file = os.path.join(PROJECT_DIR, "old_packages.txt")
    with open(freeze_file, "w") as f:
        subprocess.run([pip_path, "freeze"], stdout=f)
    run_command([pip_path, "uninstall", "-y", "-r", freeze_file])
    os.remove(freeze_file)

    print("⬆ Upgrading pip and build tools...")
    run_command([pip_path, "install", "--upgrade", "pip", "setuptools", "wheel"])

    print("📦 Installing frozen dependencies from requirements.txt...")
    run_command([pip_path, "install", "-r", REQUIREMENTS_FILE])

def run_setup_py():
    """Run the database setup script."""
    python_path = os.path.join(VENV_DIR, "Scripts", "python.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "python")
    setup_path = os.path.join(PROJECT_DIR, "setup.py")
    if os.path.exists(setup_path):
        run_command([python_path, setup_path])
    else:
        print("⚠ setup.py not found, skipping DB setup.")

def run_streamlit_app():
    """Start the Streamlit app."""
    streamlit_path = os.path.join(VENV_DIR, "Scripts", "streamlit.exe") if os.name == "nt" else os.path.join(VENV_DIR, "bin", "streamlit")
    app_path = os.path.join(PROJECT_DIR, "app.py")
    run_command([streamlit_path, "run", app_path])

if __name__ == "__main__":
    print("🚀 Starting full setup for Survey Prep App...\n")
    check_or_create_env()
    create_virtualenv()
    install_requirements()
    run_setup_py()
    run_streamlit_app()
