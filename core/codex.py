import os
import json
import unicodedata
from difflib import SequenceMatcher


def clean_text(text):
    if not text:
        return ""
    return (
        unicodedata.normalize("NFKD", text.lower().strip())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def load_codex(platform=None):
    """
    Load symbolic UI Codex for a given platform (e.g., www.gmail.com).
    Converts platform to 'codex/Gmail/gmail_codex.json'
    """
    if platform:
        platform_id = (
            platform.lower().replace("https://", "").replace("www.", "").split(".")[0]
        )
        path = f"codex/{platform_id.capitalize()}/{platform_id}_codex.json"
    else:
        path = "codex/Gmail/gmail_codex.json"  # fallback default

    if not os.path.exists(path):
        raise FileNotFoundError(f"[❌] Codex not found at: {path}")

    with open(path, "r") as f:
        raw = json.load(f)

    codex = []
    for item in raw:
        entry = {
            "name": item["name"],
            "action": item["action"],
            "match": clean_text(item["name"]),
        }
        codex.append(entry)
    return codex


def filter_ui_words(ui_words, codex):
    """
    Match UI words (from OCR) to symbolic Codex entries.
    """
    matched = []
    for word in ui_words:
        word_clean = clean_text(word)
        for item in codex:
            codex_clean = item["match"]
            if codex_clean == word_clean:
                matched.append(item)
            elif similar(codex_clean, word_clean) > 0.8:
                matched.append(item)
    return matched
