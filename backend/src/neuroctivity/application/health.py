from neuroctivity.domain.health import HealthReport, ServiceStatus


class CheckHealth:
    def __call__(self) -> HealthReport:
        return HealthReport(status=ServiceStatus.OK)
