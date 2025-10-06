from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import subprocess
import logging
from .pulse_api import router as pulse_router
from .sprint_api import router as sprint_router
from .memory_api import router as memory_router
from .vision_api import router as vision_router
from .learning_api import router as learning_router
from .automation_api import router as automation_router
from .agents_api import router as chat_route

app = FastAPI(title="MIA Platform API", version="2.0.0")

# CORS setup for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve screenshots as static files
learning_logs_path = os.path.join(
    os.path.dirname(__file__), "..", "learning", "learning_logs"
)
app.mount(
    "/Users/LAAgencia/Documents/pulse_logs/screenshots",
    StaticFiles(directory=learning_logs_path),
    name="screenshots",
)


@app.on_event("startup")
async def startup_event():
    """Initialize MIA system services on server startup"""
    logger = logging.getLogger(__name__)
    logger.info("🚀 MIA Platform starting up - initializing services...")

    try:
        # Check if pulse monitoring is already running
        pulse_check = subprocess.run(
            ["pgrep", "-f", "run_pulse"], capture_output=True, text=True
        )

        if pulse_check.returncode == 0:
            logger.info(
                f"✅ Pulse monitoring already running (PID: {pulse_check.stdout.strip()})"
            )
        else:
            # Start pulse monitoring system
            logger.info("🔍 Starting pulse monitoring system...")

            pulse_process = subprocess.Popen(
                ["python", "-m", "core.pulse"],
                cwd=os.path.dirname(os.path.dirname(__file__)),  # Go up to mia_desktop
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Give it time to start
            import time

            time.sleep(2)

            # Verify it started
            if pulse_process.poll() is None:
                logger.info(
                    f"✅ Pulse monitoring started successfully (PID: {pulse_process.pid})"
                )
            else:
                logger.error("❌ Pulse monitoring failed to start")

    except Exception as e:
        logger.error(f"❌ Failed to initialize pulse monitoring: {str(e)}")

    logger.info("🎯 MIA Platform startup complete")


# Mount API routers
app.include_router(pulse_router, prefix="/pulse")
app.include_router(sprint_router, prefix="/sprint")
app.include_router(memory_router, prefix="/memory")
app.include_router(vision_router, prefix="/vision")
app.include_router(learning_router, prefix="/learning")
app.include_router(automation_router, prefix="/automation")
app.include_router(chat_route, prefix="/api")


@app.get("/")
async def root():
    """MIA Platform Service Directory"""
    return {
        "message": "MIA Platform API v2.0",
        "architecture": "Microservices",
        "services": {
            "learning": "/learning/* - Session management",
            "automation": "/automation/* - Export & conversion",
            "pulse": "/pulse/* - System monitoring",
            "sprint": "/sprint/* - Execution engine",
            "memory": "/memory/* - Memory management",
            "vision": "/vision/* - Visual processing",
            "agents": "/api/* - Chat & agent management",
        },
        "health": "/health",
        "status": "all_services_active",
    }


@app.get("/health")
async def health_check():
    """Overall platform health"""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "services": {
            "learning": "active",
            "automation": "active",
            "pulse": "active",
            "sprint": "active",
            "memory": "active",
            "vision": "active",
        },
    }
