from __future__ import annotations

import re
from typing import Mapping

from interopera.canonical import canonical_sha256, sha256_bytes
from interopera.errors import NarrativeFirewallFailed

PLACEHOLDER = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
DIGIT = re.compile(r"\d|[%$€£¥]|\b(?:SGD|USD|bp|bps)\b", re.IGNORECASE)
NUMBER_WORD = re.compile(
    r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    r"fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|"
    r"sixty|seventy|eighty|ninety|hundred|thousand|million|billion|trillion)(?:-[a-z]+)?\b",
    re.IGNORECASE,
)


def apply_firewall(raw: str, insertions: Mapping[str, str]) -> tuple[str, dict[str, object]]:
    if DIGIT.search(raw) or NUMBER_WORD.search(raw):
        raise NarrativeFirewallFailed("Raw narrative contains a forbidden numeric token")
    if re.search(r"<[^>]+>|\[[^]]+\]\([^)]+\)|\{%|%\}", raw):
        raise NarrativeFirewallFailed("Raw narrative contains unsafe markup")
    used = PLACEHOLDER.findall(raw)
    unknown = sorted(set(used) - set(insertions))
    if unknown:
        raise NarrativeFirewallFailed(f"Unknown narrative placeholders: {unknown}")
    final = PLACEHOLDER.sub(lambda match: insertions[match.group(1)], raw)
    numeric_tokens = re.findall(r"(?:SGD\s*)?[0-9][0-9,]*(?:\.[0-9]+)?(?:%|\s*(?:bps?|yrs?))?", final)
    ledger_tokens = []
    for value in insertions.values():
        ledger_tokens.extend(re.findall(r"(?:SGD\s*)?[0-9][0-9,]*(?:\.[0-9]+)?(?:%|\s*(?:bps?|yrs?))?", value))
    if sorted(numeric_tokens) != sorted(ledger_tokens):
        raise NarrativeFirewallFailed("Final narrative numeric tokens do not match insertion ledger")
    evidence: dict[str, object] = {
        "raw_response_sha256": sha256_bytes(raw.encode()), "raw_numeric_scan": "PASS",
        "allowed_placeholders": sorted(insertions), "used_placeholders": used,
        "insertion_ledger": dict(sorted(insertions.items())), "attribution": "PASS", "result": "PASS",
        "evidence_sha256": canonical_sha256({"raw": raw, "insertions": dict(insertions)}),
    }
    return final, evidence
