"""FastAPI application for Milesight MQTT API / IOT Console backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router

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

app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": "milesight-mqtt-api",
        "docs": "/docs",
        "health": "/health",
        "stats": "/api/v1/stats",
    }
