"""CLI: poke-kg build|ask|profile|prompt|verify"""
from __future__ import annotations

import argparse
import re

from .graph import PokeGraph
from . import ingest
from .prompt_builder import build_prompt
from .verifier import FakeVLM, OpenAICompatibleVLM


def cmd_build(_):
    ingest.main()


def _graph():
    print("Loading knowledge graph...")
    return PokeGraph.load()


def cmd_ask(args):
    g = _graph()
    q = args.question.strip().lower()

    m = re.search(r"who owns (\w[\w '\-.]*)", q)
    if m:
        try:
            poke = g.get_pokemon(m.group(1))
        except KeyError:
            print(f"Unknown Pokemon: {m.group(1)}"); return
        humans = g.humans_for_pokemon(poke.id)
        if humans:
            for h in humans:
                print(f"{h.name} ({h.role}, canon: {h.canon})")
        else:
            print(f"No curated human owns {poke.name}.")
        return

    m = re.search(r"(?:evolution|evolve).*?(\w[\w'\-.]*)\s*$", q)
    if m:
        try:
            chain = g.evolution_chain(m.group(1))
        except KeyError:
            print(f"Unknown Pokemon: {m.group(1)}"); return
        print(" -> ".join(f"{p.name} (#{p.id})" for p in chain))
        return

    m = re.search(r"weakness(?:es)? of (\w[\w'\-.]*)", q)
    if m:
        try:
            w = g.pokemon_weaknesses(m.group(1))
        except KeyError:
            print(f"Unknown Pokemon: {m.group(1)}"); return
        print("weak to:", ", ".join(sorted(w["weak_to"])) or "none")
        print("resistant to:", ", ".join(sorted(w["resistant_to"])) or "none")
        print("immune to:", ", ".join(sorted(w["immune_to"])) or "none")
        return

    m = re.search(r"(?:pokemon|team) of (\w[\w '\-.]*)", q)
    if m:
        try:
            team = g.pokemon_of_human(m.group(1))
        except KeyError:
            print(f"Unknown human: {m.group(1)}"); return
        print(", ".join(f"{p.name} (#{p.id})" for p in team) or "none curated")
        return

    print("I understand: 'who owns <pokemon>', 'evolution of <pokemon>', "
          "'weaknesses of <pokemon>', 'pokemon of <human>'")


def cmd_profile(args):
    g = _graph()
    poke = g.get_pokemon(args.pokemon)
    v = poke.visual
    print(f"{poke.name.capitalize()} (#{poke.id}) -- {poke.genera}")
    print(f"Types: {', '.join(poke.types)}")
    print(f"Abilities: {', '.join(poke.abilities)}")
    print(f"Visual profile:")
    print(f"  body colors: {', '.join(v.body_colors)}")
    print(f"  has wings: {v.has_wings}")
    print(f"  can fly: {v.can_fly}")
    print(f"  limbs: {v.limb_description}")
    print(f"  distinctive features:")
    for f in v.distinctive_features:
        print(f"    - {f}")
    print(f"  sprite: {v.sprite_urls.get('official_artwork')}")


def cmd_prompt(args):
    g = _graph()
    print(build_prompt(g, args.pokemon, style=args.style or ""))


def cmd_verify(args):
    g = _graph()
    if args.vlm == "fake":
        # Demo scenario: pretend the generated image gave Pikachu wings.
        observations = {}
        if normalize(args.pokemon) == "pikachu":
            observations = {"wings": "large feathered wings present"}
        verifier = FakeVLM(g, observations=observations)
    else:
        verifier = OpenAICompatibleVLM(g)
    report = verifier.check(args.image, args.pokemon)
    print(report.to_markdown())


def normalize(name: str) -> str:
    return name.strip().lower()


def main():
    p = argparse.ArgumentParser(prog="poke-kg",
                                description="Gen-1 Pokemon consistency toolkit")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("build", help="fetch PokeAPI data and build data/pokemon_gen1.json")
    s.set_defaults(fn=cmd_build)

    s = sub.add_parser("ask", help="query the knowledge graph")
    s.add_argument("question")
    s.set_defaults(fn=cmd_ask)

    s = sub.add_parser("profile", help="print a Pokemon's visual profile")
    s.add_argument("pokemon")
    s.set_defaults(fn=cmd_profile)

    s = sub.add_parser("prompt", help="build a positive-only visual prompt")
    s.add_argument("pokemon")
    s.add_argument("--style", default="")
    s.set_defaults(fn=cmd_prompt)

    s = sub.add_parser("verify", help="verify a generated image against the visual profile")
    s.add_argument("image")
    s.add_argument("pokemon")
    s.add_argument("--vlm", choices=["fake", "openai"], default="fake")
    s.set_defaults(fn=cmd_verify)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
