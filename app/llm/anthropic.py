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
        max_tokens=300
    )