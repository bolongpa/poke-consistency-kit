"""VLM-based verification loop: check a generated image against a Pokemon's
visual profile.

The knowledge graph can't steer pixels directly, but it makes an excellent
*spec sheet* for an automated critic: generate -> VLM checks each visual
attribute -> report failures -> regenerate or fix.
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass, field
from typing import Protocol

import requests

from .graph import PokeGraph


@dataclass
class Check:
    attribute: str
    expected: str
    observed: str
    passed: bool


@dataclass
class VerificationReport:
    pokemon_id: int
    pokemon_name: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def to_markdown(self) -> str:
        lines = [f"# Verification: {self.pokemon_name} (#{self.pokemon_id})", "",
                 f"**Result: {'PASS' if self.passed else 'FAIL'}** "
                 f"({len(self.checks) - len(self.failures())}/{len(self.checks)} checks passed)", "",
                 "| Attribute | Expected | Observed | Pass |",
                 "|---|---|---|---|"]
        for c in self.checks:
            mark = "✅" if c.passed else "❌"
            lines.append(f"| {c.attribute} | {c.expected} | {c.observed} | {mark} |")
        return "\n".join(lines)


def _profile_checks(poke) -> list[tuple[str, str]]:
    """Derive (attribute, expected description) checks from a visual profile."""
    v = poke.visual
    checks = [("body color", ", ".join(v.body_colors) + " body" if v.body_colors else "body color")]
    checks.append(("wings", "has wings" if v.has_wings else "wingless"))
    if v.limb_description:
        checks.append(("limbs", v.limb_description))
    for feat in v.distinctive_features:
        # wings are already covered by the dedicated wings check above
        if "wing" in feat.lower():
            continue
        checks.append((f"feature: {feat}", f"has {feat}"))
    return checks


class Verifier(Protocol):
    def check(self, image_path: str, ref: int | str) -> VerificationReport: ...


class FakeVLM:
    """Scripted VLM for tests and offline demos.

    `observations` maps attribute -> observed description. Any attribute not
    listed is observed as expected (passes).
    """

    def __init__(self, graph: PokeGraph, observations: dict[str, str] | None = None):
        self.graph = graph
        self.observations = observations or {}

    def check(self, image_path: str, ref: int | str) -> VerificationReport:
        poke = self.graph.get_pokemon(ref)
        report = VerificationReport(pokemon_id=poke.id, pokemon_name=poke.name)
        for attr, expected in _profile_checks(poke):
            observed = self.observations.get(attr, expected)
            report.checks.append(Check(
                attribute=attr, expected=expected, observed=observed,
                passed=_matches(expected, observed)))
        return report


def _matches(expected: str, observed: str) -> bool:
    return observed.strip().lower() == expected.strip().lower()


class OpenAICompatibleVLM:
    """Ask a vision chat-completions endpoint yes/no questions per attribute.

    Works with any OpenAI-compatible vision endpoint via env:
    LLM_BASE_URL, LLM_API_KEY, LLM_MODEL.
    No accuracy claims are made -- the report just records what the VLM said.
    """

    def __init__(self, graph: PokeGraph, base_url: str | None = None,
                 api_key: str | None = None, model: str | None = None):
        self.graph = graph
        self.base_url = (base_url or os.environ.get("LLM_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or os.environ.get("LLM_MODEL", "")
        if not (self.base_url and self.api_key and self.model):
            raise ValueError("LLM_BASE_URL, LLM_API_KEY and LLM_MODEL must all be set")

    def _ask(self, image_b64: str, question: str) -> str:
        body = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text":
                     question + " Reply with exactly one word: YES or NO."},
                    {"type": "image_url", "image_url":
                     {"url": f"data:image/png;base64,{image_b64}"}},
                ],
            }],
            "max_tokens": 5,
        }
        r = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=body, timeout=120)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip().upper()

    def check(self, image_path: str, ref: int | str) -> VerificationReport:
        poke = self.graph.get_pokemon(ref)
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode()
        report = VerificationReport(pokemon_id=poke.id, pokemon_name=poke.name)
        v = poke.visual
        questions = [("wings",
                      f"Does this Pokemon have wings? (Expected: "
                      f"{'it should have wings' if v.has_wings else 'it should be wingless'})",
                      "has wings" if v.has_wings else "wingless")]
        questions.append(("body color",
                          f"Is this Pokemon's body mainly "
                          f"{', '.join(v.body_colors)}? (Expected colors: "
                          f"{', '.join(v.body_colors)})",
                          ", ".join(v.body_colors) + " body"))
        for feat in v.distinctive_features:
            questions.append((f"feature: {feat}",
                              f"Does this Pokemon have: {feat}?",
                              f"has {feat}"))
        for attr, question, expected in questions:
            try:
                answer = self._ask(image_b64, question)
            except Exception as e:  # never crash the loop on one bad call
                answer = f"ERROR: {e}"
            passed = answer == "YES"
            observed = ("matches expected" if passed
                        else f"VLM answered {answer}")
            report.checks.append(Check(attribute=attr, expected=expected,
                                       observed=observed, passed=passed))
        return report
