from fastapi import FastAPI
from fastapi.routing import APIRoute

from neuroctivity.application.health import CheckHealth
from neuroctivity.config import Settings
from neuroctivity.transport import health, reviews, visits
from neuroctivity.transport.error_handlers import register_error_handlers
from neuroctivity.transport.forwarded_path import API_PREFIX
from neuroctivity.transport.health import CHECK_HEALTH_STATE
from neuroctivity.transport.middleware import register_middleware
from neuroctivity.transport.reviews import REVIEW_ENDPOINTS_STATE, ReviewEndpoints
from neuroctivity.wiring import build_review_endpoints

SERVICE_TITLE = "Neuroctivity API"
SERVICE_VERSION = "0.1.0"
DOCS_URL = f"{API_PREFIX}/docs"
OPENAPI_URL = f"{API_PREFIX}/openapi.json"


def operation_id(route: APIRoute) -> str:
    return route.name


def create_app(settings: Settings | None = None, review_endpoints: ReviewEndpoints | None = None) -> FastAPI:
    settings = settings or Settings()
    app = FastAPI(
        title=SERVICE_TITLE,
        version=SERVICE_VERSION,
        docs_url=DOCS_URL if settings.serves_api_docs else None,
        openapi_url=OPENAPI_URL,
        redoc_url=None,
        swagger_ui_oauth2_redirect_url=None,
        redirect_slashes=False,
        generate_unique_id_function=operation_id,
    )
    setattr(app.state, CHECK_HEALTH_STATE, CheckHealth())
    setattr(app.state, REVIEW_ENDPOINTS_STATE, review_endpoints or build_review_endpoints(settings))
    for router in (health.router, reviews.router, visits.router):
        app.include_router(router, prefix=API_PREFIX)
    register_error_handlers(app)
    register_middleware(app)
    return app
