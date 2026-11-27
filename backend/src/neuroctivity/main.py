from fastapi import FastAPI

from neuroctivity.application.health import CheckHealth
from neuroctivity.transport import health
from neuroctivity.transport.health import CHECK_HEALTH_STATE

API_PREFIX = "/api"
SERVICE_TITLE = "Neuroctivity API"
SERVICE_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(
        title=SERVICE_TITLE,
        version=SERVICE_VERSION,
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        redoc_url=None,
    )
    setattr(app.state, CHECK_HEALTH_STATE, CheckHealth())
    app.include_router(health.router, prefix=API_PREFIX)
    return app
