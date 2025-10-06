import sys
import os
import time
import json
import subprocess
from datetime import datetime
import re

# Extend path to include core modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.reflection_engine import run_reflection
from core.utils.logger import save_reflection_to_log
from core.core_memory import update_memory_state
from core.core_memory import DB_PATH as MEMORY_PATH
from reading.system.get_system_context import get_full_system_context
from reading.run_ocr_mac_native import (
    run_ocr_mac_native,
    parse_visible_text,
    reconstruct_text_from_ocr,
    take_timestamped_screenshot,
)
from core.utils.calendar_tools import mark_event_completed
from models.qwen_caller import (
    call_qwen_infer_screen_task,
    call_qwen_now_context,
    call_qwen_confirm_task,
)

# Configuration
PULSE_INTERVAL = 25  # seconds
BASE_DIR = os.path.expanduser("~/Documents/pulse_logs")
INPUT_DIR = os.path.join(BASE_DIR, "screenshots")
ARCHIVE_DIR = os.path.join(INPUT_DIR, "archive")
LOG_PATH = os.path.join(BASE_DIR, "system", "mirror_log.txt")

# Ensure all folders exist
for d in [BASE_DIR, INPUT_DIR, ARCHIVE_DIR, os.path.dirname(LOG_PATH)]:
    os.makedirs(d, exist_ok=True)


def open_platform_url(task_now: dict):
    context = task_now.get("context", {})
    platform = context.get("platform")

    if not platform:
        print("[⚠️] No platform found in context.")
        return

    if not platform.startswith("http"):
        url = f"https://{platform}"
    else:
        url = platform

    script = f"""
    tell application "Google Chrome"
        if not (exists window 1) then make new window
        tell window 1
            make new tab with properties {{URL:"{url}"}}
            set active tab index to (count of tabs)
        end tell
        activate
    end tell
    """

    subprocess.run(["osascript", "-e", script])
    print(f"[🚀] Opened platform: {url}")


def extract_context_from_notes(notes: str) -> dict:
    context = {}
    # Support both newlines AND pipe separators
    parts = re.split(r"\n|\r|\|", notes)
    for part in parts:
        if ":" in part:
            key, value = part.split(":", 1)
            context[key.strip().lower()] = value.strip()
    return context


def get_task_for_now(buffer_minutes=10, calendar_name="Mia"):
    now = datetime.now()
    print(f"[🕒] Now: {now.isoformat()} — Looking for events ±{buffer_minutes} minutes")

    script = f"""
    set output to ""
    tell application "Calendar"
        try
            set theCal to calendar "{calendar_name}"
            set nowDate to current date
            set endDate to nowDate + ({buffer_minutes} * minutes)
            set startDate to nowDate - ({buffer_minutes} * minutes)
            set eventsFound to every event of theCal whose start date ≥ startDate and start date ≤ endDate
            repeat with e in eventsFound
                set eventTitle to summary of e
                set eventTime to start date of e
                set eventNotes to ""
                try
                    set eventNotes to description of e
                end try
                if eventNotes is missing value then
                    set cleanNotes to "empty"
                else
                    set AppleScript's text item delimiters to linefeed
                    set note_items to every text item of eventNotes
                    set AppleScript's text item delimiters to " | "
                    set cleanNotes to note_items as string
                    set AppleScript's text item delimiters to ""
                end if
                set output to output & eventTitle & "||" & cleanNotes & "||" & (eventTime as string) & linefeed
            end repeat
        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
    return output
    """

    try:
        result = subprocess.check_output(["osascript", "-e", script])
        decoded = result.decode("utf-8").strip()
        print(f"[📥] Raw AppleScript output:\n{decoded}\n")
    except subprocess.CalledProcessError as e:
        print(f"[❌] AppleScript error: {e}")
        return None

    if decoded.startswith("ERROR:"):
        print(f"[❌] Calendar access error: {decoded}")
        return None

    for line in decoded.splitlines():
        print(f"[🔎] Checking line: {line}")
        parts = line.split("||")
        if len(parts) != 3:
            print(f"[⚠️] Malformed line: {line}")
            continue

        title, notes, raw_start = [p.strip() for p in parts]

        # ✅ Skip completed tasks
        if "(completed)" in title.lower():
            print(f"[⏭️] Skipping completed task: {title}")
            continue

        try:
            start_time = datetime.strptime(raw_start, "%A, %B %d, %Y at %I:%M:%S %p")
        except ValueError as ve:
            print(f"[⚠️] Date parse failed: {ve} — Raw: {raw_start}")
            continue

        delta = abs((start_time - datetime.now()).total_seconds())
        print(f"[⏱] Time difference: {delta} seconds")

        if delta < buffer_minutes * 60:
            print(f"[✅] Matching event found: {title}")
            return {
                "task": title,
                "context": extract_context_from_notes(notes),
                "due": start_time.isoformat(),
            }

    print("[📭] No matching tasks found.")
    return None


def run_pulse():
    print("[MIA] Pulse started...")
    while True:
        timestamp = datetime.now().isoformat()
        timestamp_safe = timestamp.replace(":", "-")

        # 🖼️ Step 1 – Take screenshot
        image_path = take_timestamped_screenshot(INPUT_DIR)

        # 🧠 Step 2 – OCR-only mode
        print("[🧠] OCR-only mode: vision and Omni disabled.")
        treasure_map = []

        # 🧾 Step 3 – Run OCR (monolith auto-saves JSON)
        ocr_result = run_ocr_mac_native(
            image_path, timestamp=timestamp_safe, is_sprint=False
        )
        ocr_path = os.path.join(
            os.path.expanduser("~/Documents/pulse_logs/ocr"),
            f"ocr_{timestamp_safe}.json",
        )
        symbolic_scene = parse_visible_text(ocr_path)

        reconstructed_lines = reconstruct_text_from_ocr(ocr_result["text_blocks"])
        reconstructed_text = "\n".join(reconstructed_lines)

        now_context, context_verdict = call_qwen_now_context(reconstructed_text)
        print("\n🧠 NOW CONTEXT (Qwen):")
        print(now_context)
        print(f"✅ Context Verdict: {context_verdict}")

        task_guess = call_qwen_infer_screen_task(reconstructed_text)
        print("\n🔍 Qwen Task Guess:")
        print(task_guess)

        system_context = get_full_system_context()
        print(f"🖥️ [SYSTEM] Context: {system_context}")
        system_path = os.path.join(
            os.path.expanduser("~/Documents/pulse_logs/system"),
            f"system_snapshot_{timestamp_safe}.json",
        )
        os.makedirs(os.path.dirname(system_path), exist_ok=True)
        with open(system_path, "w") as f:
            json.dump(system_context, f, indent=2)

        # Save Qwen analysis for Overseer chat
        qwen_analysis = {
            "timestamp": timestamp,
            "now_context": now_context,
            "context_verdict": context_verdict,
            "task_guess": task_guess,
            "reconstructed_text": reconstructed_text[:500],
            "app": system_context.get("app", "unknown"),
        }

        # Save to file for Overseer to read
        qwen_log_path = "reading/qwen_context/latest_analysis.json"
        os.makedirs(os.path.dirname(qwen_log_path), exist_ok=True)
        with open(qwen_log_path, "w") as f:
            json.dump(qwen_analysis, f, indent=2)
        print(f"[💾] Qwen analysis saved for Overseer: {qwen_log_path}")

        print("[📅] Checking Calendar for task...")
        task_now = get_task_for_now()

        if task_now:
            print(f"\n📅 Task Assigned from Calendar:")
            print(task_now)
            print("[🧠] Parsed context:")
            print(task_now["context"])

            confirmation = call_qwen_confirm_task(task_now)
            print(f"🤖 Task Confirmation from Qwen: {confirmation}")

            if not confirmation.get("proceed"):
                print(f"❌ Task skipped: {confirmation.get('reason')}")
                task_now = None
            else:
                print("✅ Proceeding with task.")
                # 🔁 Platform URL will now be opened by Codex step using variable_1
                from action.sprint_agent import ping_pong_loop

                ping_pong_loop(task_now)

        else:
            print(
                "[📭] No calendar task matched or confirmed. Reflection will still run."
            )

        app = system_context.get("app", "unknown")
        ui_words = symbolic_scene.get("text_blocks", [])

        symbolic_input = {
            "screen_summary": f"{app} — {len(ui_words)} OCR lines detected",
            "app": system_context.get("app"),
            "window": system_context.get("window"),
            "apps_open": system_context.get("apps_open"),
            "system_status": system_context.get("system"),
            "visible_text": symbolic_scene.get("text_blocks", []),
            "llm_task_guess": task_guess,
            "now_context": now_context,
            "task_now": task_now,
        }

        reflection_result = run_reflection(json.dumps(symbolic_input, indent=2))
        save_reflection_to_log(timestamp, symbolic_input, LOG_PATH)
        update_memory_state(MEMORY_PATH, symbolic_input, reflection_result)

        if task_now:
            action_log = {
                "timestamp": timestamp,
                "task": {
                    "summary": task_now.get("task"),
                    "context": task_now.get("context"),
                    "due": task_now.get("due"),
                },
                "reflection": "Pending",
            }
            action_log_path = os.path.join(
                os.path.expanduser("~/Documents/pulse_logs/action"),
                f"action_log_{timestamp_safe}.json",
            )
            os.makedirs(os.path.dirname(action_log_path), exist_ok=True)
            with open(action_log_path, "w") as f:
                json.dump(action_log, f, indent=2)
            print(f"📔 Task log saved: {action_log_path}")

            mark_event_completed(task_now["task"], calendar_name="Mia")
            print(f"[✅] Marked event as completed in calendar: {task_now['task']}")

        archived_name = f"{timestamp_safe}_{os.path.basename(image_path)}"
        os.rename(image_path, os.path.join(ARCHIVE_DIR, archived_name))
        print(f"[MIA] Archived: {archived_name}")

        time.sleep(PULSE_INTERVAL)


if __name__ == "__main__":
    print("[⚡] Starting AM Pulse...")
    run_pulse()
