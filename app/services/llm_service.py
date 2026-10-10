import logging
from typing import Tuple
from openai import OpenAI
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings
from app.core.enums import (
    LLMProvider,
    SystemPrompt,
    CircuitBreakerState,
    AppMessage
)
from app.services.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self):
        # Bedrock Mantle OpenAI-compatible client for Qwen
        self.bedrock_client = OpenAI(
            api_key=settings.bedrock_api_key,
            base_url=settings.bedrock_base_url_qwen,
            default_headers={"Authorization": f"Bearer {settings.bedrock_api_key}"}
        )

    def _call_bedrock(self, prompt: str) -> str:
        response = self.bedrock_client.chat.completions.create(
            model=settings.bedrock_model,
            messages=[
                {"role": "system", "content": SystemPrompt.PR_SUMMARIZER.value},
                {"role": "user", "content": prompt}
            ],
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            timeout=30.0
        )
        return response.choices[0].message.content.strip()

    def _probe_bedrock(self) -> bool:
        """Sends a lightweight mock probe to test if Bedrock is healthy."""
        try:
            self.bedrock_client.chat.completions.create(
                model=settings.bedrock_model,
                messages=[{"role": "user", "content": settings.circuit_breaker_probe_prompt}],
                max_tokens=5,
                timeout=10.0
            )
            return True
        except Exception as e:
            logger.warning(f"{AppMessage.CIRCUIT_BREAKER_PROBE_FAILED.value}: {e}")
            return False

    def _call_groq_langchain(self, prompt: str) -> str:
        """Fallback to Groq using LangChain ChatGroq."""
        messages = [
            SystemMessage(content=SystemPrompt.PR_SUMMARIZER.value),
            HumanMessage(content=prompt)
        ]
        try:
            chat = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens
            )
            ai_msg = chat.invoke(messages)
            return str(ai_msg.content).strip()
        except Exception as e:
            logger.warning(f"Groq with model {settings.groq_model} failed ({e}), attempting backup model {settings.groq_backup_model}")
            chat = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_backup_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens
            )
            ai_msg = chat.invoke(messages)
            return str(ai_msg.content).strip()

    def generate_pr_summary(self, prompt: str) -> Tuple[str, LLMProvider]:
        """
        Executes summary generation with Circuit Breaker logic:
        1. Checks if Bedrock can be attempted (state is CLOSED or HALF_OPEN).
        2. In HALF_OPEN, sends a mock probe first.
        3. If Bedrock succeeds, updates circuit breaker and returns.
        4. If Bedrock fails, trips circuit breaker to OPEN (30 min cooldown) and fails over to Groq.
        """
        can_try = circuit_breaker.can_attempt_bedrock()

        if can_try:
            # If in probe state (HALF_OPEN), test health first
            if circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
                if not self._probe_bedrock():
                    circuit_breaker.record_bedrock_failure(Exception("Probe request failed"))
                    summary = self._call_groq_langchain(prompt)
                    return summary, LLMProvider.GROQ_FALLBACK

            try:
                summary = self._call_bedrock(prompt)
                circuit_breaker.record_bedrock_success()
                return summary, LLMProvider.BEDROCK_QWEN
            except Exception as e:
                circuit_breaker.record_bedrock_failure(e)
                # Fallback to Groq with LangChain
                summary = self._call_groq_langchain(prompt)
                return summary, LLMProvider.GROQ_FALLBACK
        else:
            # Circuit breaker is OPEN - directly invoke Groq
            logger.info("Circuit breaker active. Using Groq fallback.")
            summary = self._call_groq_langchain(prompt)
            return summary, LLMProvider.GROQ_FALLBACK

llm_service = LLMService()
