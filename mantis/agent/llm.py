"""LLM factory: build chat models from MantisConfig, supporting multiple providers."""

from __future__ import annotations

from langchain_core.language_models import BaseChatModel

from mantis.config import LLMConfig, MantisConfig


def build_chat_model(llm_cfg: LLMConfig, **kwargs) -> BaseChatModel:
    """Build a LangChain BaseChatModel from LLMConfig.

    Routes to the right LangChain integration based on provider.
    DeepSeek/Zhipu/OpenRouter use OpenAI-compatible APIs through `langchain_openai`.
    """
    provider = llm_cfg.provider
    api_key = llm_cfg.api_key
    if not api_key:
        raise ValueError(f"No API key set for provider '{provider}' (env: {llm_cfg.api_key_env_var})")

    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=llm_cfg.model,
            api_key=api_key,
            **kwargs,
        )

    # OpenAI-compatible providers (deepseek, zhipu, openai, openrouter)
    from langchain_openai import ChatOpenAI

    init_kwargs = dict(
        model=llm_cfg.model,
        api_key=api_key,
        temperature=kwargs.pop("temperature", 0.3),
    )
    if llm_cfg.base_url:
        init_kwargs["base_url"] = llm_cfg.base_url

    # DeepSeek v4 enables thinking mode by default, which is incompatible with
    # langchain_openai's tool-calling loop (requires reasoning_content round-trip).
    # Disable thinking explicitly for DeepSeek so tool calls work cleanly.
    if provider == "deepseek":
        extra_body = kwargs.pop("extra_body", {})
        extra_body.setdefault("thinking", {"type": "disabled"})
        init_kwargs["extra_body"] = extra_body

    init_kwargs.update(kwargs)
    return ChatOpenAI(**init_kwargs)


def build_main_llm(config: MantisConfig, **kwargs) -> BaseChatModel:
    return build_chat_model(config.main_llm, **kwargs)


def build_critic_llm(config: MantisConfig, **kwargs) -> BaseChatModel:
    return build_chat_model(config.critic_llm, **kwargs)


def build_reviewer_llm(config: MantisConfig, **kwargs) -> BaseChatModel:
    return build_chat_model(config.reviewer_llm, **kwargs)
