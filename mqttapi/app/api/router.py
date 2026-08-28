from fastapi import APIRouter

from app.api.routes import building, environment, facade, people_count, system, tof, ug65

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(tof.router)
api_router.include_router(ug65.router)
api_router.include_router(environment.router)
api_router.include_router(building.router)
api_router.include_router(facade.router)
api_router.include_router(people_count.router)
