"""Ontology integrity: 150 Pokemon, ids 1-150, no Mew, sane evolutions."""
import pytest

from poke_kg.graph import PokeGraph


@pytest.fixture(scope="module")
def g():
    return PokeGraph.load()


def test_exactly_150_pokemon(g):
    assert len(g.pokemon) == 150
    assert set(g.pokemon) == set(range(1, 151))


def test_no_mew(g):
    with pytest.raises(KeyError):
        g.get_pokemon(151)
    names = [p.name for p in g.pokemon.values()]
    assert "mew" not in names


def test_bulbasaur_line(g):
    chain = g.evolution_chain(1)
    assert [p.id for p in chain] == [1, 2, 3]
    assert [p.name for p in chain] == ["bulbasaur", "ivysaur", "venusaur"]


def test_pikachu_line_excludes_pichu(g):
    chain = g.evolution_chain("pikachu")
    assert [p.id for p in chain] == [25, 26]


def test_eevee_gen1_evolutions_only(g):
    eevee = g.get_pokemon(133)
    assert sorted(eevee.evolution_ids) == [134, 135, 136]


def test_all_evolution_ids_in_range(g):
    for p in g.pokemon.values():
        for evo in p.evolution_ids:
            assert 1 <= evo <= 150, f"{p.name} -> {evo}"


def test_pikachu_basics(g):
    pika = g.get_pokemon("pikachu")
    assert pika.id == 25
    assert pika.types == ["electric"]
    assert not pika.visual.has_wings
    assert not pika.visual.can_fly
    assert "yellow" in pika.visual.body_colors


def test_charizard_flies(g):
    char = g.get_pokemon("charizard")
    assert char.visual.has_wings and char.visual.can_fly


def test_doduo_flightless_despite_flying_type(g):
    doduo = g.get_pokemon("doduo")
    assert "flying" in doduo.types
    assert not doduo.visual.has_wings
    assert not doduo.visual.can_fly


def test_gyarados_flightless_despite_flying_type(g):
    gyara = g.get_pokemon("gyarados")
    assert "flying" in gyara.types
    assert not gyara.visual.can_fly


def test_name_normalisation(g):
    assert g.get_pokemon("Mr Mime").id == 122
    assert g.get_pokemon("farfetch'd").id == 83
    assert g.get_pokemon("25").id == 25
