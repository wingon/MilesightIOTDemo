from fastapi import APIRouter

from app.api.routes import system, tof, ug65

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(tof.router)
api_router.include_router(ug65.router)
