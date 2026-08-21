"""
LLM Usage Log - tracks every Claude API call for cost/usage monitoring.

Unlike receipts.json, this is an append-only log (no update/delete), so it
doesn't implement the Database abstract interface - it's a standalone,
simpler class following the same JSON read-all/write-all style. See SP-020.
"""

import json
import os
from datetime import datetime
from typing import Dict, List

# Anthropic pricing per 1,000,000 tokens, as of 2026-08. Keyed by model ID
# (not hardcoded to whatever LLM_MODEL is currently configured) so that
# historical cost totals stay correct even after a future model change -
# this project has already migrated models once (see CLAUDE.md).
_PRICING_PER_MILLION_TOKENS = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-opus-5": {"input": 5.00, "output": 25.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

# Used only if a record's model isn't in the table above (e.g. an unrecognized
# or future model) - better to show an approximate cost than none at all.
_DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate the USD cost of one API call from its token counts and model."""
    pricing = _PRICING_PER_MILLION_TOKENS.get(model, _DEFAULT_PRICING)
    return (
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"]
    )


class UsageLogDatabase:
    """
    JSON file-based log of every LLM (Claude) API call made by the app.

    Each record captures who triggered the call, what it cost, and whether
    it succeeded - the data behind the admin-only LLM Usage page (SP-020).
    """

    def __init__(self, file_path: str):
        """
        Initialize the usage log.

        Args:
            file_path (str): Path to the JSON file (e.g., './data/llm_usage.json')
        """
        self.file_path = file_path
        self.initialize()

    def initialize(self) -> None:
        """Create the JSON file (and parent directory) with an empty list if missing."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory)

        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([], f)
            print(f"Initialized usage log file: {self.file_path}")

    def log_call(
        self,
        user_email: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        success: bool,
        is_retry: bool,
    ) -> None:
        """
        Record one LLM API call attempt.

        Args:
            user_email (str): Email of the user whose upload triggered this call
            model (str): Claude model ID used for this call
            input_tokens (int): Input tokens consumed (0 if the call never reached the API)
            output_tokens (int): Output tokens generated (0 if the call never reached the API)
            success (bool): Whether the call succeeded (API responded AND parsed cleanly)
            is_retry (bool): Whether this was the SP-018 reconciliation retry, not the first attempt
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "user_email": user_email,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": _estimate_cost_usd(model, input_tokens, output_tokens),
            "success": success,
            "is_retry": is_retry,
        }

        records = self._read_all()
        records.append(record)
        self._write_all(records)

    def get_all_records(self) -> List[Dict]:
        """Return every logged call, oldest first."""
        return self._read_all()

    def _read_all(self) -> List[Dict]:
        """Internal: read all records from the JSON file."""
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            self.initialize()
            return []

    def _write_all(self, records: List[Dict]) -> None:
        """Internal: write all records to the JSON file."""
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
