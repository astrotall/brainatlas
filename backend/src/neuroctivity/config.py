from enum import StrEnum
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic.functional_validators import BeforeValidator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PRODUCTION = "production"
MIN_HASH_SECRET_LENGTH = 32
KEY_PREFIX_PATTERN = r"^[a-z0-9][a-z0-9:_\-]{0,39}$"
DEFAULT_REVIEWS_PER_HOUR = 3
DEFAULT_REVIEWS_PER_DAY = 10
DEFAULT_GLOBAL_REVIEWS_PER_DAY = 200


class StorageBackend(StrEnum):
    UPSTASH = "upstash"
    MEMORY = "memory"


class ClientIpSource(StrEnum):
    VERCEL = "vercel"
    PEER = "peer"


def comma_separated(value: object) -> object:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore", frozen=True)

    api_docs_enabled: bool = False
    vercel: str = ""
    vercel_env: str = ""

    storage_backend: StorageBackend = StorageBackend.UPSTASH
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: SecretStr | None = None
    redis_key_prefix: Annotated[str | None, Field(pattern=KEY_PREFIX_PATTERN)] = None

    turnstile_secret_key: SecretStr | None = None
    turnstile_hostnames: Annotated[list[str], NoDecode, BeforeValidator(comma_separated)] = Field(
        default_factory=list
    )
    turnstile_replay_guard: bool = True

    client_hash_secret: Annotated[SecretStr | None, Field(min_length=MIN_HASH_SECRET_LENGTH)] = None
    client_ip_source: ClientIpSource = ClientIpSource.VERCEL

    review_limit_per_hour: Annotated[int, Field(ge=1)] = DEFAULT_REVIEWS_PER_HOUR
    review_limit_per_day: Annotated[int, Field(ge=1)] = DEFAULT_REVIEWS_PER_DAY
    review_global_limit_per_day: Annotated[int, Field(ge=1)] = DEFAULT_GLOBAL_REVIEWS_PER_DAY

    @property
    def serves_api_docs(self) -> bool:
        return self.api_docs_enabled and not self.vercel

    @property
    def is_production(self) -> bool:
        return self.vercel_env == PRODUCTION
