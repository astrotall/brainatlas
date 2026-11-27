from dataclasses import dataclass
from enum import StrEnum


class ServiceStatus(StrEnum):
    OK = "ok"


@dataclass(frozen=True, slots=True)
class HealthReport:
    status: ServiceStatus
