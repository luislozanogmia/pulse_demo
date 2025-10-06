"""
Monolithic 'reading' module for the Pulse demo.

Includes:
- macOS-native OCR via Vision + Quartz + AppKit
- Screenshot helpers (PIL first, pyautogui fallback)
- OCR reconstruction into readable lines
- Simple parser to convert OCR JSON into a symbolic scene

Intent: one-file drop-in for the public demo repository.
"""

from __future__ import annotations

import sys
import os
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# macOS frameworks
import Quartz
import Vision
import AppKit

# Pillow
from PIL import Image, ImageGrab, ImageDraw

# Optional dependency; used as fallback only
try:
    import pyautogui  # type: ignore
except Exception:  # pragma: no cover
    pyautogui = None  # Fallback handled in _grab_screenshot


# ------------------------------------------------------------------------------
# Small logging helper
# ------------------------------------------------------------------------------
SILENT = False  # set True to quiet console prints


def _log(msg: str) -> None:
    if not SILENT:
        print(msg)


# ------------------------------------------------------------------------------
# Screenshot utilities (kept local to this file for demo simplicity)
# ------------------------------------------------------------------------------
def _timestamp() -> str:
    """Filesystem-safe timestamp: 2025-10-04T12-34-56-123456"""
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S-%f")


def _ensure_dir(folder: str | Path) -> Path:
    p = Path(folder)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _save_image(img: Image.Image, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    _log(f"[🖼️] Screenshot saved: {path}")
    return path


def _grab_screenshot() -> Image.Image:
    """
    Grab a screenshot using PIL first. If unavailable, try pyautogui.
    Avoids hard dependencies in restricted contexts.
    """
    try:
        return ImageGrab.grab()
    except Exception:
        if pyautogui is None:
            raise RuntimeError(
                "Screenshot not available: PIL.ImageGrab failed and pyautogui is not installed."
            )
        return pyautogui.screenshot()


def take_timestamped_screenshot(
    folder: str = "/Users/LAAgencia/Documents/pulse_logs/screenshots",
) -> str:
    """
    Take a full-screen screenshot with a timestamped filename.
    Returns absolute path as string.
    """
    folder_path = _ensure_dir(folder)
    filename = f"screenshot_{_timestamp()}.png"
    path = folder_path / filename
    img = _grab_screenshot()
    return str(_save_image(img, path))


def take_named_screenshot(
    filename: str, folder: str = "/Users/LAAgencia/Documents/pulse_logs/screenshots"
) -> str:
    """
    Take a full-screen screenshot saved as `filename` under `folder`.
    Returns absolute path as string.
    """
    folder_path = _ensure_dir(folder)
    safe_name = Path(filename).name
    path = folder_path / safe_name
    img = _grab_screenshot()
    return str(_save_image(img, path))


def take_cropped_screenshot(
    center_x: int,
    center_y: int,
    crop_size: int = 30,
    folder: str = "/Users/LAAgencia/Documents/pulse_logs/screenshots/ocr_crops",
) -> str:
    """
    Take a cropped screenshot around specific coordinates for OCR.

    crop_size: width/height of the square crop in pixels.
    Returns absolute path as string.
    """
    img = _grab_screenshot()

    half = max(1, int(crop_size) // 2)
    left = max(0, int(center_x) - half)
    top = max(0, int(center_y) - half)
    right = min(img.width, int(center_x) + half)
    bottom = min(img.height, int(center_y) + half)

    # Handle degenerate near-edge cases
    if right <= left:
        right = min(img.width, left + max(1, crop_size))
    if bottom <= top:
        bottom = min(img.height, top + max(1, crop_size))

    cropped = img.crop((left, top, right, bottom))

    folder_path = _ensure_dir(folder)
    filename = f"crop_{center_x}_{center_y}_{_timestamp()}.png"
    path = folder_path / filename
    _log(
        f"[🔍] OCR crop bounds: ({left},{top})–({right},{bottom}) @ {img.width}x{img.height}"
    )
    return str(_save_image(cropped, path))


def take_screenshot_with_red_dot(
    x: int,
    y: int,
    filename: str,
    folder: str = "/Users/LAAgencia/Documents/pulse_logs/screenshots",
    dot_radius: int = 8,
) -> str:
    """
    Take screenshot with a red dot centered at (x, y).
    Returns absolute path as string.
    """
    img = _grab_screenshot()

    draw = ImageDraw.Draw(img)
    draw.ellipse(
        [(x - dot_radius, y - dot_radius), (x + dot_radius, y + dot_radius)],
        fill="red",
        outline="black",
    )

    folder_path = _ensure_dir(folder)
    safe_name = Path(filename).name
    path = folder_path / safe_name
    return str(_save_image(img, path))


# ------------------------------------------------------------------------------
# OCR reconstruction helpers (kept simple, top-to-bottom line building)
# ------------------------------------------------------------------------------
def reconstruct_text_from_ocr(
    raw_blocks: List[Dict[str, Any]],
    y_tolerance: float = 0.015,
    x_tolerance: float = 0.02,
) -> List[str]:
    """
    Reconstructs OCR output into readable, line-ordered text.

    raw_blocks: list of dicts with 'text' and 'bbox' keys in Vision's normalized coords.
    y_tolerance: max vertical difference to treat as same line (normalized units)
    x_tolerance: controls spacing threshold for inserting spaces (normalized units)

    Returns a list of text lines, top to bottom.
    """
    # 1) Filter and normalize
    blocks = [
        {
            "text": b["text"].strip(),
            "x": round(float(b["bbox"][0]), 3),
            "y": round(float(b["bbox"][1]), 3),
        }
        for b in raw_blocks
        if isinstance(b, dict) and "text" in b and b["text"] and str(b["text"]).strip()
    ]

    # 2) Group into lines based on Y (Vision bbox origin is bottom-left; higher y is higher on screen)
    lines: List[Dict[str, Any]] = []
    for block in sorted(blocks, key=lambda b: -b["y"]):  # top to bottom
        placed = False
        for line in lines:
            if math.isclose(block["y"], line["y"], abs_tol=y_tolerance):
                line["blocks"].append(block)
                placed = True
                break
        if not placed:
            lines.append({"y": block["y"], "blocks": [block]})

    # 3) Sort and merge blocks within each line
    reconstructed_lines: List[str] = []
    for line in lines:
        sorted_blocks = sorted(line["blocks"], key=lambda b: b["x"])
        line_text = ""
        prev_x: Optional[float] = None
        for block in sorted_blocks:
            if prev_x is not None:
                gap = block["x"] - prev_x
                if gap > x_tolerance:
                    line_text += " "
            line_text += block["text"]
            prev_x = block["x"] + len(block["text"]) * 0.01  # crude width estimate
        reconstructed_lines.append(line_text)

    return reconstructed_lines


# ------------------------------------------------------------------------------
# macOS-native OCR
# ------------------------------------------------------------------------------
def run_ocr_mac_native(
    image_path: str, timestamp: Optional[str] = None, is_sprint: bool = False
) -> Dict[str, Any]:
    """
    Run macOS Vision OCR over an image path.

    If `timestamp` is provided, auto-saves JSON into /Users/LAAgencia/Documents/pulse_logs/ocr/.
    If `is_sprint` is True, writes to ocr_sprint_<ts>.json; else ocr_<ts>.json.
    """
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Load image as NSImage
    ns_image = AppKit.NSImage.alloc().initWithContentsOfFile_(image_path)
    if ns_image is None:
        raise RuntimeError(f"Failed to load image with AppKit: {image_path}")

    image_data = ns_image.TIFFRepresentation()
    if image_data is None:
        raise RuntimeError("Failed to get TIFFRepresentation from NSImage.")

    image_source = Quartz.CGImageSourceCreateWithData(image_data, None)
    cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)
    if cg_image is None:
        raise RuntimeError("Failed to create CGImage for OCR.")

    # Initialize OCR handler
    request_handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
        cg_image, None
    )
    results: List[Dict[str, Any]] = []

    def handle_request(request, error):
        for obs in request.results():
            if isinstance(obs, Vision.VNRecognizedTextObservation):
                top_candidate = obs.topCandidates_(1)
                if top_candidate and len(top_candidate) > 0:
                    text = top_candidate[0].string()
                    bbox_origin = obs.boundingBox().origin
                    bbox_size = obs.boundingBox().size
                    bbox = [
                        float(bbox_origin.x),
                        float(bbox_origin.y),
                        float(bbox_size.width),
                        float(bbox_size.height),
                    ]
                    results.append({"text": text, "bbox": bbox})

    # Configure OCR request
    request = Vision.VNRecognizeTextRequest.alloc().initWithCompletionHandler_(
        handle_request
    )
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setUsesLanguageCorrection_(True)

    success, error = request_handler.performRequests_error_([request], None)
    if not success:
        _log(f"OCR failed: {error}")
        return {}

    # Reconstruct clean text lines
    reconstructed_lines = reconstruct_text_from_ocr(results)

    ocr_result: Dict[str, Any] = {
        "text_blocks": results,
        "reconstructed_text": "\n".join(reconstructed_lines),
    }

    # ✅ Save based on timestamp and sprint flag
    if timestamp:
        # Always write relative to this module folder for stability
        module_dir = Path(os.path.expanduser("~/Documents/pulse_logs"))
        out_dir = module_dir / "ocr"
        out_dir.mkdir(parents=True, exist_ok=True)
        filename = (
            f"ocr_sprint_{timestamp}.json" if is_sprint else f"ocr_{timestamp}.json"
        )
        output_path = out_dir / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(ocr_result, f, indent=2, ensure_ascii=False)
        _log(f"[💾] OCR auto-saved to: {output_path}")

    return ocr_result


# ------------------------------------------------------------------------------
# Lightweight OCR JSON → symbolic scene parser
# ------------------------------------------------------------------------------
def parse_visible_text(ocr_json_path: str) -> Dict[str, Any]:
    """
    Load OCR JSON and format into a minimal symbolic scene for downstream use.
    """
    with open(ocr_json_path, "r", encoding="utf-8") as f:
        ocr_data = json.load(f)

    raw_blocks = ocr_data.get("text_blocks", [])
    blocks = [
        {"text": b["text"].strip(), "y": round(float(b["bbox"][1]), 3)}
        for b in raw_blocks
        if isinstance(b, dict) and "text" in b and str(b["text"]).strip()
    ]
    # Vision uses origin at bottom-left. Higher y = higher on screen.
    blocks.sort(key=lambda b: -b["y"])  # top-to-bottom

    return {
        "app": "Unknown",  # Filled in later by focus logic or top text
        "window": "Unknown",
        "text_blocks": blocks,
        "llm_task_guess": None,
        "reflection_ready": bool(blocks),
    }


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------
def _usage() -> None:
    print(
        "Usage:\n"
        "  python run_ocr_mac_native.py <image_path>\n"
        "  python run_ocr_mac_native.py --screenshot [--sprint]\n"
        "  python run_ocr_mac_native.py --parse <ocr_json_path>\n"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _usage()
        sys.exit(1)

    mode = sys.argv[1]

    # Mode 1: parse an OCR JSON into a symbolic scene
    if mode == "--parse":
        if len(sys.argv) != 3:
            _usage()
            sys.exit(1)
        ocr_json_path = sys.argv[2]
        scene = parse_visible_text(ocr_json_path)
        module_dir = Path(__file__).resolve().parent
        out_dir = module_dir / "parsed"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = out_dir / "symbolic_scene.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(scene, f, indent=2, ensure_ascii=False)
        print(f"✅ Parsed symbolic scene saved to: {output_path}")
        sys.exit(0)

    # Mode 2: take a screenshot and OCR it
    if mode == "--screenshot":
        is_sprint = "--sprint" in sys.argv
        module_dir = Path(__file__).resolve().parent
        shots_dir = module_dir / "screenshots"
        shots_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = take_timestamped_screenshot(str(shots_dir))
        ts = Path(screenshot_path).stem.replace("screenshot_", "")
        result = run_ocr_mac_native(screenshot_path, timestamp=ts, is_sprint=is_sprint)
        print(
            f"✅ OCR complete. {len(result.get('text_blocks', []))} text items found."
        )
        sys.exit(0)

    # Mode 3: direct image path OCR
    image_path = mode
    ts = _timestamp()
    result = run_ocr_mac_native(image_path, timestamp=ts, is_sprint=False)
    print(f"✅ OCR complete. {len(result.get('text_blocks', []))} text items found.")
    for r in result.get("text_blocks", []):
        print(f"- {r['text']} @ {r['bbox']}")

    # Save OCR output to pulse_logs/ocr
    out_dir = Path(os.path.expanduser("~/Documents/pulse_logs/ocr"))
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"ocr_{ts}.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"💾 OCR result saved to: {output_path}")
