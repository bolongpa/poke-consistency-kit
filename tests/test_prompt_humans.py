"""Prompt builder: positive-only invariant. Humans relations resolve."""
import pytest

from poke_kg.graph import PokeGraph
from poke_kg.prompt_builder import build_prompt


@pytest.fixture(scope="module")
def g():
    return PokeGraph.load()


def test_prompt_has_no_negations(g):
    import re
    neg = re.compile(
        r"\b(no|not|without|never|none|neither|nor|cannot|can't|don't|doesn't|"
        r"lack|lacking|devoid|free of|zero)\b", re.IGNORECASE)
    for pid in range(1, 151):
        prompt = build_prompt(g, pid)
        assert not neg.search(prompt), f"negation in prompt for #{pid}: {prompt}"


def test_prompt_content_pikachu(g):
    prompt = build_prompt(g, "pikachu")
    assert "Pikachu" in prompt
    assert "yellow" in prompt
    assert "red circular cheek pouches" in prompt


def test_prompt_with_style(g):
    prompt = build_prompt(g, "charizard", style="cinematic lighting")
    assert prompt.endswith("cinematic lighting")


def test_ash_owns_pikachu(g):
    team = g.pokemon_of_human("Ash Ketchum")
    assert 25 in [p.id for p in team]


def test_pikachu_owned_by_ash(g):
    humans = g.humans_for_pokemon(25)
    names = [h.name for h in humans]
    assert "Ash Ketchum" in names


def test_twenty_humans(g):
    assert len(g.humans) == 20


def test_human_roles_valid(g):
    from poke_kg.ontology import HUMAN_ROLES
    for h in g.humans.values():
        assert h.role in HUMAN_ROLES


def test_eight_gym_leaders(g):
    leaders = [h for h in g.humans.values() if h.role == "GymLeader"]
    assert len(leaders) == 8


def test_elite_four(g):
    elite = {h.name for h in g.humans.values() if h.role == "EliteFour"}
    assert elite == {"Lorelei", "Bruno", "Agatha", "Lance"}


def test_all_owned_ids_in_range(g):
    for h in g.humans.values():
        for pid in h.owned_pokemon_ids:
            assert 1 <= pid <= 150, f"{h.name} owns #{pid}"


def test_graph_stats(g):
    stats = g.stats()
    assert stats["nodes"]["pokemon"] == 150
    assert stats["nodes"]["human"] == 20
    assert stats["edges"]["EVOLVES_TO"] > 50
