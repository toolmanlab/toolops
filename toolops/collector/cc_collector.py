"""Claude Code session collector — scans ~/.claude/projects/ JSONL files and ingests LLM usage."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from toolops.pricing.models import calculate_cost

logger = logging.getLogger(__name__)

_STATE_FILE = Path.home() / ".toolops" / "cc_collector_state.json"
_CC_PROJECTS_DIR = Path.home() / ".claude" / "projects"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass
class StandardUsage:
    """Normalised LLM usage record ready for ClickHouse insertion."""

    timestamp: datetime
    session_id: str
    project: str
    git_branch: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    total_tokens: int
    service_tier: str
    source: str = "claude_code"
    cc_version: str = ""
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a flat dict suitable for ClickHouse insertion."""
        return {
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "project": self.project,
            "git_branch": self.git_branch,
            "model": self.model,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "total_tokens": self.total_tokens,
            "service_tier": self.service_tier,
            "source": self.source,
            "cc_version": self.cc_version,
            "cost_usd": self.cost_usd,
        }


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class BaseCollector(ABC):
    """Abstract collector that discovers session files and parses usage data."""

    @abstractmethod
    def discover_sessions(self) -> list[Path]:
        """Return a list of session file paths to process."""

    @abstractmethod
    def parse_usage(self, path: Path) -> list[StandardUsage]:
        """Parse a single session file and return usage records."""

    def collect(self) -> list[StandardUsage]:
        """Discover sessions and parse all usage records."""
        results: list[StandardUsage] = []
        for path in self.discover_sessions():
            try:
                results.extend(self.parse_usage(path))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to parse %s: %s", path, exc)
        return results

    def ingest_to_clickhouse(self, client: Any, usages: list[StandardUsage]) -> int:
        """Batch-insert usage records into ClickHouse.

        Args:
            client: A :class:`~toolops.storage.clickhouse.ClickHouseClient` instance.
            usages: Records to insert.

        Returns:
            Number of records inserted.
        """
        if not usages:
            return 0
        records = [u.to_dict() for u in usages]
        client.insert_llm_usage(records)
        return len(records)


# ---------------------------------------------------------------------------
# State management helpers
# ---------------------------------------------------------------------------


def _load_state() -> dict[str, int]:
    """Load per-file byte-offset state from disk."""
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_state(state: dict[str, int]) -> None:
    """Persist per-file byte-offset state to disk."""
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, indent=2))


# ---------------------------------------------------------------------------
# Claude Code collector
# ---------------------------------------------------------------------------


class ClaudeCodeCollector(BaseCollector):
    """Collector that reads Claude Code JSONL session files from ~/.claude/projects/."""

    def __init__(
        self,
        projects_dir: Path | None = None,
        state_file: Path | None = None,
        incremental: bool = True,
    ) -> None:
        self._projects_dir = projects_dir or _CC_PROJECTS_DIR
        self._state_file = state_file or _STATE_FILE
        self._incremental = incremental

    # -- BaseCollector interface ----------------------------------------------

    def discover_sessions(self) -> list[Path]:
        """Enumerate all .jsonl files under the CC projects directory."""
        if not self._projects_dir.exists():
            logger.info("CC projects directory not found: %s", self._projects_dir)
            return []
        return sorted(self._projects_dir.rglob("*.jsonl"))

    def parse_usage(self, path: Path) -> list[StandardUsage]:
        """Parse a single JSONL session file into StandardUsage records.

        Supports incremental mode — only bytes after the last known offset are
        read; the state file is updated on success.
        """
        state = _load_state() if self._incremental else {}
        key = str(path)
        offset = state.get(key, 0)

        usages: list[StandardUsage] = []

        with path.open("rb") as fh:
            fh.seek(offset)
            while True:
                line = fh.readline()
                if not line:
                    new_offset = fh.tell()
                    break
                line_str = line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    obj = json.loads(line_str)
                except json.JSONDecodeError:
                    continue

                usage = self._try_parse_record(obj)
                if usage is not None:
                    usages.append(usage)

            if self._incremental:
                state[key] = new_offset
                _save_state(state)

        return usages

    # -- Internal helpers -----------------------------------------------------

    @staticmethod
    def _try_parse_record(obj: dict[str, Any]) -> StandardUsage | None:
        """Attempt to build a StandardUsage from a raw JSONL record.

        Returns *None* for non-assistant messages or records without usage data.
        """
        # Only process assistant messages
        msg = obj.get("message", {})
        if not isinstance(msg, dict):
            return None
        if msg.get("role") != "assistant":
            return None

        usage = msg.get("usage")
        if not isinstance(usage, dict):
            return None

        input_tokens = int(usage.get("input_tokens", 0))
        output_tokens = int(usage.get("output_tokens", 0))
        cache_creation = int(usage.get("cache_creation_input_tokens", 0))
        cache_read = int(usage.get("cache_read_input_tokens", 0))
        total_tokens = input_tokens + output_tokens + cache_creation + cache_read

        raw_ts = obj.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            ts = ts.astimezone(UTC).replace(tzinfo=None)
        except Exception:  # noqa: BLE001
            ts = datetime.utcnow()

        model = str(msg.get("model", ""))

        # Skip synthetic / zero-usage records (e.g. Desktop Agent Mode placeholders)
        if model == "<synthetic>" or total_tokens == 0:
            return None

        cost_usd = calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
        )

        return StandardUsage(
            timestamp=ts,
            session_id=str(obj.get("sessionId", "")),
            project=str(obj.get("cwd", "")),
            git_branch=str(obj.get("gitBranch", "")),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_tokens=cache_creation,
            cache_read_tokens=cache_read,
            total_tokens=total_tokens,
            service_tier=str(usage.get("service_tier", "")),
            source="claude_code",
            cc_version=str(obj.get("version", "")),
            cost_usd=cost_usd,
        )
