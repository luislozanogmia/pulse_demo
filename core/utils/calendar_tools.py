import subprocess


def mark_event_completed(event_title, calendar_name="Mia"):
    if "(completed)" in event_title.lower():
        return  # Already marked as done

    new_title = f"{event_title.strip()} (completed)"
    apple_script = f"""
    tell application "Calendar"
        tell calendar "{calendar_name}"
            set theEvent to first event whose summary is "{event_title}"
            set summary of theEvent to "{new_title}"
        end tell
    end tell
    """
    subprocess.run(["osascript", "-e", apple_script])
