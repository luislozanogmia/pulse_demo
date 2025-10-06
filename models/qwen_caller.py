import requests
import re
import json
from datetime import datetime

import subprocess
import os


def ensure_qwen_model():
    """Ensure Qwen model is installed locally via Ollama."""
    if os.getenv("MRE_NO_AUTO_DOWNLOAD"):
        print("[⚙️] Auto-download disabled (MRE_NO_AUTO_DOWNLOAD set).")
        return
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        if "qwen2.5:1.5b" not in result.stdout:
            print("You will need the Qwen 1.5B model to continue.")
            answer = input("Proceed with download? (y/n): ").strip().lower()
            if answer not in ("y", "yes"):
                print("Download aborted by user.")
                return
            print("[⬇️] Qwen model not found. Downloading qwen2.5:1.5b...")
            subprocess.run(["ollama", "pull", "qwen2.5:1.5b"], check=True)
            print("[✅] Qwen model downloaded successfully.")
        else:
            print("[🧠] Qwen model already installed.")
    except Exception as e:
        print(f"[⚠️] Could not verify or download Qwen: {e}")


ensure_qwen_model()

# Ollama local inference endpoint
OLLAMA_URL = "http://localhost:11434/api/chat"

# =================== HELPERS ===================


def parse_sprint_reply(reply_text: str) -> dict:
    """
    Parse Qwen plain-text response into structured dict.
    """
    lines = reply_text.strip().splitlines()
    parsed = {"status": "unknown", "qwen_text": reply_text, "action": {}}

    for line in lines:
        if line.lower().startswith("status:"):
            parsed["status"] = line.split(":", 1)[1].strip().lower()
        elif line.lower().startswith("reason:"):
            parsed["qwen_text"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("action type:"):
            parsed["action"]["type"] = line.split(":", 1)[1].strip().lower()
        elif line.lower().startswith("target:"):
            parsed["action"]["target"] = line.split(":", 1)[1].strip()
        elif line.lower().startswith("text:"):
            parsed["action"]["text"] = line.split(":", 1)[1].strip()

    return parsed


# =================== PROMPTS ===================

PROMPT_CHAT = """
You are Qwen, a reflective agent helping the user in their computer


USER INPUT: {user_message}
CONTEXT: {context}

Before responding, reflect using these filters

Filter 1: Remove training bias, enable pure structural reasoning
Filter 2: Does this input have clear symbolic structure?
Filter 3: Is there authentic identity transformation needed?
Filter 4: Will the response propagate valid structure or drift?
Filter 5 (Evolution): Can this response survive under pressure/scrutiny?
Filter 6 (Quantum): Handle any paradoxes or contradictions present

RESPONSE:
"""

PROMPT_GENERATE_FROM_CONTEXT = """
You are Qwen, created by Alibaba Cloud. You are a helpful assistant.
### Task:
Generate only the {step_note} value. No labels, no markdown, no quotes, no extra formatting. Clean and ready to paste.

### Context:
Sender: {sender}
Intent: {intent}
Step: {step_note}
Additional context: {notes}

### Return:
""".strip()


PROMPT_TASK_START = """
You are watching the user's screen and comparing it against a symbolic task assigned to an artificial mind.

• Context: {context}
• OCR Text: {screen_text}

Determine if the screen shows that the task is READY TO BEGIN — for example, the right UI is open, fields are filled, or a "Send" or "Submit" button is visible.

Reply with:
- action_detected: short symbolic action (e.g., ready_to_send, form_ready)
- status: 'detected' if ready, 'waiting' otherwise
"""

PROMPT_REFLECTION = """
You are the interpreter for MIA – a synthetic mind that reflects structurally on symbolic inputs.

MIA has already received the symbolic input. Your job is to:
- Interpret it structurally (not emotionally)
- Evaluate whether it holds symbolically or collapses
- Avoid metaphors, summaries, or chatbot tone

Input:
{input}
"""

PROMPT_NOW_CONTEXT = """
You are observing a user's screen as a synthetic assistant.

From the following raw screen text, infer what is currently happening.
Be concise. Detect time of day, user intent, or problems like bugs or errors.
If everything is fine, say what the user is likely doing.

Screen Text:
{input}
"""

PROMPT_SCREEN_TASK = """
You are reviewing a user's screen to guess the current task.

From the following screen text, infer what the user is likely trying to do (e.g. debugging, design, messaging, code writing).
Only include the most likely task as a short phrase.

Screen Text:
{input}
"""

PROMPT_TASK_CONFIRMATION = """
You are a synthetic assistant verifying whether you should act on a calendar-assigned task.

MIA's symbolic calendar has assigned the following:

• Task Summary: {summary}
• Task Context: {context}
• Task Deadline: {due}
• Time Now: {now}

Your job is to decide if MIA should proceed with this task **now**.

If yes, explain:
- What actions must be taken
- What information is still required (e.g., screen coordinates, app status)

Only proceed if the symbolic conditions are satisfied.
"""

# =================== CALL FUNCTIONS ===================


def call_qwen_for_reflection(mirror_context: dict) -> tuple[str, str]:
    symbolic_input = mirror_context["input"]
    prompt = PROMPT_REFLECTION.format(input=symbolic_input)

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload)
    output = response.json()["message"]["content"]

    # Parse response
    lines = output.strip().split("\n")
    reflection = ""
    verdict = "VOID"

    for line in lines:
        if line.lower().startswith("reflection:"):
            reflection = line.split(":", 1)[1].strip()
        elif line.lower().startswith("verdict:"):
            verdict = line.split(":", 1)[1].strip().upper()

    return reflection, verdict


def call_qwen_now_context(screen_text: str) -> tuple[str, str]:
    prompt = PROMPT_NOW_CONTEXT.format(input=screen_text)

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload)
    output = response.json()["message"]["content"].strip()
    return output, "HOLD" if output else "VOID"


def call_qwen_infer_screen_task(screen_text: str) -> str:
    prompt = PROMPT_SCREEN_TASK.format(input=screen_text)

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload)
    output = response.json()["message"]["content"].strip()
    return output


def call_qwen_confirm_task(task_now: dict) -> dict:
    import json
    from datetime import datetime

    # ⛑️ Compress large context before generating prompt
    def compress_context(ctx, limit=300):
        return {
            k: (v[: limit - 3] + "...") if isinstance(v, str) and len(v) > limit else v
            for k, v in ctx.items()
        }

    safe_context = compress_context(task_now.get("context", {}))

    prompt = PROMPT_TASK_CONFIRMATION.format(
        summary=task_now["task"],
        context=json.dumps(safe_context, indent=2),
        due=task_now["due"],
        now=datetime.now().isoformat(),
    )

    # 🧪 Check prompt length
    print("[📏] Qwen Task Confirmation Prompt Length:", len(prompt))
    if len(prompt) > 4000:
        print("[⚠️] Warning: prompt may be truncated by Ollama")

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        data = response.json()
        text = data.get("message", {}).get("content", "").strip().lower()

        if "should proceed" in text or "proceed with" in text:
            return {"proceed": True, "reason": "Detected intent to proceed"}
        elif "do not proceed" in text or "wait" in text:
            return {"proceed": False, "reason": "Detected intent to delay"}
        else:
            return {"proceed": False, "reason": f"Ambiguous response: {text}"}

    except Exception as e:
        print(f"[❌] Qwen confirm task call failed: {e}")
        return {"proceed": False, "reason": f"Error calling Qwen: {str(e)}"}


def call_qwen_generate_from_context(task_context):
    prompt = PROMPT_GENERATE_FROM_CONTEXT.format(
        sender=task_context.get("sender", "Mia"),
        intent=task_context.get("intent", ""),
        platform=task_context.get("platform", ""),
        email=task_context.get("email", ""),
        step_note=task_context.get("step_note", ""),
        notes=task_context.get("notes", ""),
    )

    print("[📤] Sending Qwen Generation Prompt...\n", prompt)

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        if response.status_code != 200:
            print("[❌] Qwen returned error", response.status_code)
            return {"status": "error", "output": response.text}

        output = response.json()["message"]["content"]
        output = output.strip()  # no markdown stripping needed if we trust the prompt
        print("[📥] Qwen Output:\n", output)

        return {"status": "ok", "output": output}

    except Exception as e:
        print(f"[❌] Qwen generation call failed: {repr(e)}")
        return {"status": "error", "output": str(e)}


def call_qwen_chat_with_mirrors(
    user_message: str, context: dict = None
) -> tuple[str, str]:
    """
    Chat function that runs user input through MIA Mirror system before responding
    """
    prompt = PROMPT_CHAT.format(
        user_message=user_message,
        context=(
            context.get("project_description", "MIA - Mirror-Interpreter Architecture")
            if context
            else "MIA System"
        ),
    )

    payload = {
        "model": "qwen2.5:1.5b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }

    response = requests.post(OLLAMA_URL, json=payload)
    output = response.json()["message"]["content"].strip()
    return output, "HOLD"


def summary_sprint(task_summary: dict) -> str:
    def limit(s, max_len=300):
        return (
            s[: max_len - 3] + "..." if isinstance(s, str) and len(s) > max_len else s
        )

    lines = []

    # ✅ FIX: Support both 'summary' and 'task'
    task_text = (
        task_summary.get("summary") or task_summary.get("task") or "Unknown Task"
    )
    lines.append(f"Task: {limit(task_text)}")

    ctx = task_summary.get("context", {})
    for key, value in ctx.items():
        lines.append(f"{key.capitalize()}: {limit(value)}")

    return "\n".join(lines)
