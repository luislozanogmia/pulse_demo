import subprocess
from datetime import datetime


def extract_context_from_notes(notes: str) -> dict:
    """
    Parses structured notes from calendar into symbolic context.
    Recognizes fields like sender, intent, email, platform, notes.
    Appends unrecognized lines to notes.
    """
    fields = {
        "sender": "Mia",
        "intent": "",
        "platform": "",
        "email": "",
        "task_name": "",
        "variable_1": "",
        "variable_2": "",
        "variable_3": "",
        "variable_4": "",
        "excel_file": "",
        "start_row": "",
        "notes": "",
    }

    for line in notes.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in fields:
                fields[key] = value
            else:
                fields["notes"] += f"{key.capitalize()}: {value}. "
        elif "www." in line or "http" in line:
            fields["platform"] = line.strip()

    return fields


def compress_context(ctx: dict, limit=300) -> dict:
    compressed = {}
    for k, v in ctx.items():
        if isinstance(v, str) and len(v) > limit:
            compressed[k] = v[: limit - 3] + "..."
        else:
            compressed[k] = v
    return compressed


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
                try
                    set eventNotes to description of e as string
                on error
                    set eventNotes to "empty"
                end try
                set output to output & eventTitle & "||" & (eventTime as string) & "||" & eventNotes & linefeed
            end repeat
        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
    return output
    """

    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=5
        )
        output = result.stdout.strip()
        print("[📥] Raw AppleScript output:")
        print(output)
    except Exception as e:
        print(f"[❌] Subprocess error: {e}")
        return None

    if not output or output.startswith("ERROR:"):
        print(f"[❌] Calendar access failed: {output}")
        return None

    for line in output.splitlines():
        try:
            title, dt_str, notes = line.split("||")
            dt_str = dt_str.strip()
            try:
                dt = datetime.strptime(dt_str, "%A, %B %d, %Y at %I:%M:%S %p")
            except ValueError:
                dt = datetime.strptime(dt_str, "%a %b %d %H:%M:%S %Y")

            delta = abs((now - dt).total_seconds())
            if delta <= buffer_minutes * 60:
                raw_ctx = extract_context_from_notes(notes)
                return {
                    "task": title.strip(),
                    "context": compress_context(raw_ctx),
                    "due": dt.isoformat(),
                }
        except Exception as e:
            print(f"[⚠️] Parsing error: {e} in line: {line}")
            continue

    print("[📭] No matching tasks found.")
    return None
