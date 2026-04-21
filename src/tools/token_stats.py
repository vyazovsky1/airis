"""
token_stats.py — Global token usage counters for the current process.

Usage (anywhere in the codebase):
    import tools.token_stats as token_stats
    token_stats.record("thinking", in_tokens, out_tokens)
    token_stats.record("fast", in_tokens, out_tokens)
    token_stats.log_summary()
"""
import logging

logger = logging.getLogger(__name__)

# ── Global counters ────────────────────────────────────────────────────────────
_stats: dict = {
    "thinking": {"input": 0, "output": 0, "calls": 0},
    "fast":     {"input": 0, "output": 0, "calls": 0},
}


def reset() -> None:
    """Reset all counters — call at the start of each agent cycle."""
    for tier in _stats:
        _stats[tier] = {"input": 0, "output": 0, "calls": 0}


def record(tier: str, input_tokens: int, output_tokens: int) -> None:
    """Add token counts for a given tier ('thinking' or 'fast')."""
    if tier not in _stats:
        logger.warning(f"Unknown token tier '{tier}' — not recorded.")
        return
    _stats[tier]["input"]  += input_tokens
    _stats[tier]["output"] += output_tokens
    _stats[tier]["calls"]  += 1

def log_summary() -> None:
    """Emit a formatted token-usage table to the logger."""
    table_len = 78
    t = _stats["thinking"]
    f = _stats["fast"]
    total_in  = t["input"]  + f["input"]
    total_out = t["output"] + f["output"]

    logger.info("=" * table_len)
    logger.info("TOKEN USAGE SUMMARY")
    logger.info("=" * table_len)
    logger.info(
        f"  Thinking model  | calls: {t['calls']:>3} | "
        f"in: {t['input']:>7,} | out: {t['output']:>7,} | total: {t['input'] + t['output']:>8,}"
    )
    logger.info(
        f"  Fast model      | calls: {f['calls']:>3} | "
        f"in: {f['input']:>7,} | out: {f['output']:>7,} | total: {f['input'] + f['output']:>8,}"
    )
    logger.info("-" * table_len)
    logger.info(
        f"  TOTAL           |         "
        f"in: {total_in:>7,} | out: {total_out:>7,} | total: {total_in + total_out:>8,}"
    )
    logger.info("=" * table_len)
