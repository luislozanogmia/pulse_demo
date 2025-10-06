import os
import json

# import cv2 disabled for demo
from PIL import Image

# 🧠 Custom module imports
from reading.run_computer_vision import run_computer_vision
from reading.run_ocr_mac_native import run_ocr_mac_native

print("[🧠] vision_fusion.py loaded — OCR-only demo mode (CV off).")

# 🔕 Demo flags
VISION_ENABLED = False  # CV layer OFF for demo

DEBUG = False


def _log(msg: str) -> None:
    if DEBUG:
        print(msg)


def _build_ocr_blocks(ocr_result: dict, normalize_topdown: bool = False) -> list:
    """Convert OCR result into standardized treasure-map blocks."""
    blocks = []
    for block in ocr_result.get("text_blocks", []):
        text = block.get("text", "").strip()
        bbox = block.get("bbox", [])
        if text and isinstance(bbox, (list, tuple)) and len(bbox) == 4:
            x, y, w, h = bbox
            if normalize_topdown:
                y = 1 - y - h
                bbox = [x, y, w, h]
            blocks.append(
                {"type": "text", "label": text, "position": bbox, "source": "ocr"}
            )
    return blocks


def iou(boxA: list, boxB: list) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[0] + boxA[2], boxB[0] + boxB[2])
    yB = min(boxA[1] + boxA[3], boxB[1] + boxB[3])
    interWidth = max(0, xB - xA)
    interHeight = max(0, yB - yA)
    interArea = interWidth * interHeight
    boxAArea = boxA[2] * boxA[3]
    boxBArea = boxB[2] * boxB[3]
    return interArea / float(boxAArea + boxBArea - interArea + 1e-6)


def is_center_near(boxA: list, boxB: list, threshold: float = 30) -> bool:
    ax, ay, aw, ah = boxA
    bx, by, bw, bh = boxB
    centerA = (ax + aw / 2, ay + ah / 2)
    centerB = (bx + bw / 2, by + bh / 2)
    dist = ((centerA[0] - centerB[0]) ** 2 + (centerA[1] - centerB[1]) ** 2) ** 0.5
    return dist < threshold


def generate_treasure_map(image_path: str) -> list:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    timestamp = (
        os.path.basename(image_path).replace("screenshot_", "").replace(".png", "")
    )
    is_sprint = "sprint_" in os.path.basename(image_path)

    ocr_result = run_ocr_mac_native(image_path, timestamp, is_sprint)
    # Vision disabled for demo; keep OCR-only blocks
    ui_blocks = run_computer_vision(image_path, timestamp) if VISION_ENABLED else []

    text_blocks = _build_ocr_blocks(ocr_result, normalize_topdown=False)

    treasure_map = text_blocks + ui_blocks

    out_path = os.path.join("reading", "vc", f"treasure_map_{timestamp}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(treasure_map, f, indent=2, ensure_ascii=False)
    print(f"[🧭] Final treasure map saved to: {out_path}")

    return treasure_map


def generate_combined_treasure_map(image_path: str) -> list:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    timestamp = (
        os.path.basename(image_path).replace("screenshot_", "").replace(".png", "")
    )
    is_sprint = "sprint_" in os.path.basename(image_path)

    # 🔕 Demo: if vision is disabled, return OCR-only map and skip CV fusion
    if not VISION_ENABLED:
        ocr_result = run_ocr_mac_native(image_path, timestamp, is_sprint)
        ocr_blocks = _build_ocr_blocks(ocr_result, normalize_topdown=True)

        out_path = os.path.join(
            "reading", "vc", f"treasure_map_combined_{timestamp}.json"
        )
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(ocr_blocks, f, indent=2, ensure_ascii=False)
        print(
            f"[🧭] Combined treasure map (OCR-only, CV disabled) saved to: {out_path}"
        )
        return ocr_blocks

    image = cv2.imread(image_path)
    height, width = image.shape[:2]
    ocr_result = run_ocr_mac_native(image_path, timestamp, is_sprint)
    ui_blocks = run_computer_vision(image_path, timestamp)

    ocr_blocks = _build_ocr_blocks(ocr_result, normalize_topdown=True)

    cv_blocks = [
        block
        for block in ui_blocks
        if isinstance(block, dict) and block.get("source") == "cv"
    ]

    matched_ocr = set()
    matched_cv = set()
    final_blocks = []

    for i, ocr in enumerate(ocr_blocks):
        ocr_bbox = ocr["position"]
        for j, cv in enumerate(cv_blocks):
            cv_bbox = cv["position"]
            cv_norm = [
                cv_bbox[0] / float(width),
                cv_bbox[1] / float(height),
                cv_bbox[2] / float(width),
                cv_bbox[3] / float(height),
            ]
            iou_val = iou(ocr_bbox, cv_norm)
            ocr_pix = [
                ocr_bbox[0] * float(width),
                ocr_bbox[1] * float(height),
                ocr_bbox[2] * float(width),
                ocr_bbox[3] * float(height),
            ]
            if iou_val > 0.05 or is_center_near(ocr_pix, cv_bbox):
                matched_ocr.add(i)
                matched_cv.add(j)
                final_blocks.append(
                    {
                        "type": "block",
                        "label": ocr["label"],
                        "position": ocr["position"],
                        "source": "overlapping",
                    }
                )

    for i, ocr in enumerate(ocr_blocks):
        if i not in matched_ocr:
            final_blocks.append(ocr)

    for j, cv in enumerate(cv_blocks):
        if j not in matched_cv:
            final_blocks.append(cv)

    out_path = os.path.join("reading", "vc", f"treasure_map_combined_{timestamp}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(final_blocks, f, indent=2, ensure_ascii=False)
    print(f"[🧭] Combined treasure map (OCR+CV) saved to: {out_path}")

    return final_blocks


def match_target_in_treasure_map(
    treasure_map: list, target: str, return_all: bool = False
):
    """
    Generic treasure map matching with intelligent prioritization
    Works across different apps and UI patterns
    """
    if not treasure_map or not target:
        return None

    # Find all potential matches
    matches = []
    target_lower = target.lower().strip()

    for block in treasure_map:
        # Safety check: skip if block is not a dictionary
        if not isinstance(block, dict):
            continue

        label = block.get("label", "").lower().strip()
        if target_lower in label or label in target_lower:
            similarity = calculate_match_quality(target_lower, label)
            if similarity > 0.5:  # Only consider decent matches
                matches.append(
                    {"block": block, "similarity": similarity, "label": label}
                )

    if not matches:
        return None

    # Handle return_all parameter for backward compatibility
    if return_all:
        return [match["block"] for match in matches]

    if len(matches) == 1:
        return matches[0]["block"]

    # Multiple matches found - use generic scoring
    _log(f"[🎯] Multiple matches found for '{target}': {len(matches)} candidates")

    scored_matches = []
    for match in matches:
        score = score_match_generically(match, target_lower)
        scored_matches.append((score, match))
        _log(f"[📊] '{match['label'][:30]}...' → Score: {score:.2f}")

    # Return highest scored match
    best_score, best_match = max(scored_matches, key=lambda x: x[0])
    _log(f"[🏆] Selected: '{best_match['label'][:30]}...' (Score: {best_score:.2f})")

    return best_match["block"]


def calculate_match_quality(target: str, label: str) -> float:
    """Calculate how well a label matches the target (0.0 to 1.0)"""
    from difflib import SequenceMatcher

    # Exact match gets highest score
    if target == label:
        return 1.0

    # Check if target is completely contained in label
    if target in label:
        return 0.9 + (len(target) / len(label)) * 0.1

    # Use sequence matching for fuzzy similarity
    similarity = SequenceMatcher(None, target, label).ratio()
    return similarity


def score_match_generically(match: dict, target: str) -> float:
    """
    Generic scoring system that works across different UI patterns
    Higher scores = better matches
    """
    block = match["block"]

    # Safety check: ensure block is a dictionary
    if not isinstance(block, dict):
        return 0.0

    label = match["label"]
    position = block.get("position", [0, 0, 0, 0])
    source = block.get("source", "")

    # Safety check: ensure position exists and has 4 values
    if not isinstance(position, (list, tuple)) or len(position) != 4:
        return 0.0

    x, y, w, h = position
    score = 0.0

    # 1. MATCH QUALITY (40% of score)
    similarity = match.get("similarity", 0.0)
    score += similarity * 40

    # 2. SIZE PREFERENCE (20% of score)
    # Larger elements are usually better click targets
    element_area = w * h
    size_score = min(element_area * 100, 10)  # Cap at reasonable size
    score += size_score * 2

    # 3. POSITION PREFERENCE (20% of score)
    # Prefer content areas over navigation/headers
    position_score = 0

    # Prefer middle areas of screen
    if 0.2 < x < 0.8 and 0.2 < y < 0.8:
        position_score += 8
    elif 0.1 < x < 0.9 and 0.1 < y < 0.9:
        position_score += 5
    else:
        position_score += 2

    # Slight preference for lower on screen (content vs headers)
    if y > 0.3:
        position_score += 2

    score += position_score

    # 4. UI PATTERN RECOGNITION (15% of score)
    ui_score = 0

    # Prefer interactive-looking elements
    interactive_indicators = ["button", "•", ">", "→", "click"]
    if any(indicator in label for indicator in interactive_indicators):
        ui_score += 8

    # Penalize obvious non-clickable elements
    non_clickable = ["label:", "title:", "header:", "breadcrumb"]
    if any(indicator in label for indicator in non_clickable):
        ui_score -= 5

    # Penalize search/input elements when looking for results
    search_indicators = ["search", "input", "|", "type here", "enter "]
    if any(indicator in label for indicator in search_indicators):
        ui_score -= 3

    score += ui_score * 1.5

    # 5. SOURCE QUALITY (5% of score)
    # Some sources might be more reliable
    source_score = 0
    if source == "ocr":
        source_score += 3
    elif source == "overlapping":
        source_score += 5
    elif source == "cv":
        source_score += 4

    score += source_score

    return max(score, 0.0)  # Ensure non-negative score


def draw_treasure_map(image_path: str, treasure_map: list, output_path: str) -> None:
    image = cv2.imread(image_path)
    height, width = image.shape[:2]

    for block in treasure_map:
        # Safety check: skip if block is not a dictionary
        if not isinstance(block, dict):
            continue

        label = block.get("label", "").strip()
        source = block.get("source", "")

        # Safety check: ensure position exists and has 4 values
        position = block.get("position", [])
        if not isinstance(position, (list, tuple)) or len(position) != 4:
            continue

        x, y, w, h = position

        # Convert normalized coordinates to pixels
        if source in ["ocr", "overlapping"]:
            x = int(x * width)
            y = int(y * height)
            w = int(w * width)
            h = int(h * height)

        if source == "ocr":
            underline_y = y + h - 2
            cv2.line(
                image, (x, underline_y), (x + w, underline_y), (0, 0, 255), 2
            )  # Red
        elif source == "cv":
            cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)  # Green
        elif source == "overlapping":
            cv2.rectangle(image, (x, y), (x + w, y + h), (255, 0, 255), 2)  # Magenta
            if label:
                cv2.putText(
                    image,
                    label,
                    (x, y - 8),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    2,
                )

    cv2.imwrite(output_path, image)
    print(f"[📸] Output image saved to: {output_path}")


def generate_treasure_map_omni(image_path):
    """OmniParser removed for demo: use OCR path instead."""
    raise RuntimeError(
        "OmniParser is removed in demo mode. Use generate_treasure_map or generate_combined_treasure_map."
    )


def match_blocks_to_click(
    click_pos: tuple, treasure_map: list, threshold: float = 0.02
) -> list:
    """
    Given a click position (x, y) in normalized coords, return blocks whose center is near the click.
    Assumes treasure_map blocks have [x, y, w, h] format with Y from top-down.
    """
    if not click_pos or not treasure_map:
        return []

    click_x, click_y = click_pos

    # ✅ Convert Y to match top-down system (e.g., OpenCV and OCR)
    click_y = 1.0 - click_y

    matches = []

    for block in treasure_map:
        # Safety check: skip if block is not a dictionary
        if not isinstance(block, dict):
            continue

        pos = block.get("position") or block.get("box")
        if not pos or len(pos) != 4:
            continue

        bx, by, bw, bh = pos
        center_x = bx + bw / 2
        center_y = by + bh / 2

        dx = abs(center_x - click_x)
        dy = abs(center_y - click_y)

        if dx < threshold and dy < threshold:
            matches.append(block)

    return matches


def generate_pixel_treasure_map(image_path: str) -> list:
    """
    Loads the treasure map and converts all bounding boxes to absolute pixel coordinates.
    Returns the same structure but with `pixel_position` field added.
    """
    import json
    import os
    from PIL import Image

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    base_name = os.path.basename(image_path).replace(".png", "")
    json_name = f"treasure_map_combined_{base_name}.json"
    json_path = os.path.join("reading", "vc", json_name)

    with open(json_path, "r") as f:
        treasure_map = json.load(f)

    img = Image.open(image_path)
    width, height = img.size

    for block in treasure_map:
        # Safety check: skip if block is not a dictionary
        if not isinstance(block, dict):
            continue

        if (
            "position" in block
            and isinstance(block["position"], list)
            and len(block["position"]) == 4
        ):
            x, y, w, h = block["position"]
            abs_x = int(x * width)
            abs_y = int(y * height)
            abs_w = int(w * width)
            abs_h = int(h * height)
            block["pixel_position"] = [abs_x, abs_y, abs_w, abs_h]

    return treasure_map
