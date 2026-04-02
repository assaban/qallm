from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha1
from typing import Any, Literal

Severity = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
FindingType = Literal["SECURITY", "SMELL", "COMPLEXITY", "SECRET", "OTHER"]


@dataclass
class Finding:
    tool: str
    type: FindingType
    severity: Severity
    file: str
    line: int | None
    message: str
    rule_id: str | None = None
    code_snippet: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        base = f"{self.tool}|{self.type}|{self.severity}|{self.file}|{self.line}|{self.rule_id}|{self.message}"
        return sha1(base.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["id"] = self.id
        return d


@dataclass
class Patch:
    finding_id: str
    description: str
    unified_diff: str
    applied: bool = False
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Summary:
    total: int
    by_severity: dict[str, int]
    by_type: dict[str, int]


@dataclass
class AnalysisReport:
    session_id: str
    findings: list[Finding]
    summary: Summary


@dataclass
class RepairReport:
    session_id: str
    patches: list[Patch]
    token_usage: dict[str, Any]


@dataclass
class VerificationReport:
    session_id: str
    before: Summary
    after: Summary
    resolved: int
    remaining: int
    new: int
    resolved_ids: list[str]
    new_ids: list[str]
