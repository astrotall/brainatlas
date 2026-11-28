from enum import StrEnum


class Dependency(StrEnum):
    STORE = "store"
    HUMAN_CHECK = "human_check"
    CONFIGURATION = "configuration"
    CLIENT_ADDRESS = "client_address"


class ApplicationError(Exception):
    pass


class HumanCheckFailedError(ApplicationError):
    pass


class NotificationFailedError(ApplicationError):
    pass


class RateLimitedError(ApplicationError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(f"retry after {retry_after_seconds}s")
        self.retry_after_seconds = retry_after_seconds


class DependencyUnavailableError(ApplicationError):
    def __init__(self, dependency: Dependency) -> None:
        super().__init__(dependency.value)
        self.dependency = dependency
