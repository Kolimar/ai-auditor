"""Semantic registry of LLM SDK signatures, as data.

Sources: official SDK and framework docs. Entries marked
``verified=False`` were not confirmed in official docs during research; they are
kept because they are widely used, and contract tests pin their behaviour.
Changing an SDK's API means editing this table, not the extractor.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CallSig:
    """A method-chain call such as ``client.chat.completions.create(...)``."""

    framework: str
    provider: str | None
    chain: tuple[str, ...]  # suffix of the attribute chain
    client_modules: tuple[str, ...]  # modules whose constructors produce a matching receiver
    prompt_args: tuple[str, ...]  # kwargs carrying prompt content
    structured_args: tuple[str, ...] = ()  # kwargs that enforce an output schema
    structured_by_default: bool = False  # e.g. *.parse helpers
    verified: bool = True


# Keyword arguments that, together with ``model``, identify an LLM call even when
# the receiver could not be resolved (avoids matching Twilio's ``messages.create``).
LLM_KWARG_EVIDENCE = frozenset({"messages", "max_tokens", "system", "input", "instructions", "contents", "max_output_tokens"})

CALL_SIGS: tuple[CallSig, ...] = (
    CallSig("anthropic", "anthropic", ("messages", "create"), ("anthropic",), ("system", "messages"), ("output_config", "output_format")),
    CallSig("anthropic", "anthropic", ("messages", "parse"), ("anthropic",), ("system", "messages"), ("output_format", "output_config"), structured_by_default=True),
    CallSig("anthropic", "anthropic", ("messages", "stream"), ("anthropic",), ("system", "messages"), ("output_config",), verified=False),
    CallSig("openai", "openai", ("chat", "completions", "create"), ("openai",), ("messages",), ("response_format",)),
    CallSig("openai", "openai", ("chat", "completions", "parse"), ("openai",), ("messages",), ("response_format",), structured_by_default=True, verified=False),
    CallSig("openai", "openai", ("responses", "create"), ("openai",), ("instructions", "input"), ("text",)),
    CallSig("openai", "openai", ("responses", "parse"), ("openai",), ("instructions", "input"), ("text_format", "text"), structured_by_default=True, verified=False),
    CallSig("google", "google", ("models", "generate_content"), ("google.genai", "google"), ("contents", "config"), ()),
    CallSig("google", "google", ("generate_content",), ("google.generativeai",), ("contents",), (), verified=False),
)

# Plain function calls: fully-qualified name -> (framework, provider-from-model-prefix)
FUNC_SIGS: dict[str, str] = {
    "litellm.completion": "litellm",
    "litellm.acompletion": "litellm",
    "ollama.chat": "ollama",
    "ollama.generate": "ollama",
}

# Chat model constructors whose instances are invoked with .invoke/.ainvoke/.batch/.stream
CHAT_MODEL_CTORS: dict[str, str] = {
    "langchain_openai.ChatOpenAI": "openai",
    "langchain_openai.AzureChatOpenAI": "openai",
    "langchain_anthropic.ChatAnthropic": "anthropic",
    "langchain_google_genai.ChatGoogleGenerativeAI": "google",
    "langchain_community.chat_models.ChatOllama": "ollama",
    "langchain_ollama.ChatOllama": "ollama",
    "langchain.chat_models.init_chat_model": "",
}
INVOKE_METHODS = frozenset({"invoke", "ainvoke", "batch", "abatch", "stream", "astream"})

# Agent constructors -> (framework, kwarg names)
@dataclass(frozen=True)
class AgentSig:
    framework: str
    name_args: tuple[str, ...]
    prompt_args: tuple[str, ...]
    model_args: tuple[str, ...]
    model_positional: bool = False
    output_args: tuple[str, ...] = ()
    tools_args: tuple[str, ...] = ("tools",)
    delegate_args: tuple[str, ...] = ()
    max_iter_args: tuple[str, ...] = ()
    default_bounded: bool = True  # SDK enforces a default turn/request limit
    verified: bool = True


AGENT_CTORS: dict[str, AgentSig] = {
    "agents.Agent": AgentSig("openai_agents", ("name",), ("instructions",), ("model",), output_args=("output_type",),
                             delegate_args=("handoffs",)),
    "pydantic_ai.Agent": AgentSig("pydantic_ai", ("name",), ("system_prompt", "instructions"), ("model",), model_positional=True,
                                  output_args=("output_type", "result_type")),
    "crewai.Agent": AgentSig("crewai", ("role",), ("role", "goal", "backstory"), ("llm",), max_iter_args=("max_iter",)),
    "google.adk.agents.LlmAgent": AgentSig("google_adk", ("name",), ("instruction",), ("model",), output_args=("output_schema",),
                                           delegate_args=("sub_agents",), verified=False),
    "google.adk.agents.Agent": AgentSig("google_adk", ("name",), ("instruction",), ("model",), output_args=("output_schema",),
                                        delegate_args=("sub_agents",), verified=False),
    "claude_agent_sdk.AgentDefinition": AgentSig("claude_agent_sdk", (), ("prompt", "description"), ("model",),
                                                 max_iter_args=("maxTurns",)),
    "autogen_agentchat.agents.AssistantAgent": AgentSig("autogen", ("name",), ("system_message",), ("model_client",), verified=False),
    "langgraph.prebuilt.create_react_agent": AgentSig("langgraph", ("name",), ("prompt",), ("model",), model_positional=True,
                                                     output_args=("response_format",), verified=False),
    "langchain.agents.create_agent": AgentSig("langchain", ("name",), ("system_prompt",), ("model",), model_positional=True,
                                              output_args=("response_format",), verified=False),
}
AGENT_RUN_METHODS = frozenset({"run", "run_sync", "run_streamed", "kickoff"})  # Runner.run(agent, input) / agent.run_sync(input)

RETRIEVAL_METHODS: dict[str, tuple[str, ...]] = {
    # method -> kwargs that carry top-k
    "similarity_search": ("k",),
    "similarity_search_with_score": ("k",),
    "similarity_search_with_relevance_scores": ("k",),
    "max_marginal_relevance_search": ("k",),
    "get_relevant_documents": (),
    "query": ("n_results", "top_k", "similarity_top_k"),
    "search": ("limit", "top_k", "k"),
    "retrieve": ("top_k", "k"),
}
RETRIEVER_CTOR_METHODS = frozenset({"as_retriever"})
RERANK_HINTS = ("rerank", "crossencoder", "cross_encoder", "contextualcompression", "flashrank", "colbert")

TENACITY_RETRY = frozenset({"tenacity.retry", "backoff.on_exception", "backoff.on_predicate"})
FORMAT_EXCEPTIONS = frozenset({"JSONDecodeError", "ValidationError", "ValueError", "KeyError", "TypeError",
                               "OutputParserException", "UnexpectedModelBehavior"})
NETWORK_EXCEPTIONS = frozenset({"APIError", "APIConnectionError", "RateLimitError", "APITimeoutError", "Timeout",
                                "TimeoutError", "ConnectionError", "InternalServerError", "ServiceUnavailableError",
                                "OverloadedError", "APIStatusError"})
VALIDATION_CALLS = frozenset({"model_validate", "model_validate_json", "parse_obj", "parse_raw", "validate_python",
                              "validate_json"})
WEB_DECORATORS = frozenset({"get", "post", "put", "patch", "delete", "route", "websocket", "api_route"})
