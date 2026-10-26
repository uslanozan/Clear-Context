from fastapi import APIRouter

from clear_context.api.routes import investigations, system

router = APIRouter(prefix="/api")
router.include_router(system.router, tags=["system"])
router.include_router(investigations.router, tags=["investigations"])
