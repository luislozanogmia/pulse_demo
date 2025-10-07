import AppKit
import Quartz
import subprocess
import psutil
import os
import json
from datetime import datetime


def get_frontmost_app() -> str:
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app else "Unknown"


def get_active_window_title() -> str:
    options = Quartz.kCGWindowListOptionOnScreenOnly
    window_list = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID)

    for window in window_list:
        owner = window.get("kCGWindowOwnerName", "")
        if owner == get_frontmost_app():
            return window.get("kCGWindowName", "Unknown")
    return "Unknown"


def get_open_apps() -> list:
    apps = AppKit.NSWorkspace.sharedWorkspace().runningApplications()
    return sorted([app.localizedName() for app in apps if app.isActive()])


def get_cpu_memory_status() -> dict:
    cpu_percent = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": f"{cpu_percent:.1f}%",
        "memory_used": f"{mem.used / (1024 ** 3):.2f} GB",
        "memory_total": f"{mem.total / (1024 ** 3):.2f} GB",
        "memory_percent": f"{mem.percent}%",
    }


def get_full_system_context(save_to_file: bool = True) -> dict:
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "app": get_frontmost_app(),
        "window": get_active_window_title(),
        "apps_open": get_open_apps(),
        "system": get_cpu_memory_status(),
    }

    if save_to_file:
        logs_dir = os.path.expanduser("~/Documents/pulse_logs/system")
        os.makedirs(logs_dir, exist_ok=True)
        output_path = os.path.join(logs_dir, "system_snapshot.json")
        with open(output_path, "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"💾 System context saved to: {output_path}")

    return snapshot
