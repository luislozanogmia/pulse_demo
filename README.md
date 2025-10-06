# MIA Pulse — Early Demo of Proactive AI Task Execution

**Built June 2025** as a personal exploration of proactive AI systems.

## Overview

**MIA Pulse** is a proof-of-concept autonomous AI system that monitors your computer environment, checks your calendar, and executes tasks without prompts.

This early demo explored calendar-triggered task automation for sales email workflows. The execution approach and learnings from this prototype influenced the development of a more robust validation layer architecture over the past 4 months.

## Demo

▶️ [Watch 2-minute demo](https://www.loom.com/share/cb3b132aae444c2d86b53e9c3b2a09d9?sid=d1c93112-ffb0-4b1c-a00d-3150ac3a9432)

Shows the system autonomously composing and sending an email after detecting a calendar task.

## How It Works

Pulse operates in two coordinated loops:

### Pulse Loop (Continuous Monitoring)
- Captures screen via OCR + System Info + Calendar info every 25 seconds (Builds context)
- Decides if there is task and time is correct and context is valid (Decides)
- Triggers Sprint Loop when conditions align (Execution of tasks)

### Sprint Loop (Task Execution)
- Validates UI state via pre-defined UI items based on the task
- Executes task steps via click and keyboard automation (PyAutoGUI)
- Logs every action for review
- Completes without human input
- Triggers Pulse Loop again

## Core Architecture

Pulse Loop monitors environment → validates context and timing → triggers Sprint Loop → Sprint executes task via coordinates → logs action → returns to Pulse Loop

## Key Design Decisions

**Proactive Operation**: System initiates tasks based on calendar + context, not user prompts

**Coordinates and OCR**: Uses OCR to see screen and coordinates to validate and execute. Accessibility APIs for reliable UI interaction instead of visual automation

**Calendar Integration**: Monitors user's calendar to understand current context and intent


**OCR Perception**: This demo uses OCR for screen sensing

## Setup

**Installation:**
```bash
pip install -r requirements.txt
```

**Run:**
1. Enable Accessibility permissions for Terminal
2. Add calendar event in format: `HH:MM||send_email||compose message to team`
3. Start pulse loop:
```bash
python run_pulse.py
```

## File Structure

- `run_pulse.py` - Main orchestration loop
- `action/` - Task execution logic
- `core/` - Core system components
- `models/` - LLM integration (Qwen)
- `reading/` - Screen sensing (OCR)
- `codex/` - Task definitions
- `api/` - System interfaces
- `screenshots/` - Pulse loop captures
- `requirements.txt` - Dependencies

## Use Case

Original use case: automating sales email workflows triggered by calendar events. Excel integration exists in codebase but is disabled in this demo version.

## Context

Built this as an exploration of AI systems that operate proactively rather than reactively. The core insight — that AI should monitor context and act independently — emerged several months before similar proactive AI concepts were announced publicly by larger companies.

## Notes

This is a proof-of-concept demo showing:
- Continuous environment monitoring
- Calendar-based task triggering
- Autonomous execution via coordinate automation
- Multi-loop coordination pattern (Pulse → Sprint → Pulse)