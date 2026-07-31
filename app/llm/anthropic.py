from langchain_anthropic import ChatAnthropic
from functools import lru_cache
import os


@lru_cache(maxsize=1)
def get_llm(
    model: str | None = None,
    temperature: float = 0,
) -> ChatAnthropic:
    """
    Returns a singleton ChatAnthropic instance.
    """
    return ChatAnthropic(
        model=model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        max_tokens=300
    )