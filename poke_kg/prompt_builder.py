"""Prompt builder: positive-only visual descriptions for image/video models.

Diffusion text encoders handle negation badly ("no wings" can *increase* the
chance of wings), so prompts enumerate what IS there and never what isn't.
"""
from __future__ import annotations

import re

from .graph import PokeGraph

# Whole-word negation markers that must never appear in a built prompt.
_NEGATION_RE = re.compile(
    r"\b(no|not|without|never|none|neither|nor|cannot|can't|don't|doesn't|"
    r"lack|lacking|devoid|free of|zero)\b", re.IGNORECASE)


def assert_no_negations(text: str) -> None:
    m = _NEGATION_RE.search(text)
    if m:
        raise ValueError(f"prompt contains negation: {m.group(0)!r} in {text!r}")


def _clean(attrs: list[str]) -> list[str]:
    """Drop any attribute that slips a negation through (defense in depth)."""
    return [a for a in attrs if not _NEGATION_RE.search(a)]


def build_prompt(graph: PokeGraph, ref: int | str, style: str = "") -> str:
    """Build a positive-only visual prompt for a Pokemon.

    Example: "Pikachu, Mouse Pokemon, yellow body, two legs, small arms,
    long ears with black tips, red circular cheek pouches, ..."
    """
    poke = graph.get_pokemon(ref)
    parts = [poke.name.capitalize()]
    if poke.genera:
        parts.append(poke.genera)
    parts.extend(_clean(poke.visual.positive_attributes()))
    if style:
        parts.append(style)
    prompt = ", ".join(p for p in parts if p)
    assert_no_negations(prompt)
    return prompt
