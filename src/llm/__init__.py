__all__ = [
    "process_message",
    "LLMResponse",
]


def __getattr__(name: str) -> object:
    if name in __all__:
        from src.llm.engine import process_message
        from src.llm.response_runtime import LLMResponse

        exports = {
            "LLMResponse": LLMResponse,
            "process_message": process_message,
        }
        return exports[name]
    raise AttributeError(f"module 'src.llm' has no attribute {name!r}")
