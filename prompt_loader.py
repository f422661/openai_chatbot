from functools import lru_cache
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


@lru_cache(maxsize=None)
def load_prompt(filename: str) -> str:
    """Load and cache a prompt stored in the project prompts directory."""
    prompt = (PROMPTS_DIR / filename).read_text(encoding="utf-8").strip()
    if not prompt:
        raise ValueError(f"Prompt file is empty: {filename}")
    return prompt
