"""Gen-1 type chart spot checks (15 types, no Dark/Steel/Fairy)."""
import pytest

from poke_kg.graph import PokeGraph
from poke_kg.ontology import GEN1_TYPES


@pytest.fixture(scope="module")
def g():
    return PokeGraph.load()


def test_fifteen_types_only(g):
    assert set(g.types) == set(GEN1_TYPES)
    for missing in ("dark", "steel", "fairy"):
        assert missing not in g.types


def test_electric_weak_to_ground(g):
    assert "ground" in g.type_matchups("electric")["weak_to"]


def test_ground_immune_to_electric(g):
    assert "electric" in g.type_matchups("ground")["immune_to"]


def test_psychic_immune_to_nothing(g):
    assert g.type_matchups("psychic")["immune_to"] == set()


def test_ghost_super_effective_vs_psychic(g):
    # intended Gen-1 chart (the games shipped a bug making Psychic immune)
    assert "ghost" in g.type_matchups("psychic")["weak_to"]


def test_normal_immune_to_ghost(g):
    assert "ghost" in g.type_matchups("normal")["immune_to"]
    assert "normal" in g.type_matchups("ghost")["immune_to"]


def test_fighting_immune_to_ghost(g):
    assert "ghost" in g.type_matchups("fighting")["immune_to"]


def test_gen1_quirks(g):
    # Poison was super-effective vs Bug in Gen 1 only
    assert "poison" in g.type_matchups("bug")["weak_to"]
    # Bug was super-effective vs Poison in Gen 1 only
    assert "bug" in g.type_matchups("poison")["weak_to"]


def test_charizard_weaknesses(g):
    w = g.pokemon_weaknesses("charizard")  # fire/flying
    assert {"rock", "electric", "water"} <= w["weak_to"]
    assert "ground" in w["immune_to"]


def test_magnemite_weaknesses(g):
    w = g.pokemon_weaknesses("magnemite")  # electric (gen-1: pure electric)
    assert w["weak_to"] == {"ground"}
