"""Transition-based alert evaluation to avoid repeating identical alerts at 10 Hz."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from .config import Settings
from .models import Alert, AlertSeverity, TelemetryReading


@dataclass(frozen=True, slots=True)
class _Condition:
    code: str
    severity: AlertSeverity
    active: bool
    value: float | int
    active_message: str
    recovery_message: str


class AlertEngine:
    """Emit alerts only when a condition changes state."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._active: dict[tuple[str, str], bool] = {}

    def evaluate(self, reading: TelemetryReading) -> list[Alert]:
        conditions = self._conditions(reading)
        emitted: list[Alert] = []
        for condition in conditions:
            key = (reading.device_id, condition.code)
            was_active = self._active.get(key, False)
            if condition.active == was_active:
                continue
            self._active[key] = condition.active
            if (
                condition.code == "temperature_warning"
                and was_active
                and not condition.active
                and reading.temperature_c >= self.settings.critical_temperature_c
            ):
                # Escalation is not recovery: emit only the critical transition.
                continue
            emitted.append(
                Alert(
                    id=str(uuid4()),
                    device_id=reading.device_id,
                    code=condition.code,
                    severity=(
                        condition.severity
                        if condition.active
                        else AlertSeverity.INFO
                    ),
                    message=(
                        condition.active_message
                        if condition.active
                        else condition.recovery_message
                    ),
                    active=condition.active,
                    observed_value=condition.value,
                    created_at=reading.received_at,
                )
            )
        return emitted

    def _conditions(self, reading: TelemetryReading) -> tuple[_Condition, ...]:
        critical = reading.temperature_c >= self.settings.critical_temperature_c
        warning = (
            reading.temperature_c >= self.settings.warning_temperature_c
            and not critical
        )
        battery_value = reading.battery_v if reading.battery_v is not None else 30.0
        return (
            _Condition(
                "temperature_critical",
                AlertSeverity.CRITICAL,
                critical,
                reading.temperature_c,
                f"Temperature reached {reading.temperature_c:.1f} C",
                "Temperature returned below the critical threshold",
            ),
            _Condition(
                "temperature_warning",
                AlertSeverity.WARNING,
                warning,
                reading.temperature_c,
                f"Temperature reached {reading.temperature_c:.1f} C",
                "Temperature returned below the warning threshold",
            ),
            _Condition(
                "battery_low",
                AlertSeverity.WARNING,
                reading.battery_v is not None
                and battery_value < self.settings.low_battery_v,
                battery_value,
                f"Battery voltage fell to {battery_value:.2f} V",
                "Battery voltage recovered",
            ),
            _Condition(
                "i2c_errors",
                AlertSeverity.WARNING,
                reading.i2c_errors > 0,
                reading.i2c_errors,
                f"Device reports {reading.i2c_errors} I2C errors",
                "Device I2C error counter returned to zero",
            ),
            _Condition(
                "queue_drops",
                AlertSeverity.WARNING,
                reading.queue_drops > 0,
                reading.queue_drops,
                f"Device reports {reading.queue_drops} telemetry queue drops",
                "Device queue-drop counter returned to zero",
            ),
        )
