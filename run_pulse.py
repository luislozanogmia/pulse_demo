import os, time, subprocess, requests
from core.pulse import run_pulse


def ensure_ollama():
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        print("✅ Ollama already running.")
    except Exception:
        print("🚀 Starting Ollama server...")
        subprocess.Popen(["ollama", "serve"])
        for _ in range(10):
            try:
                requests.get("http://localhost:11434/api/tags", timeout=2)
                print("✅ Ollama is ready.")
                return
            except Exception:
                time.sleep(1)
        print("❌ Could not start Ollama.")


if __name__ == "__main__":
    ensure_ollama()
    run_pulse()
