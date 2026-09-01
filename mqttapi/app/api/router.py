from fastapi import APIRouter

from app.api.routes import (
    auth,
    building,
    environment,
    facade,
    people_count,
    system,
    system_config,
    system_dept,
    system_dict,
    system_log,
    system_login_log,
    system_menu,
    system_post,
    system_profile,
    system_role,
    system_user,
    system_whitelist,
    tof,
    ug65,
)

api_router = APIRouter()
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(system_user.router)
api_router.include_router(system_profile.router)
api_router.include_router(system_role.router)
api_router.include_router(system_menu.router)
api_router.include_router(system_log.router)
api_router.include_router(system_dept.router)
api_router.include_router(system_post.router)
api_router.include_router(system_login_log.router)
api_router.include_router(system_config.router)
api_router.include_router(system_dict.router)
api_router.include_router(system_whitelist.router)
api_router.include_router(tof.router)
api_router.include_router(ug65.router)
api_router.include_router(environment.router)
api_router.include_router(building.router)
api_router.include_router(facade.router)
api_router.include_router(people_count.router)
