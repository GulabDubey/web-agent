from langchain_anthropic import ChatAnthropic
from functools import lru_cache
from app.config.settings import settings


@lru_cache(maxsize=1)
def get_llm(
    model: str | None = None,
    temperature: float = 0,
) -> ChatAnthropic:
    """
    Returns a singleton ChatAnthropic instance.
    """
    return ChatAnthropic(
        model=model or settings.ANTHROPIC_MODEL,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
        # Current models think before answering and that thinking counts
        # toward max_tokens, so leave headroom or replies get cut off.
        max_tokens=2048,
        # Short support answers don't need deep reasoning; low effort keeps
        # thinking (and latency/cost) minimal on every current model.
        output_config={"effort": "low"},
    )