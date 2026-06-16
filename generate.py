#!/usr/bin/env python3
"""Generates README.md from config.yml and live GitHub API data."""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
import yaml


GITHUB_USERNAME = os.environ.get("GITHUB_USERNAME", "RenatoAntonioCL")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

SKILLICONS_BASE = "https://skillicons.dev/icons?i="
ICON_MAP = {
    "Python": "python",
    "FastAPI": "fastapi",
    "PostgreSQL": "postgres",
    "SQLAlchemy": None,
    "Docker": "docker",
    "React": "react",
    "TypeScript": "ts",
    "Vite": "vite",
    "Tailwind CSS": "tailwind",
    "GitHub Actions": "githubactions",
    "CI/CD": None,
    "Railway": None,
    "Linux": "linux",
    "Bash": "bash",
    "Git": "git",
    "Claude Code": None,
    "REST APIs": None,
}

BAR_FULL = "█"
BAR_EMPTY = "░"
BAR_WIDTH = 16


def gh_session() -> requests.Session:
    session = requests.Session()
    session.headers["Accept"] = "application/vnd.github+json"
    session.headers["X-GitHub-Api-Version"] = "2022-11-28"
    if GITHUB_TOKEN:
        session.headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return session


def fetch_all_repos(session: requests.Session) -> list[dict]:
    repos = []
    page = 1
    while True:
        resp = session.get(
            "https://api.github.com/user/repos",
            params={"per_page": 100, "page": page, "type": "all"},
            timeout=15,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        repos.extend(batch)
        page += 1
    return repos


def fetch_languages(
    session: requests.Session,
    repos: list[dict],
    exclude: list[str] | None = None,
) -> dict[str, int]:
    excluded = set(exclude or [])
    totals: dict[str, int] = {}
    for repo in repos:
        if repo.get("fork") or repo["name"] in excluded:
            continue
        resp = session.get(
            f"https://api.github.com/repos/{GITHUB_USERNAME}/{repo['name']}/languages",
            timeout=15,
        )
        if resp.status_code == 404:
            continue
        resp.raise_for_status()
        for lang, bytes_count in resp.json().items():
            totals[lang] = totals.get(lang, 0) + bytes_count
    return totals


def build_language_bars(lang_totals: dict[str, int], top_n: int = 5) -> str:
    if not lang_totals:
        return ""
    total = sum(lang_totals.values())
    sorted_langs = sorted(lang_totals.items(), key=lambda x: x[1], reverse=True)[:top_n]
    lines = []
    for lang, count in sorted_langs:
        pct = count / total
        filled = round(pct * BAR_WIDTH)
        bar = BAR_FULL * filled + BAR_EMPTY * (BAR_WIDTH - filled)
        lines.append(f"{lang:<12} {bar}  {pct * 100:4.0f}%")
    return "\n".join(lines)


def stack_icons(tech_list: list[str]) -> str:
    slugs = [ICON_MAP[t] for t in tech_list if ICON_MAP.get(t)]
    if not slugs:
        return ""
    icons = "&i=".join(slugs)
    return f"![Stack](https://skillicons.dev/icons?i={icons})"


def stack_section(stack: dict) -> str:
    sections = {
        "Backend": stack.get("backend", []),
        "Frontend": stack.get("frontend", []),
        "DevOps": stack.get("devops", []),
    }
    lines = []
    for title, tech_list in sections.items():
        slugs = [ICON_MAP[t] for t in tech_list if ICON_MAP.get(t)]
        if not slugs:
            continue
        icon_tags = "\n".join(
            f"![{t}]({SKILLICONS_BASE}{ICON_MAP[t]})"
            for t in tech_list
            if ICON_MAP.get(t)
        )
        lines.append(f"### {title}\n{icon_tags}")
    return "\n\n".join(lines)


def pinned_block(repo: dict, links: dict) -> str:
    name_display = repo["name"].capitalize()
    desc = repo["description"]
    stack_badges = " ".join(f"`{s}`" for s in repo["stack"])

    if repo.get("private"):
        header = f"**{name_display}**"
        footer = f"{stack_badges} *(private repo)*"
    else:
        repo_url = f"https://github.com/{GITHUB_USERNAME}/{repo['name']}"
        header = f"**[{name_display}]({repo_url})**"
        extra_link = ""
        if repo["name"] == "genpy":
            extra_link = f" · [{links['genpy_site']}]({links['genpy_site']})"
        footer = f"{stack_badges}{extra_link}"

    return f"{header} — {desc}\n{footer}"


def how_i_work_lines(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def generate_readme(config: dict, lang_bars: str) -> str:
    bio = config["bio"]
    links = config["links"]
    pinned = config["pinned_repos"]
    stack = config["stack"]
    hiw = config["how_i_work"]

    timestamp = datetime.now(ZoneInfo("America/Santiago")).strftime("%b %-d, %Y at %H:%M CLT")

    pinned_sections = "\n\n".join(pinned_block(r, links) for r in pinned)
    stack_md = stack_section(stack)
    hiw_md = how_i_work_lines(hiw)

    readme = f"""\
# Hey, I'm Renato 👋

{bio['tagline']}

{bio['description'].strip()}

---

## What I'm building

{pinned_sections}

---

## Stack

{stack_md}

---

## Top languages (across all repos)

```
{lang_bars}
```

---

## How I work

{hiw_md}

---

## Find me

[![LinkedIn](https://img.shields.io/badge/LinkedIn-renatoantoniocl-0A66C2?style=flat&logo=linkedin)]({links['linkedin']})
[![GenPy](https://img.shields.io/badge/GenPy-genpy--cli.vercel.app-1D9E75?style=flat)]({links['genpy_site']})

---

*README auto-generated by [generate.py](./generate.py) · Last updated: {timestamp}*
"""
    return readme


def main() -> None:
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    session = gh_session()

    print("Fetching all repos...")
    try:
        repos = fetch_all_repos(session)
        print(f"  Found {len(repos)} public repos")
        print("Fetching language stats...")
        exclude = config.get("exclude_from_stats", [])
        lang_totals = fetch_languages(session, repos, exclude)
    except requests.HTTPError as exc:
        print(f"GitHub API error: {exc}", file=sys.stderr)
        lang_totals = {}

    lang_bars = build_language_bars(lang_totals)

    readme = generate_readme(config, lang_bars)

    output_path = os.path.join(os.path.dirname(__file__), "README.md")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(readme)

    print(f"README.md written to {output_path}")


if __name__ == "__main__":
    main()
