import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the .env file from the backend folder
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Server Configuration
FLASK_PORT = int(os.getenv("FLASK_PORT", 5000))
FLASK_ENV = os.getenv("FLASK_ENV", "development")

# Supabase Credentials (Loaded securely from environment variables)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

# Supabase Client Initialization
supabase_client = None

if SUPABASE_URL and SUPABASE_KEY and not SUPABASE_URL.startswith("your-"):
    try:
        from supabase import create_client, Client
        supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[INFO] Supabase client initialized successfully connected to cloud database.")
    except Exception as e:
        print(f"[WARNING] Failed to initialize Supabase client: {e}")
        supabase_client = None
else:
    print("[INFO] Supabase credentials not set or using placeholders.")


def get_supabase_client():
    """
    Returns the initialized Supabase client.
    Raises RuntimeError if credentials are not configured yet.
    """
    if supabase_client is None:
        raise RuntimeError(
            "Supabase client is not configured. Please ensure SUPABASE_URL and "
            "SUPABASE_KEY are set in backend/.env."
        )
    return supabase_client
