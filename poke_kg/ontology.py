"""Core ontology dataclasses for the Gen-1 Pokemon knowledge graph.

Scope: Pokemon #1-150 only (Bulbasaur..Mewtwo). Mew (#151) is excluded.
Types are the 15 Gen-1 types (no Dark/Steel/Fairy).
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Relation name constants (edge labels in the knowledge graph)
# ---------------------------------------------------------------------------
HAS_TYPE = "HAS_TYPE"
EVOLVES_TO = "EVOLVES_TO"
HAS_ABILITY = "HAS_ABILITY"
LEARNS_MOVE = "LEARNS_MOVE"
WEAK_TO = "WEAK_TO"
RESISTANT_TO = "RESISTANT_TO"
IMMUNE_TO = "IMMUNE_TO"
OWNED_BY = "OWNED_BY"          # human -> pokemon
SPECIALIZES_IN = "SPECIALIZES_IN"  # human -> type (gym leaders, elite four)

GEN1_TYPES = [
    "normal", "fire", "water", "electric", "grass", "ice",
    "fighting", "poison", "ground", "flying", "psychic",
    "bug", "rock", "ghost", "dragon",
]

HUMAN_ROLES = {"Trainer", "GymLeader", "EliteFour", "Professor", "TeamRocket"}


# ---------------------------------------------------------------------------
# Visual profile: the part of the ontology that matters for AI image/video
# generation. Every field is phrased positively -- the prompt builder never
# emits negations ("no wings"), because diffusion text encoders handle
# negation badly.
# ---------------------------------------------------------------------------
@dataclass
class VisualProfile:
    body_colors: list[str] = field(default_factory=list)
    has_wings: bool = False
    can_fly: bool = False
    limb_description: str = ""
    distinctive_features: list[str] = field(default_factory=list)
    sprite_urls: dict[str, str] = field(default_factory=dict)  # default, official_artwork

    def positive_attributes(self) -> list[str]:
        """Positive-only visual descriptors, safe for diffusion prompts."""
        attrs = [f"{c} body" for c in self.body_colors]
        if self.limb_description:
            attrs.append(self.limb_description)
        attrs.extend(self.distinctive_features)
        if self.has_wings:
            attrs.append("wings")
        if self.can_fly and not self.has_wings:
            attrs.append("capable of flight")
        return attrs


@dataclass
class Pokemon:
    id: int
    name: str
    types: list[str] = field(default_factory=list)
    abilities: list[str] = field(default_factory=list)
    base_stats: dict[str, int] = field(default_factory=dict)
    height_dm: int = 0   # decimetres, as the API reports
    weight_hg: int = 0   # hectograms, as the API reports
    color: str = ""
    shape: str = ""
    genera: str = ""
    evolution_ids: list[int] = field(default_factory=list)  # direct evolutions, gen-1 only
    signature_moves: list[str] = field(default_factory=list)  # move names
    visual: VisualProfile = field(default_factory=VisualProfile)


@dataclass
class Human:
    name: str
    role: str  # one of HUMAN_ROLES
    owned_pokemon_ids: list[int] = field(default_factory=list)
    specializes_in: list[str] = field(default_factory=list)  # type names
    description: str = ""
    canon: str = ""  # where the ownership claim comes from, e.g. "anime", "games"

    def __post_init__(self):
        if self.role not in HUMAN_ROLES:
            raise ValueError(f"unknown human role: {self.role!r}")


@dataclass
class Type:
    name: str
    # attacking multipliers of THIS type against each defending type (only != 1.0 stored)
    attacking: dict[str, float] = field(default_factory=dict)


@dataclass
class Move:
    name: str
    type: str
    power: int | None = None
