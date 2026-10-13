import time
import logging
from app.core.config import settings
from app.core.enums import CircuitBreakerState, AppMessage, LLMProvider

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Generic primary->fallback circuit breaker.

    The original Bedrock->Groq breaker (llm_service) keeps its method names
    as thin aliases. The chat path (Gemini->Bedrock) uses the generic
    primary/fallback methods on its own instance below, so the two health
    signals never interfere with each other.
    """

    def __init__(
        self,
        cooldown_seconds: int = None,
        primary_label: str = LLMProvider.BEDROCK_QWEN.value,
        fallback_label: str = LLMProvider.GROQ_FALLBACK.value,
        probing_msg: str = None,
        recovered_msg: str = None,
        failed_msg: str = None,
        tripped_msg: str = None,
    ):
        self.cooldown_seconds = cooldown_seconds or settings.circuit_breaker_cooldown_seconds
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time: float = 0.0
        self.primary_label = primary_label
        self.fallback_label = fallback_label
        self._probing_msg = probing_msg or AppMessage.CIRCUIT_BREAKER_PROBING.value
        self._recovered_msg = recovered_msg or AppMessage.CIRCUIT_BREAKER_RECOVERED.value
        self._failed_msg = failed_msg or AppMessage.BEDROCK_FAILED.value
        self._tripped_msg = tripped_msg or AppMessage.CIRCUIT_BREAKER_TRIPPED.value

    # ---------------- generic API (used by chat Gemini->Bedrock) ---------------- #

    def can_attempt_primary(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True

        elapsed = time.time() - self.last_failure_time
        if elapsed >= self.cooldown_seconds:
            self.state = CircuitBreakerState.HALF_OPEN
            logger.info(self._probing_msg)
            return True

        return False

    def record_primary_success(self):
        if self.state != CircuitBreakerState.CLOSED:
            logger.info(self._recovered_msg)
        self.state = CircuitBreakerState.CLOSED
        self.last_failure_time = 0.0

    def record_primary_failure(self, error: Exception):
        self.last_failure_time = time.time()
        self.state = CircuitBreakerState.OPEN
        logger.warning(f"{self._failed_msg}: {error}")
        logger.warning(f"{self._tripped_msg} ({self.cooldown_seconds}s)")

    # ---------------- legacy Bedrock aliases (llm_service) ---------------- #

    def can_attempt_bedrock(self) -> bool:
        return self.can_attempt_primary()

    def record_bedrock_success(self):
        self.record_primary_success()

    def record_bedrock_failure(self, error: Exception):
        self.record_primary_failure(error)

    def get_status(self) -> dict:
        now = time.time()
        elapsed = now - self.last_failure_time if self.last_failure_time else 0
        remaining = max(0.0, self.cooldown_seconds - elapsed) if self.state == CircuitBreakerState.OPEN else 0.0
        active_provider = (
            self.primary_label
            if self.state == CircuitBreakerState.CLOSED
            else self.fallback_label
        )
        return {
            "state": self.state.value,
            "cooldown_seconds": self.cooldown_seconds,
            "seconds_remaining": round(remaining, 1),
            "last_failure_time": self.last_failure_time,
            "active_provider": active_provider,
        }


circuit_breaker = CircuitBreaker()

# Chat path: Gemini (primary, model from GEMINI_CHAT_MODEL) -> Bedrock
# (fallback, model from BEDROCK_MODEL). Separate instance: a sick Gemini must
# not trip Bedrock summaries, and vice versa.
chat_circuit_breaker = CircuitBreaker(
    primary_label=LLMProvider.GEMINI_CHAT.value,
    fallback_label=LLMProvider.BEDROCK_FALLBACK.value,
    probing_msg=AppMessage.CHAT_CIRCUIT_PROBING.value,
    recovered_msg=AppMessage.CHAT_CIRCUIT_RECOVERED.value,
    failed_msg=AppMessage.GEMINI_FAILED.value,
    tripped_msg=AppMessage.CHAT_CIRCUIT_TRIPPED.value,
)
