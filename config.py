import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

OBSIDIAN_VAULT = Path(
    os.environ.get(
        "OBSIDIAN_VAULT",
        str(Path.home() / "Library/Mobile Documents/iCloud~md~obsidian/Documents/LLM Vault"),
    )
)
PAPERS_FOLDER = OBSIDIAN_VAULT / "Papers"
TOPICS_FOLDER = OBSIDIAN_VAULT / "Topics"
LENS_FOLDER = OBSIDIAN_VAULT / "Lens"

PDF_STORE = Path(os.environ.get("PDF_STORE", str(Path(__file__).parent / "Papers")))
INBOX_DIR = PDF_STORE / "Inbox"
