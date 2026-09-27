"""Fetch Gen-1 Pokemon (#1-150) from PokeAPI and build data/pokemon_gen1.json.

Raw responses are cached under data/.cache/ (gitignored) so rebuilds are
polite. The committed data/pokemon_gen1.json is sufficient to run everything
offline -- tests never touch the network.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.request

API = "https://pokeapi.co/api/v2"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
CACHE = os.path.join(DATA, ".cache")
WING_SHAPES = {"wings", "bug-wings"}


def _cache_path(url: str) -> str:
    return os.path.join(CACHE, hashlib.sha1(url.encode()).hexdigest() + ".json")


def fetch(url: str) -> dict:
    os.makedirs(CACHE, exist_ok=True)
    path = _cache_path(url)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    req = urllib.request.Request(url, headers={"User-Agent": "poke-consistency-kit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    time.sleep(0.05)  # be polite
    return data


def _species_id(url: str) -> int:
    return int(url.rstrip("/").split("/")[-1])


def _chain_edges(chain_url: str) -> list[tuple[int, int]]:
    """Parent->child evolution edges, filtered to Gen-1 ids (1-150)."""
    chain = fetch(chain_url)["chain"]
    edges: list[tuple[int, int]] = []

    def walk(node, parent_id: int | None):
        sid = _species_id(node["species"]["url"])
        if parent_id is not None and 1 <= sid <= 150 and 1 <= parent_id <= 150:
            edges.append((parent_id, sid))
        for child in node.get("evolves_to", []):
            walk(child, sid)

    walk(chain, None)
    return edges


def _signature_moves(poke: dict) -> list[str]:
    """Up to 4 Red/Blue level-up moves, preferring the highest-level ones."""
    found: list[tuple[int, str]] = []
    for m in poke.get("moves", []):
        for v in m["version_group_details"]:
            if (v["version_group"]["name"] == "red-blue"
                    and v["move_learn_method"]["name"] == "level-up"):
                found.append((v["level_learned_at"], m["move"]["name"]))
    found.sort()
    return [name for _, name in found[-4:]]


def build() -> dict:
    with open(os.path.join(DATA, "visual_curation.json"), encoding="utf-8") as f:
        curation = json.load(f)

    pokemons: list[dict] = []
    evo_edges: set[tuple[int, int]] = set()
    seen_chains: set[str] = set()
    move_names: set[str] = set()

    for pid in range(1, 151):
        poke = fetch(f"{API}/pokemon/{pid}")
        species = fetch(f"{API}/pokemon-species/{pid}")

        color = (species.get("color") or {}).get("name", "")
        shape = (species.get("shape") or {}).get("name", "")
        genera = next((g["genus"] for g in species.get("genera", [])
                       if g["language"]["name"] == "en"), "")
        chain_url = species["evolution_chain"]["url"]
        if chain_url not in seen_chains:
            seen_chains.add(chain_url)
            evo_edges.update(_chain_edges(chain_url))

        sig = _signature_moves(poke)
        move_names.update(sig)

        cur = curation.get(str(pid), {})
        sprites = poke.get("sprites", {})
        artwork = (sprites.get("other", {}).get("official-artwork", {})
                   .get("front_default"))

        pokemons.append({
            "id": poke["id"],
            "name": poke["name"],
            "types": [t["type"]["name"] for t in
                      sorted(poke["types"], key=lambda t: t["slot"])],
            "abilities": [a["ability"]["name"] for a in poke["abilities"]],
            "base_stats": {s["stat"]["name"]: s["base_stat"] for s in poke["stats"]},
            "height_dm": poke["height"],
            "weight_hg": poke["weight"],
            "color": color,
            "shape": shape,
            "genera": genera,
            "signature_moves": sig,
            "visual": {
                "body_colors": cur.get("colors", [color] if color else []),
                "has_wings": cur.get("has_wings", shape in WING_SHAPES),
                "can_fly": cur.get("fly", False),
                "limb_description": cur.get("limbs", ""),
                "distinctive_features": cur.get("features", []),
                "sprite_urls": {
                    "default": sprites.get("front_default") or "",
                    "official_artwork": artwork or "",
                },
            },
        })
        if pid % 25 == 0:
            print(f"  fetched {pid}/150")

    evo_map: dict[int, list[int]] = {}
    for a, b in sorted(evo_edges):
        evo_map.setdefault(a, []).append(b)

    moves: dict[str, dict] = {}
    for name in sorted(move_names):
        m = fetch(f"{API}/move/{name}")
        moves[name] = {"type": m["type"]["name"], "power": m["power"]}

    for p in pokemons:
        p["evolution_ids"] = evo_map.get(p["id"], [])

    return {"pokemon": pokemons, "moves": moves}


def main() -> None:
    print("Building data/pokemon_gen1.json from PokeAPI (cached in data/.cache/)...")
    data = build()
    out = os.path.join(DATA, "pokemon_gen1.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    kb = os.path.getsize(out) / 1024
    print(f"Wrote {out} ({kb:.0f} KB, {len(data['pokemon'])} pokemon, "
          f"{len(data['moves'])} moves)")


if __name__ == "__main__":
    main()
