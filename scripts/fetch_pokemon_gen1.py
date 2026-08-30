#!/usr/bin/env python3
"""Generate RAG-ready Markdown for the first 151 Pokémon using PokéAPI."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


API_ROOT = "https://pokeapi.co/api/v2"
GEN1_IDS = range(1, 152)
LANGUAGE_PRIORITY = ("zh-hant", "zh-hans", "en", "ja")
STAT_NAMES = {
    "hp": "HP",
    "attack": "攻擊",
    "defense": "防禦",
    "special-attack": "特攻",
    "special-defense": "特防",
    "speed": "速度",
}


@lru_cache(maxsize=None)
def fetch_json(url: str) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "openai-chatbot-rag-dataset/1.0"})
    for attempt in range(4):
        try:
            with urlopen(request, timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2**attempt)
    raise RuntimeError(f"Unable to fetch {url}")


def localized_name(resource: dict[str, Any]) -> str:
    names = {
        entry["language"]["name"]: entry["name"]
        for entry in resource.get("names", [])
    }
    for language in LANGUAGE_PRIORITY:
        if names.get(language):
            return names[language]
    return resource.get("name", "未知")


def fetch_many(urls: set[str], workers: int) -> dict[str, dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_json, url): url for url in sorted(urls)}
        for future in as_completed(futures):
            url = futures[future]
            results[url] = future.result()
    return results


def evolution_names(
    node: dict[str, Any],
    species_by_url: dict[str, dict[str, Any]],
) -> list[list[str]]:
    current_url = node["species"]["url"]
    current = localized_name(species_by_url.get(current_url, node["species"]))
    children = node.get("evolves_to", [])
    if not children:
        return [[current]]

    paths: list[list[str]] = []
    for child in children:
        for path in evolution_names(child, species_by_url):
            paths.append([current, *path])
    return paths


def evolution_species_urls(node: dict[str, Any]) -> set[str]:
    urls = {node["species"]["url"]}
    for child in node.get("evolves_to", []):
        urls.update(evolution_species_urls(child))
    return urls


def red_blue_moves(pokemon: dict[str, Any]) -> tuple[list[tuple[int, str]], list[str]]:
    level_up: list[tuple[int, str]] = []
    machine: list[str] = []
    for move in pokemon["moves"]:
        for detail in move["version_group_details"]:
            if detail["version_group"]["name"] != "red-blue":
                continue
            method = detail["move_learn_method"]["name"]
            if method == "level-up":
                level_up.append((detail["level_learned_at"], move["move"]["url"]))
            elif method == "machine":
                machine.append(move["move"]["url"])
    return sorted(set(level_up)), sorted(set(machine))


def render_document(
    pokemon: dict[str, Any],
    species: dict[str, Any],
    resources: dict[str, dict[str, Any]],
    species_by_url: dict[str, dict[str, Any]],
    evolution: dict[str, Any],
) -> str:
    number = pokemon["id"]
    chinese_name = localized_name(species)
    english_name = pokemon["name"].replace("-", " ").title()

    types = [localized_name(resources[item["type"]["url"]]) for item in pokemon["types"]]
    abilities = [
        localized_name(resources[item["ability"]["url"]])
        for item in pokemon["abilities"]
    ]
    stats = {
        STAT_NAMES[item["stat"]["name"]]: item["base_stat"]
        for item in pokemon["stats"]
    }
    total = sum(stats.values())

    level_moves, machine_moves = red_blue_moves(pokemon)
    rendered_level_moves = [
        f"Lv.{level if level > 0 else 1} {localized_name(resources[url])}"
        for level, url in level_moves
    ]
    rendered_machine_moves = [localized_name(resources[url]) for url in machine_moves]

    paths = evolution_names(evolution["chain"], species_by_url)
    rendered_paths = [" → ".join(path) for path in paths]

    stat_text = "、".join(f"{name} {value}" for name, value in stats.items())
    lines = [
        f"# #{number:03d} {chinese_name}（{english_name}）",
        "",
        "## 基本資料",
        "",
        f"- 全國圖鑑編號：{number}",
        f"- 中文名稱：{chinese_name}",
        f"- 英文名稱：{english_name}",
        f"- 屬性：{'／'.join(types)}",
        f"- 身高：{pokemon['height'] / 10:g} 公尺",
        f"- 體重：{pokemon['weight'] / 10:g} 公斤",
        f"- 基礎經驗值：{pokemon.get('base_experience', '未知')}",
        "",
        "## 特性",
        "",
        f"- 現行特性：{'、'.join(abilities) if abilities else '無資料'}",
        "- 注意：第一世代《紅／綠／藍》原作尚未引入寶可夢特性系統。",
        "",
        "## 種族值",
        "",
        f"- {stat_text}",
        f"- 種族值總和：{total}",
        "- 注意：此處為 PokéAPI 現行六項種族值，不代表第一世代原作的單一「特殊」數值。",
        "",
        "## 進化鏈",
        "",
        *[f"- {path}" for path in rendered_paths],
        "",
        "## 第一世代《紅／綠》招式",
        "",
        "### 升級可學",
        "",
        f"- {'、'.join(rendered_level_moves) if rendered_level_moves else '無資料'}",
        "",
        "### 招式學習器可學",
        "",
        f"- {'、'.join(rendered_machine_moves) if rendered_machine_moves else '無資料'}",
        "",
        "## 資料範圍與來源",
        "",
        "- 本文件整理結構化事實資料，不收錄 Pokédex flavor text。",
        f"- Pokémon API：{API_ROOT}/pokemon/{number}/",
        f"- Species API：{API_ROOT}/pokemon-species/{number}/",
        "- 資料來源：PokéAPI（https://pokeapi.co/）",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("documents/pokemon_gen1"),
    )
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    pokemon_urls = {f"{API_ROOT}/pokemon/{number}/" for number in GEN1_IDS}
    species_urls = {f"{API_ROOT}/pokemon-species/{number}/" for number in GEN1_IDS}
    pokemon_by_url = fetch_many(pokemon_urls, args.workers)
    species_by_url = fetch_many(species_urls, args.workers)

    resource_urls: set[str] = set()
    evolution_urls: set[str] = set()
    for pokemon in pokemon_by_url.values():
        resource_urls.update(item["type"]["url"] for item in pokemon["types"])
        resource_urls.update(item["ability"]["url"] for item in pokemon["abilities"])
        for move in pokemon["moves"]:
            if any(
                detail["version_group"]["name"] == "red-blue"
                for detail in move["version_group_details"]
            ):
                resource_urls.add(move["move"]["url"])
    for species in species_by_url.values():
        evolution_urls.add(species["evolution_chain"]["url"])

    resources = fetch_many(resource_urls, args.workers)
    evolutions = fetch_many(evolution_urls, args.workers)
    evolution_species = set().union(
        *(evolution_species_urls(evolution["chain"]) for evolution in evolutions.values())
    )
    missing_species = evolution_species.difference(species_by_url)
    species_by_url.update(fetch_many(missing_species, args.workers))

    for number in GEN1_IDS:
        pokemon_url = f"{API_ROOT}/pokemon/{number}/"
        species_url = f"{API_ROOT}/pokemon-species/{number}/"
        pokemon = pokemon_by_url[pokemon_url]
        species = species_by_url[species_url]
        evolution_url = species["evolution_chain"]["url"]
        content = render_document(
            pokemon,
            species,
            resources,
            species_by_url,
            evolutions[evolution_url],
        )
        destination = args.output / f"{number:03d}-{pokemon['name']}.md"
        destination.write_text(content, encoding="utf-8")

    print(f"Generated {len(list(GEN1_IDS))} Pokémon documents in {args.output}")


if __name__ == "__main__":
    main()
