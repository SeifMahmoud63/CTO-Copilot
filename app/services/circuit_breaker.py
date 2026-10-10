import time
import logging
from app.core.config import settings
from app.core.enums import CircuitBreakerState, AppMessage, LLMProvider

logger = logging.getLogger(__name__)

class CircuitBreaker:
    def __init__(self, cooldown_seconds: int = None):
        self.cooldown_seconds = cooldown_seconds or settings.circuit_breaker_cooldown_seconds
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time: float = 0.0

    def can_attempt_bedrock(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True

        elapsed = time.time() - self.last_failure_time
        if elapsed >= self.cooldown_seconds:
            self.state = CircuitBreakerState.HALF_OPEN
            logger.info(AppMessage.CIRCUIT_BREAKER_PROBING.value)
            return True

        return False

    def record_bedrock_success(self):
        if self.state != CircuitBreakerState.CLOSED:
            logger.info(AppMessage.CIRCUIT_BREAKER_RECOVERED.value)
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0.0

    def record_bedrock_failure(self, error: Exception):
        self.last_failure_time = time.time()
        self.state = CircuitBreakerState.OPEN
        logger.warning(f"{AppMessage.BEDROCK_FAILED.value}: {str(error)}")
        logger.warning(f"{AppMessage.CIRCUIT_BREAKER_TRIPPED.value} ({self.cooldown_seconds}s)")

    def get_status(self) -> dict:
        now = time.time()
        elapsed = now - self.last_failure_time if self.last_failure_time else 0
        remaining = max(0.0, self.cooldown_seconds - elapsed) if self.state == CircuitBreakerState.OPEN else 0.0
        active_provider = (
            LLMProvider.BEDROCK_QWEN.value
            if self.state == CircuitBreakerState.CLOSED
            else LLMProvider.GROQ_FALLBACK.value
        )
        return {
            "state": self.state.value,
            "cooldown_seconds": self.cooldown_seconds,
            "seconds_remaining": round(remaining, 1),
            "last_failure_time": self.last_failure_time,
            "active_provider": active_provider,
        }

circuit_breaker = CircuitBreaker()
