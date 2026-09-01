"""FastAPI application for Milesight MQTT API / IOT Console backend."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.router import api_router
from app.security import AuthError

app = FastAPI(
    title="Milesight MQTT API",
    description="REST API for tof / ug65 uplink data. Backend for IOT Console.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=exc.code, content={"detail": exc.message})


app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": "milesight-mqtt-api",
        "docs": "/docs",
        "health": "/health",
        "stats": "/api/v1/stats",
    }
