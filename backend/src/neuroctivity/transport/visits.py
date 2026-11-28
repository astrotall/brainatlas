from typing import Annotated

from fastapi import APIRouter, Response
from pydantic import BaseModel, ConfigDict, Field

from neuroctivity.transport.errors import ErrorCode, RouteNotImplementedError, error_responses
from neuroctivity.transport.tags import Tag

VISIT_PATH = "/visit"
STATS_PATH = "/stats"

router = APIRouter()


class VisitStats(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    today: Annotated[int, Field(ge=0, description="Unique visitors today")]
    total: Annotated[
        int, Field(ge=0, description="Sum of daily unique visitors; a returning visitor counts again")
    ]


@router.post(
    VISIT_PATH,
    status_code=204,
    response_class=Response,
    tags=[Tag.STATS, Tag.PLANNED],
    responses=error_responses(
        ErrorCode.RATE_LIMITED, ErrorCode.NOT_IMPLEMENTED, ErrorCode.SERVICE_UNAVAILABLE
    ),
)
def record_visit() -> None:
    raise RouteNotImplementedError


@router.get(
    STATS_PATH,
    tags=[Tag.STATS, Tag.PLANNED],
    responses=error_responses(ErrorCode.NOT_IMPLEMENTED, ErrorCode.SERVICE_UNAVAILABLE),
)
def read_stats() -> VisitStats:
    raise RouteNotImplementedError
