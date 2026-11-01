from fastapi import APIRouter

from clear_context.api.routes import groups, investigations, media, settings, system

router = APIRouter(prefix="/api")
router.include_router(system.router, tags=["system"])
router.include_router(investigations.router, tags=["investigations"])
router.include_router(media.router, tags=["media"])
router.include_router(settings.router, tags=["settings"])
router.include_router(groups.router, tags=["history"])
