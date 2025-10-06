from AppKit import NSWorkspace
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListExcludeDesktopElements,
)
import pyautogui

screen_width, screen_height = pyautogui.size()


def get_window_at_coordinates(x, y):
    """Get the topmost VISIBLE window at specific screen coordinates"""
    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    window_list = CGWindowListCopyWindowInfo(options, 0)

    # Filter out problematic windows BEFORE sorting
    filtered_windows = []

    for window in window_list:
        # Skip invisible windows (alpha = 0)
        if window.get("kCGWindowAlpha", 1) == 0:
            continue

        # Skip system/background processes
        owner_name = window.get("kCGWindowOwnerName", "").lower()
        if owner_name in [
            "dock",
            "windowserver",
            "spotlight",
            "controlcenter",
            "notificationcenter",
            "systemuiserver",
            "menuextras",
            "loginwindow",
            "screensaverbg",
            "desktop",
        ]:
            continue

        # Skip windows without meaningful names (unless they're from good apps)
        window_name = window.get("kCGWindowName", "")
        if not window_name or window_name.lower() in ["", "unknown", "window"]:
            # Allow unnamed windows only from known good apps
            if owner_name not in [
                "google chrome",
                "spotify",
                "finder",
                "safari",
                "firefox",
            ]:
                continue

        # Skip tiny windows (likely system artifacts)
        bounds = window.get("kCGWindowBounds", {})
        width = bounds.get("Width", 0)
        height = bounds.get("Height", 0)
        if width < 10 or height < 10:
            continue

        # Skip windows that are way off-screen
        window_x = bounds.get("X", 0)
        window_y = bounds.get("Y", 0)
        if window_x < -1000 or window_y < -1000:
            continue

        filtered_windows.append(window)

    # NOW sort by layer (higher = more on top)
    sorted_windows = sorted(
        filtered_windows, key=lambda w: w.get("kCGWindowLayer", 0), reverse=True
    )

    # Find the topmost window containing our click
    for window in sorted_windows:
        bounds = window.get("kCGWindowBounds", {})
        window_x = bounds.get("X", 0)
        window_y = bounds.get("Y", 0)
        window_width = bounds.get("Width", 0)
        window_height = bounds.get("Height", 0)

        # Check if click is within window bounds
        if (
            window_x <= x <= window_x + window_width
            and window_y <= y <= window_y + window_height
        ):

            return {
                "title": window.get("kCGWindowName", "Unknown"),
                "app": window.get("kCGWindowOwnerName", "Unknown"),
                "pid": window.get("kCGWindowOwnerPID", 0),
                "left": window_x,
                "top": window_y,
                "width": window_width,
                "height": window_height,
                "layer": window.get("kCGWindowLayer", 0),  # Debug info
                "alpha": window.get("kCGWindowAlpha", 1),  # Debug info
            }

    # Fallback: try to get frontmost app if coordinate detection failed
    try:
        active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return {
            "title": "Main Window",
            "app": active_app.localizedName(),
            "pid": active_app.processIdentifier(),
            "left": 0,
            "top": 0,
            "width": screen_width,
            "height": screen_height,
            "layer": 0,
            "alpha": 1,
        }
    except:
        pass

    return {
        "title": "Desktop",
        "app": "Finder",
        "pid": 0,
        "left": 0,
        "top": 0,
        "width": 1920,
        "height": 1080,
        "layer": 0,
        "alpha": 1,
    }


def debug_windows_at_coordinates(x, y):
    """Debug function to see what windows are detected at coordinates"""
    options = kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements
    window_list = CGWindowListCopyWindowInfo(options, 0)

    print(f"\n🎯 Windows at coordinates ({x}, {y}):")

    for i, window in enumerate(window_list):
        bounds = window.get("kCGWindowBounds", {})
        window_x = bounds.get("X", 0)
        window_y = bounds.get("Y", 0)
        window_width = bounds.get("Width", 0)
        window_height = bounds.get("Height", 0)

        if (
            window_x <= x <= window_x + window_width
            and window_y <= y <= window_y + window_height
        ):

            print(
                f"  {i}: {window.get('kCGWindowOwnerName')} - {window.get('kCGWindowName')}"
            )
            print(
                f"     Layer: {window.get('kCGWindowLayer')}, Alpha: {window.get('kCGWindowAlpha')}"
            )
            print(
                f"     Bounds: ({window_x}, {window_y}, {window_width}, {window_height})"
            )


def calculate_replay_click(
    recorded_click: dict, target_window: dict
) -> tuple[int, int]:
    """
    Given a recorded click with relative position and a new target window,
    returns the absolute coordinates to click.

    Args:
        recorded_click: {
            "rel_position": [rel_x, rel_y],
            "window": {
                "left": ..., "top": ..., "width": ..., "height": ...
            }
        }
        target_window: {
            "left": ..., "top": ..., "width": ..., "height": ...
        }

    Returns:
        (new_x, new_y): Absolute screen coordinates
    """
    # ✅ Basic validation
    if not isinstance(recorded_click, dict) or "rel_position" not in recorded_click:
        raise ValueError("Missing 'rel_position' in recorded_click")

    if not isinstance(target_window, dict):
        raise ValueError("target_window must be a dictionary")

    if any(k not in target_window for k in ["left", "top", "width", "height"]):
        raise ValueError("target_window missing required keys")

    rel_x, rel_y = recorded_click["rel_position"]
    new_x = target_window["left"] + (rel_x * target_window["width"])
    new_y = target_window["top"] + (rel_y * target_window["height"])

    return round(new_x), round(new_y)
