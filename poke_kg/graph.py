"""Knowledge graph construction and queries over the Gen-1 Pokemon ontology."""
from __future__ import annotations

import json
import os
import re

import networkx as nx

from .ontology import (
    EVOLVES_TO, HAS_ABILITY, HAS_TYPE, IMMUNE_TO, LEARNS_MOVE, OWNED_BY,
    RESISTANT_TO, SPECIALIZES_IN, WEAK_TO,
    Human, Move, Pokemon, Type, VisualProfile,
)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")

# Friendly-name normalisation for CLI/tests: "mr mime" -> "mr-mime", etc.
_NAME_FIX = {
    "♀": "-f", "♂": "-m", "'": "", ".": "", " ": "-",
}


def normalize_name(name: str) -> str:
    name = name.strip().lower()
    for k, v in _NAME_FIX.items():
        name = name.replace(k, v)
    return re.sub(r"-+", "-", name)


class PokeGraph:
    def __init__(self):
        self.g = nx.MultiDiGraph()
        self.pokemon: dict[int, Pokemon] = {}
        self.pokemon_by_name: dict[str, Pokemon] = {}
        self.humans: dict[str, Human] = {}
        self.moves: dict[str, Move] = {}
        self.types: dict[str, Type] = {}
        self._chart: dict[str, dict[str, float]] = {}

    # -- loading ---------------------------------------------------------
    @classmethod
    def load(cls) -> "PokeGraph":
        self = cls()
        with open(os.path.join(DATA, "pokemon_gen1.json"), encoding="utf-8") as f:
            pdata = json.load(f)
        with open(os.path.join(DATA, "humans.json"), encoding="utf-8") as f:
            hdata = json.load(f)
        with open(os.path.join(DATA, "type_chart_gen1.json"), encoding="utf-8") as f:
            chart = json.load(f)
        chart.pop("_note", None)
        self._chart = chart

        for tname, attacking in chart.items():
            self.types[tname] = Type(name=tname, attacking=attacking)
            self.g.add_node(f"type:{tname}", kind="type", name=tname)

        for mname, m in pdata["moves"].items():
            self.moves[mname] = Move(name=mname, type=m["type"], power=m["power"])
            self.g.add_node(f"move:{mname}", kind="move", name=mname,
                            type=m["type"], power=m["power"])

        for p in pdata["pokemon"]:
            v = p["visual"]
            poke = Pokemon(
                id=p["id"], name=p["name"], types=p["types"],
                abilities=p["abilities"], base_stats=p["base_stats"],
                height_dm=p["height_dm"], weight_hg=p["weight_hg"],
                color=p["color"], shape=p["shape"], genera=p["genera"],
                evolution_ids=p["evolution_ids"],
                signature_moves=p["signature_moves"],
                visual=VisualProfile(
                    body_colors=v["body_colors"], has_wings=v["has_wings"],
                    can_fly=v["can_fly"], limb_description=v["limb_description"],
                    distinctive_features=v["distinctive_features"],
                    sprite_urls=v["sprite_urls"]),
            )
            self.pokemon[poke.id] = poke
            self.pokemon_by_name[normalize_name(poke.name)] = poke
            self.g.add_node(f"pokemon:{poke.id}", kind="pokemon", id=poke.id,
                            name=poke.name, types=poke.types)

        for h in hdata:
            human = Human(name=h["name"], role=h["role"],
                          owned_pokemon_ids=h["owned_pokemon_ids"],
                          specializes_in=h["specializes_in"],
                          description=h["description"], canon=h["canon"])
            self.humans[human.name] = human
            self.g.add_node(f"human:{human.name}", kind="human",
                            name=human.name, role=human.role)

        self._build_edges()
        return self

    def _edge(self, u: str, v: str, rel: str):
        self.g.add_edge(u, v, rel=rel)

    def _build_edges(self):
        for pid, poke in self.pokemon.items():
            me = f"pokemon:{pid}"
            for t in poke.types:
                self._edge(me, f"type:{t}", HAS_TYPE)
            for evo in poke.evolution_ids:
                self._edge(me, f"pokemon:{evo}", EVOLVES_TO)
            for ab in poke.abilities:
                anode = f"ability:{ab}"
                if anode not in self.g:
                    self.g.add_node(anode, kind="ability", name=ab)
                self._edge(me, anode, HAS_ABILITY)
            for m in poke.signature_moves:
                if m in self.moves:
                    self._edge(me, f"move:{m}", LEARNS_MOVE)
            weak, resist, immune = self._defensive_matchups(poke.types)
            for t in weak:
                self._edge(me, f"type:{t}", WEAK_TO)
            for t in resist:
                self._edge(me, f"type:{t}", RESISTANT_TO)
            for t in immune:
                self._edge(me, f"type:{t}", IMMUNE_TO)

        for human in self.humans.values():
            me = f"human:{human.name}"
            for pid in human.owned_pokemon_ids:
                if pid in self.pokemon:
                    self._edge(me, f"pokemon:{pid}", OWNED_BY)
            for t in human.specializes_in:
                if t in self.types:
                    self._edge(me, f"type:{t}", SPECIALIZES_IN)

    def _defensive_matchups(self, types: list[str]):
        """(weak_to, resistant_to, immune_to) attacking-type sets for a defender."""
        weak, resist, immune = set(), set(), set()
        for atk, table in self._chart.items():
            mult = 1.0
            for d in types:
                mult *= table.get(d, 1.0)
            if mult == 0:
                immune.add(atk)
            elif mult > 1:
                weak.add(atk)
            elif mult < 1:
                resist.add(atk)
        return weak, resist, immune

    # -- lookups ----------------------------------------------------------
    def get_pokemon(self, ref: int | str) -> Pokemon:
        if isinstance(ref, int):
            return self.pokemon[ref]
        key = normalize_name(ref)
        if key.isdigit():
            return self.pokemon[int(key)]
        return self.pokemon_by_name[key]

    def get_human(self, name: str) -> Human:
        for hname, h in self.humans.items():
            if hname.lower() == name.strip().lower():
                return h
        raise KeyError(f"unknown human: {name}")

    # -- queries ----------------------------------------------------------
    def evolution_chain(self, ref: int | str) -> list[Pokemon]:
        """Full evolution line containing this Pokemon, in order."""
        start = self.get_pokemon(ref)
        # walk back to the base form
        node = start.id
        while True:
            preds = [u for u, v, d in self.g.in_edges(f"pokemon:{node}", data=True)
                     if d.get("rel") == EVOLVES_TO]
            if not preds:
                break
            node = int(preds[0].split(":")[1])
        chain, seen = [], set()
        while node not in seen:
            seen.add(node)
            chain.append(self.pokemon[node])
            succs = sorted(int(v.split(":")[1]) for _, v, d
                           in self.g.out_edges(f"pokemon:{node}", data=True)
                           if d.get("rel") == EVOLVES_TO)
            node = succs[0] if succs else -1
            if node == -1:
                break
        return chain

    def type_matchups(self, type_name: str) -> dict[str, set[str]]:
        """For a defending type: which attacking types it's weak/resistant/immune to."""
        t = type_name.strip().lower()
        weak = {atk for atk, table in self._chart.items() if table.get(t, 1.0) > 1}
        resist = {atk for atk, table in self._chart.items() if 0 < table.get(t, 1.0) < 1}
        immune = {atk for atk, table in self._chart.items() if table.get(t, 1.0) == 0}
        return {"weak_to": weak, "resistant_to": resist, "immune_to": immune}

    def pokemon_weaknesses(self, ref: int | str) -> dict[str, set[str]]:
        poke = self.get_pokemon(ref)
        weak, resist, immune = self._defensive_matchups(poke.types)
        return {"weak_to": weak, "resistant_to": resist, "immune_to": immune}

    def pokemon_of_human(self, name: str) -> list[Pokemon]:
        human = self.get_human(name)
        return [self.pokemon[pid] for pid in human.owned_pokemon_ids
                if pid in self.pokemon]

    def humans_for_pokemon(self, ref: int | str) -> list[Human]:
        poke = self.get_pokemon(ref)
        return [h for h in self.humans.values() if poke.id in h.owned_pokemon_ids]

    def visual_profile(self, ref: int | str) -> VisualProfile:
        return self.get_pokemon(ref).visual

    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        for _, d in self.g.nodes(data=True):
            kinds[d.get("kind", "?")] = kinds.get(d.get("kind", "?"), 0) + 1
        rels: dict[str, int] = {}
        for _, _, d in self.g.edges(data=True):
            rels[d.get("rel", "?")] = rels.get(d.get("rel", "?"), 0) + 1
        return {"nodes": kinds, "edges": rels}
