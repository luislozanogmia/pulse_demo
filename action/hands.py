# hands.py
import pyautogui
import json
import time
import os

# Locate this file's directory to resolve relative path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACTION_QUEUE = os.path.join(BASE_DIR, "action_queue", "action_queue.json")


def load_actions():
    if not os.path.exists(ACTION_QUEUE):
        return []
    with open(ACTION_QUEUE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def execute_action(action):
    act_type = action.get("action")

    if act_type == "click":
        pos = action.get("position", pyautogui.position())
        pyautogui.moveTo(*pos)
        pyautogui.click()

    elif act_type == "move":
        pos = action.get("position", [0, 0])
        pyautogui.moveTo(*pos)

    elif act_type == "type":
        text = action.get("text", "")
        delay = action.get("delay", 0.1)
        pyautogui.write(text, interval=delay)

    elif act_type == "hotkey":
        keys = action.get("keys", [])
        pyautogui.hotkey(*keys)

    else:
        print(f"[⚠️] Unknown action type: {act_type}")


def hands_loop():
    print("[🖐️ MIA Hands] Listening for action queue...")
    while True:
        actions = load_actions()
        if actions:
            for action in actions:
                execute_action(action)
            # Clear queue after execution
            with open(ACTION_QUEUE, "w") as f:
                f.write("[]")
        time.sleep(1)


if __name__ == "__main__":
    hands_loop()
