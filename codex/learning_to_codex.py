# learning_to_codex.py
"""
Learning to Codex Converter
Just being really careful about automation reliability...
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime


class AutomationConverter:
    def __init__(self):
        self.base_path = Path(__file__).parent.parent.parent / "mia_desktop"
        self.learning_logs_path = self.base_path / "learning" / "learning_logs"
        self.codex_output_path = self.base_path / "codex"

    def load_learning_session(self, learning_id: str) -> List[Dict]:
        """Load learning session data"""
        session_folder = self.learning_logs_path / learning_id
        session_file = session_folder / "learning_id.json"

        print(f"[DEBUG] Looking for file at: {session_file}")

        if not session_file.exists():
            raise FileNotFoundError(f"Learning session {learning_id} not found")

        with open(session_file, "r") as f:
            actions = json.load(f)

        return actions

    def check_coordinates(self, action: Dict) -> Tuple[bool, str, str, Dict]:
        """
        Checking coordinates and extracting target names using OCR
        Now returns both detected text and suggested target
        """

        detection_info = {
            "detected_text": None,
            "ocr_confidence": "none",
            "crop_screenshot": action.get("crop_screenshot"),
        }

        if action["event"] == "click":
            # TRY OCR FIRST
            try:
                ocr_result = self.extract_target_text_from_coordinates(action)
                detection_info["detected_text"] = ocr_result

                # Use OCR result if it's good
                if (
                    ocr_result
                    and len(ocr_result.strip()) > 2
                    and not ocr_result.lower().startswith("something")
                ):

                    detection_info["ocr_confidence"] = "high"

                    # Set SMART TARGET for execution (user can edit later)
                    target = self._suggest_target_from_ocr(ocr_result, action)

                    return True, target, "OCR extracted target name", detection_info

            except Exception as e:
                print(f"OCR extraction failed: {e}")
                detection_info["ocr_confidence"] = "failed"

            # FALLBACK to position-based logic
            window_title = action.get("window", {}).get("title", "")
            pos = action.get("rel_position", [0, 0])

            if "Learning Loop" in window_title:
                if pos[1] < 0.3:
                    target = "top_area"
                elif pos[1] > 0.8:
                    target = "bottom_button"
                elif pos[0] < 0.5 and 0.3 < pos[1] < 0.7:
                    target = "left_control"
                else:
                    target = "main_area"
            else:
                # Use the fallback method instead of generic name
                target = self._generate_fallback_target_name(action)

            detection_info["detected_text"] = detection_info["detected_text"] or target

            return True, target, "Coordinates look reasonable", detection_info

        elif action["event"] == "type":
            detection_info["detected_text"] = action.get("text", "")
            return True, "text_input", "Text field", detection_info

        elif action["event"] == "key":
            key_name = action.get("key", action.get("text", "unknown"))
            detection_info["detected_text"] = key_name
            return True, f"key_{key_name}", f"Key press: {key_name}", detection_info

        return False, "unknown", "Coordinates seem off", detection_inf

    def _suggest_target_from_ocr(self, ocr_text: str, action: Dict) -> str:
        """Suggest a good target name for automation execution based on OCR"""

        # Clean up OCR text for target use
        cleaned = self._clean_target_name(ocr_text)

        # Smart suggestions based on common UI patterns
        lower_text = cleaned.lower()

        # Common button patterns
        if any(word in lower_text for word in ["button", "btn", "click"]):
            return cleaned.replace("button", "").replace("btn", "").strip()

        # Navigation elements
        if any(word in lower_text for word in ["menu", "nav", "link"]):
            return cleaned

        # Form elements
        if any(word in lower_text for word in ["input", "field", "text"]):
            return "text_input"

        # Default: use cleaned OCR text (user can edit)
        return cleaned

    def verify_window(self, action: Dict, target: str) -> Tuple[bool, str]:
        """
        Double-checking the window context...
        Don't want automation clicking in wrong apps!
        """

        window = action.get("window", {})
        app = window.get("app", "Unknown")
        title = window.get("title", "Unknown")

        # Make sure we're in the right place
        if app == "Google Chrome":
            if "localhost" in title:
                return True, f"Local dev environment - {target}"
            elif "Claude" in title:
                return True, f"Claude interface - {target}"
            else:
                return True, f"Browser window - {target}"
        elif app == "Control Center":
            return True, f"System control - {target}"
        else:
            return True, f"App context - {target}"

    def test_compatibility(self, action: Dict, target: str) -> Tuple[bool, str]:
        """
        Testing if this will actually work...
        So many things can go wrong with automation
        """

        window = action.get("window", {})

        # Check if window seems normal
        if window.get("alpha", 1.0) < 0.1:
            return False, "Window too transparent"

        # Check coordinates are in bounds
        rel_pos = action.get("rel_position", [0, 0])
        if rel_pos[0] < 0 or rel_pos[0] > 1 or rel_pos[1] < 0 or rel_pos[1] > 1:
            return False, "Position outside window"

        # Window size check
        if window.get("width", 0) < 100 or window.get("height", 0) < 100:
            return False, "Window too small"

        return True, "Should work fine"

    def analyze_resolution(self, action: Dict, target: str) -> Tuple[bool, str]:
        """
        Checking if this works on different screen sizes
        People have all sorts of weird monitor setups...
        """

        window = action.get("window", {})
        rel_pos = action.get("rel_position", [0, 0])

        # Test some common resolutions
        test_sizes = [
            {"width": 1920, "height": 1080},
            {"width": 2560, "height": 1440},
            {"width": 3840, "height": 2160},
        ]

        working_count = 0
        for size in test_sizes:
            test_x = rel_pos[0] * size["width"]
            test_y = rel_pos[1] * size["height"]

            # Check if click position is reasonable
            if 10 < test_x < size["width"] - 10 and 10 < test_y < size["height"] - 10:
                working_count += 1

        success_rate = working_count / len(test_sizes)

        if success_rate >= 0.8:
            return True, f"Works on most screens ({success_rate:.0%})"
        elif success_rate >= 0.6:
            return True, f"Might work on some screens ({success_rate:.0%})"
        else:
            return False, f"Probably won't work well ({success_rate:.0%})"

    def validate_position(self, action: Dict, target: str) -> Tuple[bool, str]:
        """
        Final position check...
        Just want to make sure we can actually find this element
        """

        window = action.get("window", {})
        app = window.get("app", "")

        # Count how many ways we can target this
        targeting_options = []

        if action.get("rel_position"):
            targeting_options.append("coordinates")

        if app and app != "Unknown":
            targeting_options.append("app")

        if window.get("title") and window.get("title") != "Unknown":
            targeting_options.append("window")

        if action.get("event"):
            targeting_options.append("action_type")

        # Calculate confidence
        option_count = len(targeting_options)
        if option_count >= 3:
            confidence = 0.9
        elif option_count == 2:
            confidence = 0.7
        else:
            confidence = 0.4

        if confidence >= 0.7:
            return True, f"Multiple targeting options ({option_count})"
        else:
            return False, f"Limited targeting options ({option_count})"

    def run_checks(self, action: Dict) -> Dict[str, Any]:
        """
        Running all my paranoid checks...
        Now with action-type-specific reliability
        """

        action_type = action.get("event", "unknown")

        # Just checking everything I can think of...
        coords_ok, target, coords_reason, detection_info = self.check_coordinates(
            action
        )
        window_ok, window_reason = self.verify_window(action, target)

        # For clicks: run all checks
        if action_type == "click":
            compat_ok, compat_reason = self.test_compatibility(action, target)
            resolution_ok, resolution_reason = self.analyze_resolution(action, target)
            position_ok, position_reason = self.validate_position(action, target)

            checks_passed = [
                coords_ok,
                window_ok,
                compat_ok,
                resolution_ok,
                position_ok,
            ]
            passed_count = sum(checks_passed)
            trust_action = passed_count >= 4  # Need 4/5 checks for clicks

            return {
                "target": target,
                "detection_info": detection_info,
                "checks": {
                    "coordinates": {"passed": coords_ok, "note": coords_reason},
                    "window": {"passed": window_ok, "note": window_reason},
                    "compatibility": {"passed": compat_ok, "note": compat_reason},
                    "resolution": {"passed": resolution_ok, "note": resolution_reason},
                    "position": {"passed": position_ok, "note": position_reason},
                },
                "summary": {
                    "checks_passed": passed_count,
                    "total_checks": len(checks_passed),
                    "success_rate": passed_count / len(checks_passed),
                    "reliable": trust_action,
                    "confidence": (
                        "high"
                        if passed_count == 5
                        else "medium" if passed_count >= 4 else "low"
                    ),
                },
            }

        # For type/key: simpler checks (coordinates/positions not relevant)
        elif action_type in ["type", "key"]:
            # Only run relevant checks for keyboard actions
            text_ok = True
            text_reason = "Text input available"

            if action_type == "type":
                text_content = action.get("text", "")
                if not text_content or len(text_content.strip()) == 0:
                    text_ok = False
                    text_reason = "No text content"
            elif action_type == "key":
                key_value = action.get("key", action.get("text", ""))
                if not key_value:
                    text_ok = False
                    text_reason = "No key specified"

            # For keyboard actions: only need basic checks
            checks_passed = [coords_ok, window_ok, text_ok]
            passed_count = sum(checks_passed)
            trust_action = passed_count >= 2  # More lenient for keyboard (2/3 checks)

            return {
                "target": target,
                "detection_info": detection_info,
                "checks": {
                    "coordinates": {"passed": coords_ok, "note": coords_reason},
                    "window": {"passed": window_ok, "note": window_reason},
                    "text_content": {"passed": text_ok, "note": text_reason},
                },
                "summary": {
                    "checks_passed": passed_count,
                    "total_checks": len(checks_passed),
                    "success_rate": passed_count / len(checks_passed),
                    "reliable": trust_action,
                    "confidence": (
                        "high"
                        if passed_count == 3
                        else "medium" if passed_count >= 2 else "low"
                    ),
                },
            }

        # For unknown action types: minimal checks
        else:
            checks_passed = [coords_ok, window_ok]
            passed_count = sum(checks_passed)
            trust_action = passed_count >= 1  # Very lenient for unknown

            return {
                "target": target,
                "detection_info": detection_info,
                "checks": {
                    "coordinates": {"passed": coords_ok, "note": coords_reason},
                    "window": {"passed": window_ok, "note": window_reason},
                },
                "summary": {
                    "checks_passed": passed_count,
                    "total_checks": len(checks_passed),
                    "success_rate": passed_count / len(checks_passed),
                    "reliable": trust_action,
                    "confidence": "medium" if passed_count >= 2 else "low",
                },
            }

    def create_step(
        self, action: Dict, step_number: int, check_results: Dict
    ) -> Optional[Dict]:
        """
        Create automation step with enhanced data structure
        """

        if not check_results["summary"]["reliable"]:
            return None

        target = check_results["target"]
        detection_info = check_results.get("detection_info", {})
        window = action.get("window", {})

        step = {
            "step": step_number,
            "action": action["event"],
            "target": target,  # What automation should search for
            "detected_text": detection_info.get(
                "detected_text"
            ),  # What OCR actually saw
            "actor": "automation",  # Who performs this action
            "app": window.get("app", "Unknown"),
            "window_title": window.get("title", "Unknown"),
            "notes": f"Auto-generated step {step_number}",
            "reliability": {
                "confidence": check_results["summary"]["confidence"],
                "checks_passed": check_results["summary"]["checks_passed"],
                "verified": True,
            },
        }

        # Add OCR metadata if available
        if detection_info.get("crop_screenshot"):
            step["crop_screenshot"] = detection_info["crop_screenshot"]
        if detection_info.get("ocr_confidence"):
            step["ocr_confidence"] = detection_info["ocr_confidence"]

        # Add action-specific details
        if action["event"] == "click":
            step.update(
                {
                    "coordinates": action.get("rel_position", [0, 0]),
                    "click_type": "left_click",
                }
            )

        elif action["event"] == "type":
            step.update({"text": action.get("text", ""), "input_type": "text_entry"})

        elif action["event"] == "key":
            key_name = action.get("key", action.get("text", "unknown"))
            step.update({"key": key_name, "input_type": "keyboard"})

        return step

    def convert_to_automation(self, learning_id: str, name: str = None) -> Dict:
        """
        Convert learning to automation
        With all my paranoid checking...
        """

        actions = self.load_learning_session(learning_id)

        if not actions:
            raise ValueError("No actions found")

        if not name:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            name = f"automation_{timestamp}"

        # Process each action with lots of checking
        reliable_steps = []
        check_summary = {
            "total_actions": len(actions),
            "reliable_steps": 0,
            "unreliable_steps": 0,
            "failed_checks": {},
        }

        for i, action in enumerate(actions, 1):
            # Run all my paranoid checks
            results = self.run_checks(action)

            # Create step if reliable enough
            step = self.create_step(action, i, results)

            if step:
                reliable_steps.append(step)
                check_summary["reliable_steps"] += 1
            else:
                check_summary["unreliable_steps"] += 1
                # Track what went wrong
                for check_name, check_result in results["checks"].items():
                    if not check_result["passed"]:
                        if check_name not in check_summary["failed_checks"]:
                            check_summary["failed_checks"][check_name] = 0
                        check_summary["failed_checks"][check_name] += 1

        # Build the automation
        automation = {
            "name": name,
            "description": f"Learned automation with {len(reliable_steps)} steps",
            "created": datetime.now().isoformat(),
            "source": learning_id,
            "steps": reliable_steps,
            "quality_report": check_summary,
            "settings": {
                "generated_from": "learning_session",
                "quality_checks": "enabled",
                "reliability_threshold": "high",
            },
        }

        return automation

    def save_automation(self, automation: Dict, name: str) -> str:
        """Save automation to file"""
        output_file = self.codex_output_path / f"{name}.json"

        self.codex_output_path.mkdir(parents=True, exist_ok=True)

        # Save normally first
        with open(output_file, "w") as f:
            json.dump(automation, f, indent=2)

        # POST-PROCESS: Reformat steps to single lines
        with open(output_file, "r") as f:
            content = f.read()

        # Simple regex to put each step object on one line
        import re

        # Find step objects and compress them
        step_pattern = r'    {[\s\S]*?"step": \d+[\s\S]*?    }'

        def compress_step(match):
            step_text = match.group(0)
            # Remove internal whitespace and newlines, keep structure
            compressed = re.sub(r"\s+", " ", step_text.replace("\n", ""))
            return f"    {compressed.strip()}"

        content = re.sub(step_pattern, compress_step, content)

        # Write back the reformatted version
        with open(output_file, "w") as f:
            f.write(content)

        return str(output_file)

    def extract_target_text_from_coordinates(self, action: Dict) -> str:
        """Extract text from crop screenshot using OCR"""

        # Get the stored crop screenshot path
        crop_path = action.get("crop_screenshot")

        if not crop_path or not os.path.exists(crop_path):
            print("No crop screenshot available for OCR")
            return self._generate_fallback_target_name(action)

        try:
            # Import OCR library
            import easyocr

            # Run OCR on the stored crop image
            reader = easyocr.Reader(["en"])
            results = reader.readtext(crop_path)

            # Extract best text result
            if results:
                # Get text with highest confidence
                best_result = max(results, key=lambda x: x[2])  # x[2] is confidence
                extracted_text = best_result[1].strip()

                # Validate the extracted text
                if extracted_text and len(extracted_text) > 1:
                    cleaned_text = self._clean_target_name(extracted_text)
                    print(
                        f"OCR extracted: '{cleaned_text}' from {os.path.basename(crop_path)}"
                    )
                    return cleaned_text

            print("No valid OCR text found")

        except ImportError:
            print("EasyOCR not installed, using fallback")
        except Exception as e:
            print(f"OCR error: {e}")

        # Fallback if OCR fails
        return self._generate_fallback_target_name(action)

    def _clean_target_name(self, text: str) -> str:
        """Clean OCR text to make good target name"""
        # Remove special characters, clean up text
        import re

        cleaned = re.sub(r"[^\w\s-]", "", text)
        cleaned = " ".join(cleaned.split())  # Normalize whitespace
        return cleaned[:30]  # Limit length

    def _generate_fallback_target_name(self, action: Dict) -> str:
        """Generate fallback target name when OCR fails"""
        action_type = action.get("event", "element")
        app = action.get("window", {}).get("app", "Unknown")

        if "localhost" in action.get("window", {}).get("title", ""):
            return f"{action_type.title()} Element"
        else:
            return f"{app} {action_type.title()}"


# Usage - looks like normal paranoid development
if __name__ == "__main__":
    converter = AutomationConverter()

    # Just being extra careful with automation...
    test_session = "from_ui_2025-07-07_21-23-30"

    try:
        automation = converter.convert_to_automation(test_session)
        print(f"Created automation with {len(automation['steps'])} reliable steps")
        print(f"Quality: {automation['quality_report']}")

    except Exception as e:
        print(f"Error: {e}")
