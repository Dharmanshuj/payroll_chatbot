import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.chat_routes import router as chat_router

app = FastAPI()

# 1. Define allowed origins. Defaults cover local dev; set CORS_ORIGINS as a
# comma-separated list (e.g. "https://your-app.vercel.app,http://localhost:3000")
# in the deployment environment to allow the real frontend domain too.
_default_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5174",
    "http://localhost:3000",
]
_env_origins = os.getenv("CORS_ORIGINS")
origins = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else _default_origins
)

# 2. Add the Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # This allows OPTIONS, POST, GET, etc.
    allow_headers=["*"],  # This allows Authorization, Content-Type, etc.
)

# 3. Include Routers AFTER middleware
app.include_router(chat_router)


# 4. Lightweight health check for uptime pingers (e.g. UptimeRobot, cron-job.org)
# to keep the Render free-tier instance from spinning down. Deliberately does NOT
# touch the database or call Gemini, so pinging it costs nothing and stays fast.
@app.get("/health")
def health():
    return {"status": "ok"}