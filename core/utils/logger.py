import os


def save_reflection_to_log(timestamp: str, input_text: str, log_path: str):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    log_entry = f"""
🪞 Pulse Log
Timestamp: {timestamp}
Input: {input_text}
──────────────────────────────────────
"""

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry)
