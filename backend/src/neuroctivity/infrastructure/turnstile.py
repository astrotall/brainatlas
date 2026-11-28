import logging
from collections.abc import Collection
from enum import StrEnum
from http import HTTPStatus

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool, ValidationError

from neuroctivity.application.errors import Dependency, DependencyUnavailableError, HumanCheckFailedError

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
MAX_ERROR_CODES_LOGGED = 5
TOKEN_ERROR_CODES = frozenset({"missing-input-response", "invalid-input-response", "timeout-or-duplicate"})
TEST_SECRET_KEYS = frozenset(
    {
        "1x0000000000000000000000000000000AA",
        "2x0000000000000000000000000000000AA",
        "3x0000000000000000000000000000000AA",
    }
)

logger = logging.getLogger(__name__)


class Outcome(StrEnum):
    REJECTED_BY_PROVIDER = "rejected_by_provider"
    HOSTNAME = "hostname"
    PROVIDER_ERROR = "provider_error"
    TRANSPORT_ERROR = "transport_error"
    HTTP_STATUS = "http_status"
    MALFORMED_ANSWER = "malformed_answer"


class SiteverifyAnswer(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    success: StrictBool
    error_codes: list[str] = Field(default_factory=list, alias="error-codes")
    hostname: str | None = None


def unavailable(reason: Outcome, detail: str = "") -> DependencyUnavailableError:
    logger.warning("turnstile_unavailable", extra={"reason": reason.value, "detail": detail})
    return DependencyUnavailableError(Dependency.HUMAN_CHECK)


def rejected(reason: Outcome, codes: Collection[str] = ()) -> HumanCheckFailedError:
    logger.info(
        "turnstile_rejected", extra={"reason": reason.value, "codes": sorted(codes)[:MAX_ERROR_CODES_LOGGED]}
    )
    return HumanCheckFailedError()


class TurnstileVerifier:
    def __init__(self, client: httpx.AsyncClient, secret: str, hostnames: Collection[str]) -> None:
        self._client = client
        self._secret = secret
        self._hostnames = frozenset(hostnames)

    async def verify(self, token: str) -> None:
        answer = await self._siteverify(token)
        if not answer.success:
            codes = set(answer.error_codes)
            if codes - TOKEN_ERROR_CODES:
                raise unavailable(Outcome.PROVIDER_ERROR, ",".join(sorted(codes))[:64])
            raise rejected(Outcome.REJECTED_BY_PROVIDER, codes)
        if self._hostnames and answer.hostname not in self._hostnames:
            raise rejected(Outcome.HOSTNAME)

    async def _siteverify(self, token: str) -> SiteverifyAnswer:
        try:
            response = await self._client.post(
                SITEVERIFY_URL, data={"secret": self._secret, "response": token}
            )
        except httpx.HTTPError as error:
            raise unavailable(Outcome.TRANSPORT_ERROR, type(error).__name__) from None
        if response.status_code != HTTPStatus.OK:
            raise unavailable(Outcome.HTTP_STATUS, str(response.status_code))
        try:
            return SiteverifyAnswer.model_validate_json(response.content)
        except ValidationError:
            raise unavailable(Outcome.MALFORMED_ANSWER) from None
