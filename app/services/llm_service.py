import logging
from typing import Optional, Tuple
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
        # Bedrock Mantle OpenAI-compatible client (primary model from settings)
        self.bedrock_client = OpenAI(
            api_key=settings.bedrock_api_key,
            base_url=settings.bedrock_base_url_qwen,
            default_headers={"Authorization": f"Bearer {settings.bedrock_api_key}"}
        )

    def _call_bedrock(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        response = self.bedrock_client.chat.completions.create(
            model=settings.bedrock_model,
            messages=[
                {"role": "system", "content": system_prompt or SystemPrompt.PR_SUMMARIZER.value},
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

    def _call_groq_langchain(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[str, str]:
        """Fallback to Groq using LangChain ChatGroq."""
        messages = [
            SystemMessage(content=system_prompt or SystemPrompt.PR_SUMMARIZER.value),
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
            logger.info(
                "Summary reply via Groq fallback model '%s'.", settings.groq_model)
            return str(ai_msg.content).strip(), settings.groq_model
        except Exception as e:
            logger.warning(
                f"Groq model '{settings.groq_model}' failed, attempting backup model "
                f"'{settings.groq_backup_model}'.", exc_info=True)
            chat = ChatGroq(
                api_key=settings.groq_api_key,
                model_name=settings.groq_backup_model,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens
            )
            ai_msg = chat.invoke(messages)
            logger.info(
                "Summary reply via Groq backup model '%s'.", settings.groq_backup_model)
            return str(ai_msg.content).strip(), settings.groq_backup_model

    def generate_pr_summary(self, prompt: str, system_prompt: Optional[str] = None) -> Tuple[str, LLMProvider, str]:
        """Generate summary through Bedrock, falling back to Groq if breaker is tripped.

        `system_prompt` overrides the default PR summarizer (e.g. email triage).
        """
        can_try = circuit_breaker.can_attempt_bedrock()

        if can_try:
            # Probe before sending full payload when half-open
            if circuit_breaker.state == CircuitBreakerState.HALF_OPEN:
                if not self._probe_bedrock():
                    circuit_breaker.record_bedrock_failure(Exception("Probe request failed"))
                    summary, model_used = self._call_groq_langchain(prompt, system_prompt)
                    return summary, LLMProvider.GROQ_FALLBACK, model_used

            try:
                summary = self._call_bedrock(prompt, system_prompt)
                circuit_breaker.record_bedrock_success()
                logger.info(
                    "Summary reply via Bedrock model '%s'.", settings.bedrock_model)
                return summary, LLMProvider.BEDROCK_QWEN, settings.bedrock_model
            except Exception as e:
                circuit_breaker.record_bedrock_failure(e)
                logger.warning(
                    "Bedrock model '%s' failed, falling back to Groq via circuit breaker "
                    "(state=%s).", settings.bedrock_model, circuit_breaker.state.value)
                summary, model_used = self._call_groq_langchain(prompt, system_prompt)
                return summary, LLMProvider.GROQ_FALLBACK, model_used
        else:
            logger.info(
                "Circuit breaker active (state=%s). Summary via Groq fallback.",
                circuit_breaker.state.value)
            summary, model_used = self._call_groq_langchain(prompt, system_prompt)
            return summary, LLMProvider.GROQ_FALLBACK, model_used

llm_service = LLMService()
