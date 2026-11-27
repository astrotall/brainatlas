from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from neuroctivity.application.health import CheckHealth
from neuroctivity.domain.health import ServiceStatus

HEALTH_PATH = "/health"
CHECK_HEALTH_STATE = "check_health"

router = APIRouter()


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: ServiceStatus


def check_health_use_case(request: Request) -> CheckHealth:
    use_case: object = getattr(request.app.state, CHECK_HEALTH_STATE, None)
    if not isinstance(use_case, CheckHealth):
        message = f"{CHECK_HEALTH_STATE} is not wired into the application state"
        raise TypeError(message)
    return use_case


@router.get(HEALTH_PATH)
def read_health(check_health: Annotated[CheckHealth, Depends(check_health_use_case)]) -> HealthResponse:
    return HealthResponse(status=check_health().status)
