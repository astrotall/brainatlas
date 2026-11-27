from neuroctivity.application.health import CheckHealth
from neuroctivity.domain.health import HealthReport, ServiceStatus


def test_reports_the_service_as_ok() -> None:
    assert CheckHealth()() == HealthReport(status=ServiceStatus.OK)
