import tiktoken

try:
    _enc = tiktoken.get_encoding("cl100k_base")
except Exception:
    _enc = None


def count_tokens(text: str) -> int:
    """Return accurate BPE token count for text using cl100k_base or fallback."""
    if not text:
        return 0
    if _enc:
        try:
            return len(_enc.encode(text, disallowed_special=()))
        except Exception:
            pass
    # Approximate: ~4 chars per token for code/english
    return max(1, len(text) // 4)
