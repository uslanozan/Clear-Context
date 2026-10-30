from fastapi import APIRouter

from clear_context.api.routes import investigations, media, system

router = APIRouter(prefix="/api")
router.include_router(system.router, tags=["system"])
router.include_router(investigations.router, tags=["investigations"])
router.include_router(media.router, tags=["media"])
