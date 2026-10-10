from enum import Enum

class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"

class LLMProvider(str, Enum):
    BEDROCK_QWEN = "bedrock_qwen"
    GROQ_FALLBACK = "groq_fallback"

class CircuitBreakerState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation: Bedrock primary is active
    OPEN = "OPEN"          # Bedrock failure: Fallback to Groq active
    HALF_OPEN = "HALF_OPEN"# 30-min cooldown elapsed: probing Bedrock

class PRStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    MERGED = "merged"

class SystemPrompt(str, Enum):
    PR_SUMMARIZER = (
        "You are an expert AI engineering assistant serving a Chief Technology Officer (CTO). "
        "Your task is to analyze GitHub Pull Request details (title, description, author, branch, and diff) "
        "and produce a concise, high-impact executive summary in English.\n"
        "Guidelines:\n"
        "- State what changed and why in 2 to 4 bullet points.\n"
        "- Highlight any notable architectural changes, optimizations, or potential risks.\n"
        "- Keep the tone professional, technical, and objective."
    )

class UserPromptTemplate(str, Enum):
    PR_DIFF_TEMPLATE = (
        "Analyze the following Pull Request and summarize it for the CTO:\n\n"
        "Title: {title}\n"
        "Author: {author}\n"
        "Base Branch: {base_branch} <- Head Branch: {head_branch}\n"
        "Description:\n{description}\n\n"
        "Code Changes (Diff excerpt):\n{diff_excerpt}\n\n"
        "Please provide the executive summary:"
    )

class AppMessage(str, Enum):
    STARTUP = "CTO Copilot application initialized successfully."
    BEDROCK_HEALTHY = "Bedrock primary provider is active and healthy."
    BEDROCK_FAILED = "Bedrock call failed. Tripping circuit breaker and routing to Groq."
    CIRCUIT_BREAKER_TRIPPED = "Circuit breaker opened. Bedrock in 30-minute cooldown."
    CIRCUIT_BREAKER_PROBING = "30-minute cooldown elapsed. Testing Bedrock availability with probe request."
    CIRCUIT_BREAKER_RECOVERED = "Bedrock probe succeeded. Restored Bedrock as primary provider."
    CIRCUIT_BREAKER_PROBE_FAILED = "Bedrock probe failed. Extending Groq fallback."
    GROQ_SUCCESS = "Summary generated successfully via Groq fallback."
    BEDROCK_SUCCESS = "Summary generated successfully via Bedrock Qwen."
    NO_PRS_FOUND = "No pull requests found in the target repository."
    PR_FETCH_SUCCESS = "Pull requests retrieved successfully."
    PR_SUMMARIZED = "Pull request analyzed and summarized."
