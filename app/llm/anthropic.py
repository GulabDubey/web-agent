from app.llm.factory import env_llm_config, get_chat_model


def get_llm():
    """
    Chat model from this service's .env Anthropic settings.

    Chatbot replies use the website's provider/model configured in Django
    (see app/services/llm_config_service.py); this remains the fallback and
    is used by internal tools that aren't tied to a website.
    """
    return get_chat_model(env_llm_config())
