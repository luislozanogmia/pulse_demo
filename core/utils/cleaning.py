import re
import unicodedata
from textblob import TextBlob
from datetime import datetime


def fix_simple_typos(text):
    return str(TextBlob(text).correct())


def extract_and_clean_llm_output(raw: str, step_name: str, task_context: dict) -> str:
    """
    Applies full post-processing to any LLM output given a step_name and task context:
    - Extracts quoted or block text
    - Removes 'Subject:' or 'Body:' labels based on step_name
    - Drops leftover subject line from body if present
    - Replaces placeholders like {EMAIL}, {PLATFORM}, {INTENT}
    """
    step_name = step_name.strip().lower()
    raw = raw.strip()
    output = extract_quoted_text(raw)

    # Normalize label removal
    output_lower = output.lower()
    if "subject" in step_name and output_lower.startswith("subject:"):
        output = remove_leading_label(output, "subject")

    if "body" in step_name:
        lines = output.strip().splitlines()
        if lines and lines[0].lower().startswith("subject:"):
            lines = lines[1:]
        output = "\n".join(lines).strip()
        if output.lower().startswith("body:"):
            output = remove_leading_label(output, "body")

    # Replace symbolic placeholders
    output = (
        output.replace("{EMAIL}", task_context.get("email", ""))
        .replace("{PLATFORM}", task_context.get("platform", ""))
        .replace("{INTENT}", task_context.get("intent", ""))
    )

    return output.strip()


def remove_outer_quotes(text):
    text = text.strip()
    if (text.startswith('"""') and text.endswith('"""')) or (
        text.startswith("'''") and text.endswith("'''")
    ):
        return text[3:-3].strip()
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1].strip()
    return text


def remove_symbolic_contaminants(text: str) -> str:
    lines = text.strip().splitlines()
    cleaned = []
    for line in lines:
        cleaned_line = re.sub(
            r'^(---Log Start---\s*|\s*(#|>>>|\*{1,2}[^:]+:{0,1}|\*|-+|>+|`{3,}|"{3}|\'{3}|[A-Z_]+:))\s*',
            "",
            line,
        )
        if cleaned_line.strip():
            cleaned.append(cleaned_line)
    return "\n".join(cleaned).strip()


def normalize_symbolic_text(s: str) -> str:
    if not s:
        return s
    s = s.strip()

    # ✅ Skip normalization for multiline content
    if "\n" in s:
        return s

    words = s.split()
    if (
        len(words) <= 7
        and sum(w[0].isupper() for w in words if w and w[0].isalpha()) >= len(words) - 1
        and not any(p in s for p in ".!?{}[]:()")
    ):
        return s[0].lower() + s[1:]

    return s


def strip_llm_explanation(text: str) -> str:
    return text.split("\n\n")[0].strip() if "\n\n" in text else text


def remove_code_block(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            content = "\n".join(lines[1:-1]).strip()
            content = re.sub(
                r"^(json|python|plaintext)\n", "", content, flags=re.IGNORECASE
            )
            content = content.encode().decode(
                "unicode_escape"
            )  # ✅ Fix for escaped quotes
            return content.strip()
        return (
            text.replace("```plaintext", "")
            .replace("```json", "")
            .replace("```python", "")
            .replace("```", "")
            .strip()
        )
    return text


def detect_case_type(s: str) -> str:
    s = s.strip()
    if re.match(r'^"```(json|plaintext|python)?\n(.|\n)+\n```"$', s):
        return "wrapped_code_block"
    elif s.startswith('"```plaintext') and s.endswith("```"):
        return "double_wrapped_markdown"
    elif s.startswith('"```plaintext') and "\n\n" in s:
        return "double_wrapped_with_explanation"
    elif s.startswith("```plaintext") and s.endswith("```"):
        return "plain_markdown"
    elif s.startswith('"') and "\n\n" in s:
        return "quoted_with_explanation"
    elif re.match(r'^\*\*.+\*\*:\s*".*"$', s):
        return "labelled_quote"
    elif re.match(r'^[A-Z_]+:\s*".*"$', s):
        return "upper_labelled_quote"
    elif s.startswith('"') and s.endswith('"'):
        return "simple_quote"
    return "unknown"


def extract_quoted_text(s: str) -> str:
    s = s.strip()

    # Sample 37
    if (
        s.startswith('"')
        and "\n\n" in s
        and not any(x in s for x in ["```", "json", "python", "plaintext"])
    ):
        first_part = s.split("\n\n")[0]
        if first_part.endswith('"'):
            inner = remove_outer_quotes(first_part)
            if inner and inner[0].isupper() and not any(p in inner for p in ".!?"):
                return inner[0].lower() + inner[1:]

    # Sample 36
    if (
        s.startswith('"')
        and s.endswith('"')
        and "\n" in s
        and not any(x in s for x in ["```", "json", "python", "plaintext"])
    ):
        inner = remove_outer_quotes(s)
        lines = [l.strip() for l in inner.splitlines() if l.strip()]
        for line in lines:
            if re.match(r"^[A-Z]?[a-z]+( [a-z]+)*$", line):  # likely clean sentence
                return normalize_symbolic_text(line)

    case_type = detect_case_type(s)

    if case_type == "wrapped_code_block":
        s = remove_outer_quotes(s)
        return normalize_symbolic_text(remove_code_block(s))

    elif case_type == "double_wrapped_markdown":
        lines = s.splitlines()
        middle = "\n".join(lines[1:]).strip()
        if middle.endswith("```"):
            middle = middle[:-3].strip()
        return normalize_symbolic_text(remove_outer_quotes(middle))

    elif case_type == "double_wrapped_with_explanation":
        s = strip_llm_explanation(s)
        s = remove_outer_quotes(s)
        s = remove_code_block(s)
        return normalize_symbolic_text(s)

    elif case_type == "plain_markdown":
        s = remove_code_block(s)
        return normalize_symbolic_text(remove_outer_quotes(s))

    elif case_type == "quoted_with_explanation":
        s = strip_llm_explanation(s)
        return normalize_symbolic_text(remove_outer_quotes(s))

    elif case_type == "labelled_quote":
        match = re.match(r'^\*\*(.+)\*\*:\s*"(.*)"$', s)
        if match:
            return match.group(2).strip()  # ✅ Skip normalization

    elif case_type == "upper_labelled_quote":
        match = re.match(r'^([A-Z_]+):\s*"(.*)"$', s)
        if match:
            return match.group(2).strip()  # ✅ Skip normalization

    elif case_type == "simple_quote":
        return normalize_symbolic_text(remove_outer_quotes(s))

    prev = None
    while s != prev:
        prev = s
        s = remove_outer_quotes(s)
        s = remove_code_block(s)
        s = remove_symbolic_contaminants(s)
        s = strip_llm_explanation(s)

    s = remove_symbolic_contaminants(s)

    # ✅ Final fallback if still empty
    if not s.strip() and "prev" in locals() and prev:
        lines = prev.splitlines()
        lines = [l.strip() for l in lines if l.strip()]
        if lines:
            s = max(lines, key=len)

    if not s.strip() and "prev" in locals() and prev:
        lines = [l.strip() for l in prev.splitlines() if l.strip()]
        if lines:
            for line in lines:
                if re.match(r"^[A-Z]?[a-z]+( [a-z]+)*$", line):  # A short clean line
                    s = line
                    break

    return normalize_symbolic_text(s)


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text


def remove_leading_label(text: str, label: str) -> str:
    """
    Removes a leading label like 'Subject:' or 'Body:' from the start of a string.
    Case-insensitive, ignores extra spaces.
    """
    if not text or not label:
        return text
    pattern = rf"^\s*{re.escape(label)}:\s*"
    return re.sub(pattern, "", text, count=1, flags=re.IGNORECASE).strip()


# ============================================================================
# TIMESTAMP UTILITIES - Added for session event normalization
# ============================================================================


def normalize_timestamp(timestamp_str: str) -> str:
    """
    Normalize custom timestamp format to standard ISO format.
    Converts: '2025-07-24T13-02-34.664502' → '2025-07-24T13:02:34.664502'

    Args:
        timestamp_str: Raw timestamp string from event logs

    Returns:
        Standard ISO timestamp string, or current time if parsing fails
    """
    if not timestamp_str:
        return datetime.now().isoformat()

    try:
        timestamp_str = timestamp_str.strip()

        # Handle custom format: 2025-07-24T13-02-34.664502
        if "T" in timestamp_str:
            date_part, time_part = timestamp_str.split("T", 1)

            # Replace dashes in time part with colons
            # Split on dash, but preserve fractional seconds
            time_components = time_part.split("-")

            if len(time_components) >= 3:
                # Reconstruct: hours:minutes:seconds.microseconds
                hours = time_components[0]
                minutes = time_components[1]
                # Everything after second dash is seconds+microseconds
                seconds_part = "-".join(time_components[2:])

                normalized_time = f"{hours}:{minutes}:{seconds_part}"
                return f"{date_part}T{normalized_time}"

        # If already in standard format or different format, return as-is
        return timestamp_str

    except Exception as e:
        print(f"[⚠️] Timestamp normalization failed: {e}")
        return datetime.now().isoformat()


def format_display_timestamp(timestamp_str: str) -> str:
    """
    Convert timestamp to human-readable format for UI display.

    Args:
        timestamp_str: ISO timestamp string

    Returns:
        Human-readable timestamp (e.g., "Jul 24, 1:02:34 PM")
    """
    if not timestamp_str:
        return "Unknown time"

    try:
        # First normalize the timestamp
        normalized = normalize_timestamp(timestamp_str)

        # Parse and format for display
        dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %I:%M:%S %p")

    except Exception as e:
        print(f"[⚠️] Display timestamp formatting failed: {e}")
        return "Invalid time"


def parse_event_timestamp(event: dict) -> str:
    """
    Extract and normalize timestamp from event dictionary with fallbacks.

    Args:
        event: Event dictionary from learning logs

    Returns:
        Normalized ISO timestamp string
    """
    # Try multiple possible timestamp field names
    timestamp_fields = [
        "input_timestamp",
        "timestamp",
        "time",
        "created_at",
        "logged_at",
        "event_time",
    ]

    for field in timestamp_fields:
        if field in event and event[field]:
            timestamp_value = event[field]

            # Handle different timestamp types
            if isinstance(timestamp_value, str):
                return normalize_timestamp(timestamp_value)
            elif isinstance(timestamp_value, (int, float)):
                # Unix timestamp
                return datetime.fromtimestamp(timestamp_value).isoformat()

    # Fallback to current time
    return datetime.now().isoformat()


def clean_event_description(event_type: str, event_data: dict) -> str:
    """
    Generate clean, standardized descriptions for different event types.

    Args:
        event_type: Type of event ('click', 'key', 'type', etc.)
        event_data: Raw event data dictionary

    Returns:
        Clean, human-readable event description
    """
    try:
        if event_type == "click":
            pos = event_data.get("raw_position", [0, 0])
            app = event_data.get("app", "Unknown App")
            window_title = event_data.get("window", {}).get("title", "Unknown")

            # Clean up coordinates display
            x, y = round(pos[0], 1), round(pos[1], 1)
            return f"Clicked at ({x}, {y}) in {window_title}"

        elif event_type == "key":
            key_value = event_data.get("key", "unknown")
            # Clean up key display
            key_display = key_value.replace("key.", "").replace("_", " ").title()
            if key_display.lower() == "tab":
                key_display = "TAB"
            return f"Pressed {key_display} key"

        elif event_type == "type":
            text = event_data.get("text", "")
            # Truncate very long text
            if len(text) > 50:
                text = text[:47] + "..."
            return f'Typed: "{text}"'

        else:
            return f"Unknown event: {event_type}"

    except Exception as e:
        print(f"[⚠️] Event description generation failed: {e}")
        return f"Event: {event_type}"
