import time
import json
import os
import re
import subprocess
import unicodedata
import platform
from typing import Dict, Any
from difflib import SequenceMatcher
from datetime import datetime

try:
    import pyautogui  # type: ignore
except Exception:
    pyautogui = None

try:
    import pyperclip  # type: ignore
except Exception:
    pyperclip = None
from reading.run_ocr_mac_native import (
    run_ocr_mac_native,
    take_timestamped_screenshot,
    reconstruct_text_from_ocr,
)
from models.qwen_caller import call_qwen_generate_from_context, summary_sprint
from reading.vision_fusion import generate_treasure_map
from reading.vision_fusion import match_target_in_treasure_map
from core.utils.cleaning import extract_and_clean_llm_output
from core.codex import load_codex, filter_ui_words

# REMOVED: from reading.run_omniparser_fallback import run_omniparser_fallback
# This will now be imported only when needed

# =========================================================================
# 🔨 HYBRID AUTOMATION ARCHITECTURE - Platform Detection & Adapter Selection
# =========================================================================


class AutomationAdapter:
    """Automation adapter using PyAutoGUI and Pyperclip only"""

    def __init__(self):
        self.platform = platform.system()
        print(f"[🐍] PyAutoGUI adapter active for {self.platform}")

    def press_key(self, key):
        """Press single key using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        try:
            pyautogui.press(key)
            print(f"[⌨️] Pressed key: {key}")
            return True
        except Exception as e:
            print(f"[❌] Error pressing key '{key}': {e}")
            return False

    def arrow_key(self, direction):
        """Press arrow key using PyAutoGUI with corruption prevention"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        try:
            pyautogui.keyDown(direction)
            time.sleep(0.02)
            pyautogui.keyUp(direction)
            print(f"[⬆️] Simulated directional key: {direction}")
            return True
        except Exception as e:
            print(f"[❌] Error pressing arrow key '{direction}': {e}")
            return False

    def tab_key(self):
        """Press Tab key using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        try:
            pyautogui.keyDown("tab")
            time.sleep(0.05)
            pyautogui.keyUp("tab")
            print("[⇥] Pressed Tab key")
            return True
        except Exception as e:
            print(f"[❌] Error pressing Tab key: {e}")
            return False

    def key_combo(self, modifiers, key):
        """Execute key combinations using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        try:
            mapped_keys = []
            for mod in modifiers:
                if mod in ["cmd", "command"]:
                    mapped_keys.append("command")
                elif mod in ["ctrl", "control"]:
                    mapped_keys.append("ctrl")
                elif mod in ["shift"]:
                    mapped_keys.append("shift")
                elif mod in ["opt", "option", "alt"]:
                    mapped_keys.append("option")
                else:
                    mapped_keys.append(mod)
            mapped_keys.append(key)
            pyautogui.hotkey(*mapped_keys, interval=0.25)
            print(f"[⌨️] Pressed key combo: {'+'.join(modifiers)}+{key}")
            return True
        except Exception as e:
            print(f"[❌] Error pressing key combo: {e}")
            return False

    def click(self, x, y):
        """Click at coordinates using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        pyautogui.moveTo(x, y)
        pyautogui.click()
        print(f"[🖱️] PyAutoGUI click used at ({x}, {y})")
        return True

    def type_text(self, text):
        """Type text using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        try:
            pyautogui.typewrite(text)
            print(f"[⌨️] Typed: {text}")
            return True
        except Exception as e:
            print(f"[❌] Error typing text: {e}")
            return False

    def paste_text(self, text):
        """Paste text using PyAutoGUI and Pyperclip"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available; cannot paste text")
        if pyperclip is None:
            raise RuntimeError("Pyperclip not available; cannot access clipboard")
        try:
            pyperclip.copy(text)
            time.sleep(0.8)
            if pyperclip.paste() != text:
                print("[⚠️] Clipboard copy failed, retrying…")
                pyperclip.copy(text)
                time.sleep(1.0)
            pyautogui.hotkey(
                "command" if self.platform == "Darwin" else "ctrl", "v", interval=0.25
            )
            print(f"[📋] Pasted: {text}")
            return True
        except Exception as e:
            print(f"[❌] Error pasting text: {e}")
            return False

    def get_screen_size(self):
        """Get screen dimensions using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available; cannot get screen size")
        try:
            return pyautogui.size()
        except Exception as e:
            print(f"[❌] Error getting screen size: {e}")
            return (1920, 1080)

    def move_mouse(self, x, y, duration=0.5):
        """Move mouse using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available on this platform")
        pyautogui.moveTo(x, y, duration=duration)
        print(f"[🖱️] Mouse moved to ({x}, {y})")
        return True

    def get_mouse_position(self):
        """Get current mouse position using PyAutoGUI"""
        if pyautogui is None:
            raise RuntimeError("PyAutoGUI not available; cannot get mouse position")
        try:
            return pyautogui.position()
        except Exception as e:
            print(f"[❌] Error getting mouse position: {e}")
            return (0, 0)


# Global automation adapter instance
automation = AutomationAdapter()

# helper functions

use_omniparser_fallback = False


def resolve_step_placeholders(
    step: Dict[str, Any], task_context: Dict[str, Any], debug: bool = True
) -> Dict[str, Any]:
    """
    Robust placeholder resolution with debugging and flexible matching
    """
    resolved = {}

    if debug:
        print(f"[🔧] Task context keys: {list(task_context.keys())}")
        print(f"[🔧] Task context values: {task_context}")

    for key, val in step.items():
        if isinstance(val, str):
            original_val = val
            new_val = val

            if debug and "{" in val:
                print(f"[🔍] Processing field '{key}': '{val}'")

            # Method 1: Direct replacement (most reliable)
            replacements_made = []
            for ctx_key, ctx_val in task_context.items():
                placeholder = f"{{{ctx_key}}}"
                if placeholder in new_val:
                    safe_val = str(ctx_val) if ctx_val is not None else ""
                    new_val = new_val.replace(placeholder, safe_val)
                    replacements_made.append(f"{placeholder} → '{safe_val}'")

            # Method 2: Regex-based replacement for flexible matching
            # This handles cases with extra whitespace: { variable_1 }
            def regex_replace(match):
                placeholder_content = match.group(1).strip()
                if placeholder_content in task_context:
                    ctx_val = task_context[placeholder_content]
                    safe_val = str(ctx_val) if ctx_val is not None else ""
                    replacements_made.append(
                        f"{{{placeholder_content}}} → '{safe_val}' (regex)"
                    )
                    return safe_val
                return match.group(0)  # Return original if no match

            # Apply regex replacement for flexible whitespace matching
            new_val = re.sub(r"\{\s*([^}]+)\s*\}", regex_replace, new_val)

            if debug and replacements_made:
                print(f"[✅] Replacements for '{key}': {replacements_made}")
                print(f"[📝] '{original_val}' → '{new_val}'")
            elif debug and "{" in original_val:
                # Find unresolved placeholders
                unresolved = re.findall(r"\{[^}]+\}", new_val)
                if unresolved:
                    print(f"[⚠️] Unresolved placeholders in '{key}': {unresolved}")

            resolved[key] = new_val
        else:
            resolved[key] = val

    return resolved


def parse_notes_config(notes_text):
    """Parse calendar notes for configuration values"""
    config = {}

    if not notes_text:
        return config

    # Parse key: value pairs from notes
    lines = notes_text.strip().split("\n")
    for line in lines:
        line = line.strip()
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            config[key] = value

    print(f"[📝] Parsed notes config: {config}")
    return config


def read_excel_file(excel_path, start_row=2):
    """Read Excel file and return rows as list of lists"""
    try:
        import pandas as pd

        # Read Excel file
        df = pd.read_excel(excel_path, header=None)  # No header, raw data

        # Convert to list of lists, starting from specified row
        rows = []
        for idx in range(start_row - 1, len(df)):  # start_row is 1-based
            row_data = df.iloc[idx].tolist()

            # Check if row is empty (stop processing)
            if all(pd.isna(val) or str(val).strip() == "" for val in row_data):
                print(f"[📊] Found empty row at {idx + 1}, stopping")
                break

            # Convert NaN to empty string
            clean_row = [str(val) if not pd.isna(val) else "" for val in row_data]
            rows.append(clean_row)

        print(f"[📊] Loaded {len(rows)} rows from Excel (starting row {start_row})")
        return rows

    except Exception as e:
        print(f"[❌] Failed to read Excel file: {e}")
        return []


def extract_column_value(row_data, column_letter):
    """Extract value from specific column (A=0, B=1, C=2, etc.)"""
    try:
        # Convert column letter to index (A=0, B=1, etc.)
        col_index = ord(column_letter.upper()) - ord("A")

        if col_index < len(row_data):
            return str(row_data[col_index]).strip()
        else:
            print(f"[⚠️] Column {column_letter} not found in row")
            return ""

    except Exception as e:
        print(f"[❌] Error extracting column {column_letter}: {e}")
        return ""


def type_or_paste(text):
    """Enhanced type_or_paste using hybrid automation adapter"""
    return automation.paste_text(text)


# Config
SPRINT_INTERVAL = 5
SPRINT_LOG_PATH = os.path.expanduser("~/Documents/pulse_logs/sprint_log")
SCREENSHOT_DIR = os.path.expanduser("~/Documents/pulse_logs/screenshots")
os.makedirs(SPRINT_LOG_PATH, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def take_screenshot():
    # Use ISO-style timestamp with colon-safe formatting
    timestamp_iso = datetime.now().isoformat().replace(":", "-")
    filename = f"sprint_{timestamp_iso}.png"
    filepath = os.path.join(SCREENSHOT_DIR, filename)
    result = subprocess.run(["screencapture", "-x", filepath])
    if result.returncode != 0:
        raise RuntimeError("Screenshot failed")
    print(f"[📸] Sprint screenshot saved: {filepath}")
    return filepath


def ping_pong_loop(task_summary):
    print("[🏓] Starting symbolic sprint ping-pong loop...")

    # 🔄 Extract runtime values if wrapped in value/example format
    def extract_value(v):
        val = v.get("value") if isinstance(v, dict) else v
        if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
            return ""  # Treat unresolved placeholders as empty
        return val

    # Parse notes for Excel configuration
    notes_text = extract_value(task_summary.get("context", {}).get("notes", ""))
    notes_config = parse_notes_config(notes_text)

    # Build task context with original variable definitions
    original_task_context = {
        "task_name": extract_value(task_summary.get("context", {}).get("task_name")),
        "intent": extract_value(task_summary.get("context", {}).get("intent")),
        "platform": extract_value(task_summary.get("context", {}).get("platform")),
        "variable_1": extract_value(task_summary.get("context", {}).get("variable_1")),
        "variable_2": extract_value(task_summary.get("context", {}).get("variable_2")),
        "variable_3": extract_value(task_summary.get("context", {}).get("variable_3")),
        "variable_4": extract_value(task_summary.get("context", {}).get("variable_4")),
        # "excel_file": extract_value(task_summary.get("context", {}).get("excel_file")),  # (Excel disabled)
        # "start_row": extract_value(task_summary.get("context", {}).get("start_row")),    # (Excel disabled)
        "notes": notes_text,
        "notes_config": notes_config,
    }

    # ===== Excel logic disabled =====
    # excel_file = original_task_context.get("excel_file")  # Instead of notes_config.get()
    # start_row_value = original_task_context.get("start_row", 2)
    # try:
    #     start_row = int(start_row_value) if start_row_value not in [None, ""] else 2
    # except Exception:
    #     start_row = 2
    #
    # print(f"[🔍] DEBUG: excel_file = '{excel_file}'")
    # print(f"[🔍] DEBUG: start_row = {start_row}")
    # print(f"[🔍] DEBUG: notes_config = {notes_config}")
    #
    # excel_rows = []
    # if excel_file and os.path.exists(excel_file):
    #     print(f"[🔍] DEBUG: File exists, reading...")
    #     excel_rows = read_excel_file(excel_file, start_row)
    #     if not excel_rows:
    #         print("[❌] No data rows found in Excel file")
    #         return
    #     print(f"[📊] Will process {len(excel_rows)} rows from Excel")
    excel_rows = []

    # Handle item list for batch processing (fallback if no Excel)
    item_list = task_summary.get("context", {}).get("list", [])
    if isinstance(item_list, str):
        item_list = [s.strip() for s in item_list.split(";") if s.strip()]
    # Insert mock list or intent-based fallback if no Excel/list data is provided
    if not item_list and not excel_rows:
        intent_text = original_task_context.get("intent", "")
        target_email = original_task_context.get("email", "")

        if intent_text and target_email:
            item_list = [target_email]
            print(f"[🪂] No list found, using intent-based email: {target_email}")
        else:
            item_list = ["mock_email_1@example.com", "mock_email_2@example.com"]
            print("[🧪] Mock mode active: no email/intents found, running test items")

    task_summary_text = summary_sprint(task_summary)
    print("[🧾] Context Summary:\n", task_summary_text)

    steps = task_summary.get("steps")

    # ✅ If steps are missing, try to auto-load based on platform
    if not steps:
        platform_raw = task_summary.get("context", {}).get("platform", "")
        # Try to get task_name from context, else fallback to event title (task_summary["task"])
        context_task_name = task_summary.get("context", {}).get("task_name", "")
        calendar_task_name = task_summary.get("task", "")
        # Normalize task name (use calendar title if context empty)
        raw_task_name = context_task_name if context_task_name else calendar_task_name
        task_name = raw_task_name.strip().lower().replace(" ", "_")
        source = "context" if context_task_name else "calendar"
        print(f"[🧪] Resolved task_name: {task_name} (from {source})")
        platform_folder = (
            platform_raw.lower()
            .replace("https://", "")
            .replace("www.", "")
            .split(".")[0]
        )

        steps_path = f"codex/{platform_folder}/tasks/{task_name}.json"

        if os.path.exists(steps_path):
            with open(steps_path) as f:
                task_data = json.load(f)
                steps = task_data.get("steps", [])
                print(f"[📥] Loaded {len(steps)} symbolic steps from: {steps_path}")
        else:
            print(f"[❌] Symbolic task file not found at: {steps_path}")
            steps = []

    if not steps:
        print("[❌] No symbolic steps loaded. Exiting sprint loop.")
        return

    # 🔁 Load treasure_map from task or regenerate
    treasure_map = task_summary.get("treasure_map")
    if not treasure_map:
        try:
            first_screenshot = take_screenshot()
            treasure_map = generate_treasure_map(first_screenshot)
            print("[🧭] Treasure map generated inside sprint loop.")
        except Exception as e:
            print(f"[❌] Failed to generate treasure map: {e}")
            treasure_map = []

    # Main processing loop for each item
    if excel_rows:
        items_to_process = excel_rows
        processing_mode = "excel"
    else:
        items_to_process = item_list
        processing_mode = "list"

    # Main processing loop
    for current_item in items_to_process:

        # Build task_context for this iteration
        task_context = original_task_context.copy()

        if processing_mode == "excel":
            # Excel mode: inject column values into variables
            row_data = current_item
            print(f"[🔁] Processing Excel row: {row_data}")

            # Process each variable to check for extract_column_X pattern
            for var_key in ["variable_1", "variable_2", "variable_3", "variable_4"]:
                var_value = task_context[var_key]

                # Check if variable has extract_column_X pattern
                if isinstance(var_value, str) and var_value.startswith(
                    "extract_column_"
                ):
                    # Extract column letter (extract_column_B -> B)
                    column_letter = var_value.split("_")[-1]
                    extracted_value = extract_column_value(row_data, column_letter)
                    task_context[var_key] = extracted_value
                    print(
                        f"[📊] {var_key}: '{var_value}' → '{extracted_value}' (column {column_letter})"
                    )

        else:
            # List mode: original behavior
            item = current_item
            print(f"[🔁] Running symbolic sprint for: {item}")
            task_context["variable_1"] = item

        step_index = 0
        pulse = 0

        # Process each step for current item
        while step_index < len(steps):
            pulse += 1
            timestamp = datetime.now().isoformat()

            if pulse == 1:
                print("[⏳] Waiting for screen to stabilize (first pulse)...")
                time.sleep(1)
            else:
                time.sleep(SPRINT_INTERVAL)

            if processing_mode == "excel":
                print(
                    f"[🪛] Pulse {pulse} — step_index {step_index} — processing Excel row {len(excel_rows) - len(items_to_process) + items_to_process.index(current_item) + 1}"
                )
            else:
                print(
                    f"[🪛] Pulse {pulse} — step_index {step_index} — processing item: {current_item}"
                )

            # 📸 Take screenshot and update treasure map
            try:
                screenshot_path = take_timestamped_screenshot()
                print(f"[📸] Screenshot taken: {screenshot_path}")

                # Extract timestamp for OCR + VC filenames
                screenshot_timestamp = (
                    os.path.basename(screenshot_path)
                    .replace("sprint_", "")
                    .replace(".png", "")
                )

                # --- OCR Layer ---
                ocr_result = run_ocr_mac_native(
                    screenshot_path, timestamp=screenshot_timestamp, is_sprint=True
                )
                if "text_blocks" not in ocr_result or not ocr_result["text_blocks"]:
                    print("[❌] OCR missing or empty 'text_blocks'.")
                    break

                text_lines = reconstruct_text_from_ocr(ocr_result["text_blocks"])
                visible_text = "\n".join(text_lines).strip()
                ui_words = [
                    block["text"]
                    for block in ocr_result["text_blocks"]
                    if block["text"].strip()
                ]
                print(f"[👁️] Visible Text:\n{visible_text[:500]}")

                # --- Computer Vision Layout Layer ---
                from reading.run_computer_vision import run_computer_vision

                run_computer_vision(screenshot_path, screenshot_timestamp)

                # --- Treasure Map Fusion using full vision stack ---
                try:
                    from reading.vision_fusion import generate_combined_treasure_map

                    treasure_map = generate_combined_treasure_map(screenshot_path)
                    print(
                        f"[🧭] Treasure map generated using Vision Fusion. Blocks: {len(treasure_map)}"
                    )
                except Exception as vf_error:
                    print(f"[⚠️] Vision Fusion failed: {vf_error}")
                    if use_omniparser_fallback:
                        try:
                            # LAZY LOADING: Import omniparser only when needed
                            print(
                                "[🔄] Attempting OmniParser fallback (lazy loading)..."
                            )

                            # Try the vision_fusion omniparser first
                            try:
                                from reading.vision_fusion import (
                                    generate_treasure_map_omni,
                                )

                                treasure_map, _, _ = generate_treasure_map_omni(
                                    screenshot_path
                                )
                                print(
                                    "[🧠] Treasure map recovered using OmniParser (vision_fusion)."
                                )
                            except (ImportError, AttributeError) as import_error:
                                print(
                                    f"[⚠️] vision_fusion omniparser not available: {import_error}"
                                )
                                # Fallback to the original omniparser
                                try:
                                    from reading.run_omniparser_fallback import (
                                        run_omniparser_fallback,
                                    )

                                    omni_result = run_omniparser_fallback(
                                        screenshot_path
                                    )
                                    # Convert omniparser result to treasure_map format if needed
                                    treasure_map = (
                                        omni_result
                                        if isinstance(omni_result, list)
                                        else []
                                    )
                                    print(
                                        "[🧠] Treasure map recovered using OmniParser fallback."
                                    )
                                except ImportError as final_error:
                                    print(
                                        f"[❌] All OmniParser options failed: {final_error}"
                                    )
                                    treasure_map = []

                        except Exception as omni_error:
                            print(f"[❌] OmniParser also failed: {omni_error}")
                            treasure_map = []
                    else:
                        print("[🛑] Skipping OmniParser fallback (disabled by config).")
                        treasure_map = []

                # Filter UI elements using Codex
                platform_folder = (
                    task_context["platform"]
                    .lower()
                    .replace("https://", "")
                    .replace("www.", "")
                    .split(".")[0]
                )
                codex = load_codex(platform=platform_folder)
                filtered_ui_codex = filter_ui_words(ui_words, codex)
                codex_words = list(
                    dict.fromkeys(entry["name"] for entry in filtered_ui_codex)
                )
                print("[📌] Codex-filtered UI elements:", codex_words)

            except Exception as e:
                print(f"[❌] Visual stack (screenshot → OCR → VC → map) failed: {e}")
                break

            # 🧠 Get current symbolic step
            current_step = steps[
                step_index
            ].copy()  # Make a copy to avoid modifying original
            print(f"[🧠] Current Step {step_index}: {current_step}")

            # 🪞 Mirror 1: Placeholder resolution - RESOLVE BEFORE ANY PROCESSING
            current_step = resolve_step_placeholders(
                current_step, task_context, debug=True
            )
            print(f"[✅] Resolved Step {step_index}: {current_step}")

            # 🪞 Mirror 2: Refuse unresolved tokens
            if any(
                "{" in str(v) and "}" in str(v)
                for v in current_step.values()
                if isinstance(v, str)
            ):
                print(f"[🛑] Unresolved placeholder in step: {current_step}")
                break

            # 🪞 Mirror 3: Handle Qwen-generated content
            if current_step.get("actor") == "artificial" and not current_step.get(
                "text"
            ):
                print(
                    "[🤖] Qwen-triggered step detected. Calling Qwen for dynamic content..."
                )

                qwen_response = call_qwen_generate_from_context(
                    {
                        "task_type": "generate_step_text",
                        "intent": task_context["intent"],
                        "platform": task_context["platform"],
                        "context": task_context,
                        "step_note": current_step.get("note", ""),
                    }
                )

                if qwen_response["status"] == "ok":
                    raw_output = qwen_response["output"]
                    step_name = current_step.get("step_name", "")
                    clean_output = extract_and_clean_llm_output(
                        raw_output, step_name, task_context
                    )

                    current_step["text"] = clean_output
                    print(f"[✅] Step text injected: {current_step['text']}")
                else:
                    print("[❌] Qwen failed:", qwen_response["output"])
                    break

            # 🪞 Mirror 4-5: Action execution
            try:
                print(f"[⚙️] Executing step: {current_step}")
                execute_action(current_step, treasure_map, task_context)
            except Exception as e:
                print(f"[❌] Step execution failed: {e}")
                break

            # ✅ Mirror pass — move to next step
            step_index += 1

            # 4. Log
            try:
                log_data = {
                    "timestamp": timestamp,
                    "pulse": pulse,
                    "task": task_summary,
                    "current_item": current_item,
                    "step_index": step_index,
                    "resolved_step": current_step,
                }
                filename = f"sprint_ping_{timestamp.replace(':', '-')}.json"
                filepath = os.path.join(SPRINT_LOG_PATH, filename)
                with open(filepath, "w") as f:
                    json.dump(log_data, f, indent=2)
                print(f"[📩] Sprint pulse {pulse} logged: {filepath}")
            except Exception as e:
                print(f"[❌] Log write failed: {e}")

        print(f"[✅] Completed all steps for item: {current_item}")

    print("[🏁] All items processed successfully!")


# Utility functions


def clean_text(text: str) -> str:
    if not text:
        return ""
    return (
        unicodedata.normalize("NFKD", text.lower().strip())
        .encode("ascii", "ignore")
        .decode("ascii")
    )


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def execute_action(parsed_action, treasure_map, task_context=None):
    """
    Enhanced execute_action with hybrid automation adapter and duplicate click prevention
    """
    action_type = parsed_action.get("type", "")

    if action_type == "open":
        # Handle 'open' action - typically opening a URL
        target = parsed_action.get("target", "")
        if target.startswith("http"):
            import webbrowser

            webbrowser.open(target)
            print(f"[🌐] Opened URL: {target}")
        else:
            print(f"[⚠️] Open action with non-URL target: {target}")

    elif action_type == "move" or action_type == "hover":
        # NEW: Mouse movement without clicking
        target = parsed_action.get("target")
        direct_coords = parsed_action.get("coordinates")
        duration = parsed_action.get(
            "duration", 0.5
        )  # Default smooth movement duration

        if direct_coords:
            # Use direct coordinates from JSON
            screen_w, screen_h = automation.get_screen_size()
            final_x = int(direct_coords[0] * screen_w)
            final_y = int(direct_coords[1] * screen_h)

            print(f"[🖱️] Moving mouse to '{target}': ({final_x}, {final_y})")

            # Smooth mouse movement via automation adapter
            automation.move_mouse(final_x, final_y, duration)
            print(f"[✅] Mouse moved to {target} at coordinates ({final_x}, {final_y})")

            # Store movement for tracking (optional)
            if task_context is not None:
                task_context["last_move_coords"] = (final_x, final_y)
                task_context["last_move_target"] = target

        elif target:
            # Use treasure map to find target
            match = match_target_in_treasure_map(treasure_map, target)
            print(f"[🔍] Match result for mouse move '{target}': {match}")

            if match and "position" in match:
                x, y, w, h = match["position"]
                screen_w, screen_h = automation.get_screen_size()
                x_px = int(x * screen_w)
                y_px = int(y * screen_h)
                w_px = int(w * screen_w)
                h_px = int(h * screen_h)
                final_x = x_px + w_px // 2
                final_y = y_px + h_px // 2

                # Smooth mouse movement via automation adapter
                automation.move_mouse(final_x, final_y, duration)
                print(f"[🖱️] Mouse moved to {target} at center of {match['position']}")

                # Store movement for tracking (optional)
                if task_context is not None:
                    task_context["last_move_coords"] = (final_x, final_y)
                    task_context["last_move_target"] = target
            else:
                print(
                    f"[❌] Could not find target '{target}' in treasure map for mouse movement"
                )

    elif action_type == "click":
        target = parsed_action.get("target")
        direct_coords = parsed_action.get(
            "coordinates"
        )  # NEW: Check for direct coordinates

        if direct_coords:
            # Use direct coordinates from JSON
            screen_w, screen_h = automation.get_screen_size()
            final_x = int(direct_coords[0] * screen_w)
            final_y = int(direct_coords[1] * screen_h)

            print(
                f"[📍] Using direct coordinates for '{target}': ({final_x}, {final_y})"
            )
            print(f"[🧠] Screen size: {screen_w}x{screen_h}")
            print(f"[🎯] Direct click coordinates: ({final_x}, {final_y})")

            # 🛡️ SMART DUPLICATE CLICK PREVENTION (same logic as treasure map)
            click_tolerance = 15  # pixels - adjust as needed
            should_click = True

            if (
                task_context
                and "last_click_coords" in task_context
                and "last_click_target" in task_context
            ):
                last_coords = task_context["last_click_coords"]
                last_target = task_context["last_click_target"]

                if isinstance(last_coords, tuple) and len(last_coords) >= 2:
                    # Always treat stored coords as pixel coordinates (we store them as pixels)
                    last_x_px, last_y_px = last_coords[:2]
                    print(f"[🔧] DEBUG: Stored coords: {last_coords}")
                    print(
                        f"[🔧] DEBUG: Extracted last position: ({last_x_px}, {last_y_px})"
                    )

                    # Calculate distance between current and last click
                    distance = (
                        (final_x - last_x_px) ** 2 + (final_y - last_y_px) ** 2
                    ) ** 0.5

                    print(f"[📏] Distance from last click: {distance:.1f} pixels")
                    print(f"[📍] Last click was at: ({last_x_px}, {last_y_px})")
                    print(
                        f"[🎯] Last target: '{last_target}' | Current target: '{target}'"
                    )

                    # PRIMARY: Block if coordinates are identical (0-2px = same UI element)
                    if distance <= 2:  # Very tight tolerance for exact same element
                        should_click = False
                        print(
                            f"[🛡️] DUPLICATE CLICK PREVENTED - identical coordinates ({distance:.1f}px ≤ 2px)"
                        )
                        print(
                            f"[🔄] Same UI element: '{last_target}' → '{target}' at same location"
                        )
                    # SECONDARY: Block if same target AND close coordinates
                    elif (
                        distance < click_tolerance
                        and target.lower().strip() == last_target.lower().strip()
                    ):
                        should_click = False
                        print(
                            f"[🛡️] DUPLICATE CLICK PREVENTED - same target '{target}' too close to last click ({distance:.1f}px < {click_tolerance}px)"
                        )
                        print(
                            f"[🔄] Skipping click - exact same target at same location"
                        )
                    else:
                        print(
                            f"[✅] ALLOWING CLICK - sufficient distance ({distance:.1f}px) or different target"
                        )

            if should_click:
                automation.click(final_x, final_y)
                print(
                    f"[🖱️] Clicked on {target} at direct coordinates ({final_x}, {final_y})"
                )

                # 💾 Store current click coordinates for next comparison
                if task_context is not None:
                    task_context["last_click_coords"] = (
                        final_x,
                        final_y,
                    )  # Store as pixel coords
                    task_context["last_click_target"] = target
                    task_context["last_click_time"] = time.time()
            else:
                # Still update some tracking info even if we skipped
                if task_context is not None:
                    task_context["last_skipped_target"] = target

        elif target:
            # Existing treasure map logic (updated with automation adapter)
            match = match_target_in_treasure_map(treasure_map, target)
            print(f"[🔍] Match result for '{target}': {match}")

            if match and "position" in match:
                x, y, w, h = match["position"]
                screen_w, screen_h = automation.get_screen_size()
                x_px = int(x * screen_w)
                y_px = int(y * screen_h)
                w_px = int(w * screen_w)
                h_px = int(h * screen_h)
                final_x = x_px + w_px // 2
                final_y = y_px + h_px // 2

                print(f"[🧠] Screen size: {screen_w}x{screen_h}")
                print(f"[📐] Normalized coords: {x}, {y}, {w}, {h}")
                print(f"[📍] Pixel coords: x={x_px}, y={y_px}, w={w_px}, h={h_px}")
                print(f"[🎯] Target click coordinates: ({final_x}, {final_y})")

                # 🛡️ SMART DUPLICATE CLICK PREVENTION
                click_tolerance = 15  # pixels - adjust as needed
                should_click = True

                if (
                    task_context
                    and "last_click_coords" in task_context
                    and "last_click_target" in task_context
                ):
                    last_coords = task_context["last_click_coords"]
                    last_target = task_context["last_click_target"]

                    if isinstance(last_coords, tuple) and len(last_coords) >= 2:
                        # Always treat stored coords as pixel coordinates (we store them as pixels)
                        last_x_px, last_y_px = last_coords[:2]
                        print(f"[🔧] DEBUG: Stored coords: {last_coords}")
                        print(
                            f"[🔧] DEBUG: Extracted last position: ({last_x_px}, {last_y_px})"
                        )

                        # Calculate distance between current and last click
                        distance = (
                            (final_x - last_x_px) ** 2 + (final_y - last_y_px) ** 2
                        ) ** 0.5

                        print(f"[📏] Distance from last click: {distance:.1f} pixels")
                        print(f"[📍] Last click was at: ({last_x_px}, {last_y_px})")
                        print(
                            f"[🎯] Last target: '{last_target}' | Current target: '{target}'"
                        )

                        # PRIMARY: Block if coordinates are identical (0-2px = same UI element)
                        if distance <= 2:  # Very tight tolerance for exact same element
                            should_click = False
                            print(
                                f"[🛡️] DUPLICATE CLICK PREVENTED - identical coordinates ({distance:.1f}px ≤ 2px)"
                            )
                            print(
                                f"[🔄] Same UI element: '{last_target}' → '{target}' at same location"
                            )
                        # SECONDARY: Block if same target AND close coordinates
                        elif (
                            distance < click_tolerance
                            and target.lower().strip() == last_target.lower().strip()
                        ):
                            should_click = False
                            print(
                                f"[🛡️] DUPLICATE CLICK PREVENTED - same target '{target}' too close to last click ({distance:.1f}px < {click_tolerance}px)"
                            )
                            print(
                                f"[🔄] Skipping click - exact same target at same location"
                            )
                        else:
                            print(
                                f"[✅] ALLOWING CLICK - sufficient distance ({distance:.1f}px) or different target"
                            )

                if should_click:
                    automation.click(final_x, final_y)
                    print(f"[🖱️] Clicked on {target} at center of {match['position']}")

                    # 💾 Store current click coordinates for next comparison
                    if task_context is not None:
                        task_context["last_click_coords"] = (
                            final_x,
                            final_y,
                        )  # Store as pixel coords
                        task_context["last_click_target"] = target
                        task_context["last_click_time"] = time.time()
                else:
                    # Still update some tracking info even if we skipped
                    if task_context is not None:
                        task_context["last_skipped_target"] = target

            else:
                print(f"[❌] Could not find target '{target}' in treasure map")

    elif action_type == "key":
        key = parsed_action.get("text", "").lower().strip()
        if not key:
            print("[⚠️] No key specified to press.")
        elif "+" in key:
            # Handle key combinations with hybrid automation adapter
            keys = [k.strip().lower() for k in key.split("+")]

            # Map common variations to consistent format
            mapped_keys = []
            for k in keys:
                if k in ["cmd", "command"]:
                    mapped_keys.append("command")
                elif k in ["ctrl", "control"]:
                    mapped_keys.append("ctrl")
                elif k in ["shift"]:
                    mapped_keys.append("shift")
                elif k in ["opt", "option", "alt"]:
                    mapped_keys.append("option")
                else:
                    mapped_keys.append(k)

            try:
                # Use automation adapter for key combinations
                modifiers = mapped_keys[:-1]  # All except last
                main_key = mapped_keys[-1]  # Last key
                automation.key_combo(modifiers, main_key)
                print(f"[⌨️] Pressed key combo: {key}")
            except Exception as e:
                print(f"[❌] Error pressing key combo '{key}': {e}")
        else:
            # Single key press with hybrid automation adapter
            try:
                if key in ["up", "down", "left", "right"]:
                    # Use specialized arrow key handling
                    automation.arrow_key(key)
                    print(f"[⬆️] Pressed directional key: {key}")
                elif key == "tab":
                    automation.tab_key()
                    print("[⇥] Simulated Tab key")
                else:
                    # Normal keys
                    automation.press_key(key)
                    print(f"[⌨️] Pressed key: {key}")
            except Exception as e:
                print(f"[❌] Error pressing key '{key}': {e}")

    elif action_type == "type":
        text = parsed_action.get("text", "")
        if text:
            type_or_paste(text)
        else:
            print("[⚠️] No text specified to type.")


# Additional helper function for more sophisticated duplicate detection
def are_coordinates_similar(coords1, coords2, tolerance=15):
    """
    Check if two coordinate sets represent the same click location
    coords can be (x, y) or (x_norm, y_norm, w_norm, h_norm)
    """
    if not coords1 or not coords2:
        return False

    # Convert normalized to pixel coordinates if needed
    screen_w, screen_h = automation.get_screen_size()

    if len(coords1) == 4:  # normalized
        x1 = int(coords1[0] * screen_w) + int(coords1[2] * screen_w) // 2
        y1 = int(coords1[1] * screen_h) + int(coords1[3] * screen_h) // 2
    else:  # pixel
        x1, y1 = coords1[:2]

    if len(coords2) == 4:  # normalized
        x2 = int(coords2[0] * screen_w) + int(coords2[2] * screen_w) // 2
        y2 = int(coords2[1] * screen_h) + int(coords2[3] * screen_h) // 2
    else:  # pixel
        x2, y2 = coords2[:2]

    distance = ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5
    return distance < tolerance
