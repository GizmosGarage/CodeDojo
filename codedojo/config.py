import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024
SOLUTION_FILE = Path.cwd() / "solution.py"
TIMEOUT_SECONDS = 10
BELT_EXAM_DAILY_LIMIT = 3
BELT_EXAM_CHALLENGES_PER_EXAM = 3
DATA_DIR = Path(__file__).parent / "data"
LOG_FILE = DATA_DIR / "session_log.jsonl"
PROGRESS_FILE = DATA_DIR / "progress.json"
INTERRUPTED_CHALLENGE_FILE = DATA_DIR / "interrupted_challenge.json"
BELT_EXAM_FILE = DATA_DIR / "belt_exam.json"
KNOWLEDGE_MODEL_FILE = DATA_DIR / "knowledge_model.pt"

# Max messages kept in session history (user+assistant pairs); trims oldest turns first.
CONVERSATION_MAX_MESSAGES = 40


def validate_config():
    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-api-key-here":
        print("Error: ANTHROPIC_API_KEY is not set.")
        print("Add your API key to the .env file in the project root:")
        print("  ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)
