"""Verifier: FakeVLM catches the winged-Pikachu failure mode."""
import pytest

from poke_kg.graph import PokeGraph
from poke_kg.verifier import FakeVLM


@pytest.fixture(scope="module")
def g():
    return PokeGraph.load()


def test_clean_image_passes(g):
    v = FakeVLM(g)  # no scripted faults -> everything matches
    report = v.check("fake.png", "pikachu")
    assert report.passed
    assert report.failures() == []


def test_winged_pikachu_fails(g):
    v = FakeVLM(g, observations={"wings": "large feathered wings present"})
    report = v.check("fake.png", "pikachu")
    assert not report.passed
    failures = report.failures()
    assert len(failures) == 1
    assert failures[0].attribute == "wings"
    assert failures[0].expected == "wingless"
    assert "wings present" in failures[0].observed


def test_winged_charizard_passes_wings_check(g):
    # Charizard SHOULD have wings: the same observation passes here.
    v = FakeVLM(g, observations={"wings": "has wings"})
    report = v.check("fake.png", "charizard")
    assert all(c.passed for c in report.checks if c.attribute == "wings")


def test_report_markdown(g):
    v = FakeVLM(g, observations={"wings": "large feathered wings present"})
    md = v.check("fake.png", "pikachu").to_markdown()
    assert "FAIL" in md
    assert "wingless" in md


def test_distinctive_features_become_checks(g):
    v = FakeVLM(g)
    report = v.check("fake.png", "pikachu")
    attrs = [c.attribute for c in report.checks]
    assert any("red circular cheek pouches" in a for a in attrs)
