from tiktoken import get_encoding

_encoder = get_encoding("cl100k_base")

def count_message_tokens(messages):
    """
    Count tokens from LangChain messages list.
    Example:
    [
        HumanMessage(content="Hello"),
        AIMessage(content="Hi")
    ]
    """

    total = 0

    for message in messages:
        total += len(_encoder.encode(message.content))

    return total