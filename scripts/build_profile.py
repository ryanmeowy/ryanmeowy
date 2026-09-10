#!/usr/bin/env python3
"""Build README cards; --refresh also counts public source snapshots with cloc."""

import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fnmatch import fnmatch
from html import escape
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from textwrap import wrap
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
USERNAME = "ryanmeowy"
# These two default branches contain published output or image assets, not source.
EXCLUDED_REPOS = {
    "ryanmeowy/ryanxys.github.io": "Generated Hexo site: rendered posts and theme assets",
    "ryanmeowy/pic": "Image asset repository, no source files",
}
# ponytail: explicit generated-file rules; extend them when a new generator is added.
EXCLUDED_DIRS = {
    ".git", "node_modules", "vendor", "third_party", "third-party", ".venv", "venv",
    ".tox", "__pycache__", "site-packages", "dist", "build", "target", "out",
    "coverage", ".next", ".nuxt", ".output", ".cache", ".gradle", ".idea", ".vscode",
    "generated", "generated-sources", "Pods", "Carthage", ".build", ".swiftpm",
    ".ipynb_checkpoints",
}
EXCLUDED_FILES = (
    "package-lock.json", "npm-shrinkwrap.json", "pnpm-lock.yaml", "yarn.lock",
    "bun.lock", "bun.lockb", "poetry.lock", "uv.lock", "Pipfile.lock", "Cargo.lock",
    "composer.lock", "Gemfile.lock", "go.sum", "*.min.js", "*.min.css", "*.map",
    "*_pb2.py", "*_pb2_grpc.py", "*.pb.go", "*.generated.*",
    "mvnw", "mvnw.cmd", "gradlew", "gradlew.bat",
)
EXCLUDED_EXTENSIONS = "md,markdown,rst,txt,csv,tsv,svg,lock"
# Edit these lines, then run: python3 scripts/build_profile.py
FIELDS = [
    ("user", "Name", "ryan"),
    ("terminal", "Role", "Backend Engineer"),
    ("target", "Focus", "Search / RAG / Agent"),
    ("code", "Languages", "Java, Python"),
    ("box", "Tools", "Elasticsearch, Spring Boot"),
    ("book", "Currently", "Building Anchr"),
    ("pin", "Location", "Shanghai, China"),
    ("heart", "Interests", "Tech, Cats, Coffee, Photography"),
    ("bolt", "Status", "Always Learning"),
]
COLORS = dict(bg="#091119", border="#38648a", text="#edf3fc",
              muted="#87a1bf", blue="#64c5ff", green="#60ef81", gold="#f5d76b", red="#ff696e")
ICONS = {
    "heart": '<path d="M10 19 2 11C-4 4 5-2 10 4c5-6 14 0 8 7z" fill="currentColor" stroke="none"/>',
    "people": '<circle cx="7" cy="6" r="3" fill="currentColor"/><circle cx="15" cy="7" r="2.5" fill="currentColor"/><path d="M1 19v-3a6 6 0 0 1 12 0v3zm13-8a5 5 0 0 1 5 5v3h-4"/>',
    "branch": '<circle cx="4" cy="4" r="2.5"/><circle cx="16" cy="4" r="2.5"/><circle cx="10" cy="17" r="2.5"/><path d="M4 7v3l6 4 6-4V7"/>',
    "commit": '<rect x="1" y="1" width="5" height="5" rx="1"/><rect x="1" y="14" width="5" height="5" rx="1"/><rect x="14" y="1" width="5" height="5" rx="1"/><rect x="14" y="14" width="5" height="5" rx="1"/><path d="M3.5 6v8m13-8v8M6 3.5h8M6 16.5h8"/>',
    "monitor": '<path d="M2 1h16v14H2zM2 12h16M10 15v4m-5 0h10"/>',
    "clock": '<circle cx="10" cy="10" r="9"/><path d="M10 4v7l5 3"/>',
    "trophy": '<path d="M5 1h10v7a5 5 0 0 1-10 0zm0 2H1v3a5 5 0 0 0 5 5m9-8h4v3a5 5 0 0 1-5 5m-4 2v6m-5 0h10"/>',
    "user": '<circle cx="10" cy="5" r="3"/><path d="M3 19v-3a7 7 0 0 1 14 0v3z"/>',
    "terminal": '<path d="m3 4 6 6-6 6m9 1h6"/>',
    "target": '<circle cx="10" cy="10" r="8"/><circle cx="10" cy="10" r="4"/><path d="m10 10 9-9m-4 0h4v4"/>',
    "code": '<path d="m6 4-5 6 5 6m8-12 5 6-5 6M12 2 8 18"/>',
    "box": '<path d="m10 1 8 4v10l-8 4-8-4V5zm0 8v10M2 5l8 4 8-4M6 3l8 4"/>',
    "book": '<path d="M10 4C6 1 2 2 1 3v14c3-1 6-1 9 2 3-3 6-3 9-2V3c-3-1-6-1-9 1v15"/>',
    "pin": '<path d="M17 8c0 5-7 11-7 11S3 13 3 8a7 7 0 1 1 14 0Z"/><circle cx="10" cy="8" r="2"/>',
    "bolt": '<path d="m12 1-9 10h7l-2 8 9-11h-7z" fill="currentColor"/>',
    "stats": '<path d="M2 19V12h3v7m4 0V7h3v12m4 0V1h3v18"/>',
    "star": '<path d="m10 1 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z"/>',
    "calendar": '<rect x="2" y="4" width="16" height="15" rx="2"/><path d="M6 1v6m8-6v6M2 10h16"/>',
    "cup": '<path d="M3 8h12v6a5 5 0 0 1-5 5H8a5 5 0 0 1-5-5zm12 1h2a3 3 0 0 1 0 6h-2M6 4V1m5 3V1M1 21h18"/>',
}


def github(path, payload=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "ryanmeowy-profile"}
    if token := os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(payload).encode() if payload is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    with urlopen(Request(f"https://api.github.com/{path}", headers=headers, data=data), timeout=30) as response:
        result = json.load(response)
    if isinstance(result, dict) and result.get("errors"):
        raise RuntimeError("GitHub query failed: " + str(result["errors"]))
    return result


def count_repository(repo):
    name, branch = repo["full_name"], repo["default_branch"]
    result = {"repository": name, "branch": branch, "commit": None, "files": 0, "code": 0}
    if name in EXCLUDED_REPOS:
        return {**result, "excluded": EXCLUDED_REPOS[name]}
    try:
        result["commit"] = github(f"repos/{name}/commits/{quote(branch, safe='')}")["sha"]
    except HTTPError as error:
        if error.code == 409:  # GitHub returns 409 for an empty repository.
            return {**result, "empty": True}
        raise
    with TemporaryDirectory(prefix="profile-loc-") as directory:
        root = Path(directory)
        # Public codeload URL: never forward the GitHub API token to this host.
        url = f'https://codeload.github.com/{name}/tar.gz/{result["commit"]}'
        with urlopen(url, timeout=120) as response, tarfile.open(fileobj=response, mode="r|gz") as archive:
            for member in archive:
                if not member.isfile():  # No links, devices, or archive extraction commands.
                    continue
                path = PurePosixPath(member.name)
                parts = path.parts[1:]  # GitHub adds a repository-SHA root directory.
                if path.is_absolute() or ".." in path.parts or not parts:
                    raise ValueError("Unsafe source archive path")
                if EXCLUDED_DIRS.intersection(parts[:-1]) or any(fnmatch(parts[-1], pattern) for pattern in EXCLUDED_FILES):
                    continue
                if name == f"{USERNAME}/{USERNAME}" and parts == ("assets", "stats.json"):
                    continue  # Do not count this workflow's generated snapshot as source.
                destination = root.joinpath(*parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(member) as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
        report = subprocess.run(
            ["cloc", "--config=/dev/null", "--json", "--quiet", "--no-autogen",
             "--timeout=30", f"--exclude-ext={EXCLUDED_EXTENSIONS}",
             "--exclude-lang=Text,Markdown,reStructuredText",
             "--exclude-content=(?mi)^(?://|#|/\\*|\\*|<!--)\\s*(?:Code generated .* DO NOT EDIT|@generated|This file is auto-generated)",
             str(root)],
            check=True, capture_output=True, text=True, timeout=180,
        )
        if report.stderr.strip():
            raise RuntimeError(f"cloc could not fully count {name}: {report.stderr.strip()}")
        counts = json.loads(report.stdout or "{}")
        total = counts.get("SUM", {})
        result.update(files=total.get("nFiles", 0), code=total.get("code", 0))
        result["languages"] = {key: value["code"] for key, value in counts.items() if key not in {"header", "SUM"}}
    print(f'{name}: {result["code"]:,} code lines', flush=True)
    return result


def count_lines_of_code(repos):
    if not shutil.which("cloc"):
        raise RuntimeError("Install cloc to refresh code line counts; offline rendering needs no cloc.")
    source_repos = sorted(
        (repo for repo in repos if not repo["fork"] and not repo["private"]
         and repo["owner"]["login"].lower() == USERNAME.lower()),
        key=lambda repo: repo["full_name"].lower(),
    )
    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(count_repository, source_repos))


def fetch_stats():
    if not (os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")):
        raise RuntimeError("Set GH_TOKEN or GITHUB_TOKEN to refresh GitHub contribution data.")
    user = github(f"users/{USERNAME}")
    repos = []
    page = 1
    while True:
        batch = github(f"users/{USERNAME}/repos?type=owner&per_page=100&page={page}")
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    now = datetime.now(timezone.utc)
    years = range(int(user["created_at"][:4]), now.year + 1)
    # Separate calendar-year ranges avoid double counting the all-time commit total.
    periods = []
    for year in years:
        start = f"{year}-01-01T00:00:00Z"
        end = (now.isoformat(timespec="seconds").replace("+00:00", "Z")
               if year == now.year else f"{year}-12-31T23:59:59Z")
        periods.append(f'y{year}: contributionsCollection(from: "{start}", to: "{end}") {{ totalCommitContributions }}')
    query = ('query { user(login: "' + USERNAME + '") { ' + ' '.join(periods)
             + ' recent: contributionsCollection { contributionCalendar { totalContributions } } } }')
    activity = github("graphql", {"query": query})["data"]["user"]
    code_repositories = count_lines_of_code(repos)
    return {
        "repos": user["public_repos"],
        "stars": sum(repo["stargazers_count"] for repo in repos if not repo["fork"]),
        "followers": user["followers"],
        "following": user["following"],
        "commits": sum(activity[f"y{year}"]["totalCommitContributions"] for year in years),
        "contributions": activity["recent"]["contributionCalendar"]["totalContributions"],
        "lines_of_code": sum(repo["code"] for repo in code_repositories),
        "code_counting": {
            "tool": "cloc " + subprocess.check_output(["cloc", "--version"], text=True).strip(),
            "scope": "Owned public non-fork default branches; excludes dependencies, generated output, comments and blank lines",
            "repositories": code_repositories,
        },
        "since": int(user["created_at"][:4]),
        "updated": datetime.now(timezone.utc).date().isoformat(),
    }


def text(x, y, value, color="text", size=20, weight=400):
    return (f'<text xml:space="preserve" x="{x}" y="{y}" fill="{COLORS[color]}" '
            f'font-size="{size}" font-weight="{weight}">{escape(str(value))}</text>')


def icon(name, x, y, color="blue", size=18):
    return (f'<g transform="translate({x} {y}) scale({size / 20})" fill="none" '
            f'color="{COLORS[color]}" stroke="{COLORS[color]}" stroke-width="1.7" stroke-linecap="round" '
            f'stroke-linejoin="round">{ICONS[name]}</g>')


def line(x1, y, x2):
    return f'<path d="M{x1} {y}H{x2}" stroke="{COLORS["blue"]}" stroke-width="1.6" stroke-dasharray="10 2"/>'


def render(stats, illustration, mobile=False):
    width, height = (600, 1444) if mobile else (1672, 941)
    frame_x, frame_y = (12, 16) if mobile else (38, 68)
    frame_w, frame_h = (576, 1412) if mobile else (1596, 814)
    art_x, art_y, art_w, art_h = (32, 92, 536, 429) if mobile else (64, 135, 818, 651)
    panel_x, panel_y = (36, 570) if mobile else (916, 164)
    panel_right = 564 if mobile else 1588
    value_x = 230 if mobile else 1158
    label_x = panel_x + (36 if mobile else 54)
    size, step = (22, 34) if mobile else (22, 33)
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">ryanmeowy@github — pixel workspace</title>',
        '<desc id="desc">Ryan, backend engineer. Search / RAG / Agent. Java, Python. Building Anchr in Shanghai. Pixel art of a programmer with clear-lens eyeglasses and a sleeping cat, technical books, coffee and a Shanghai moonlit skyline.</desc>',
        '<defs><radialGradient id="canvas"><stop stop-color="#102139"/><stop offset="1" stop-color="#050d16"/></radialGradient>',
        '<linearGradient id="terminal" x2="0" y2="1"><stop stop-color="#091119"/><stop offset=".6" stop-color="#080f17"/><stop offset="1" stop-color="#0a131e"/></linearGradient>',
        '<filter id="glow" x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="5"/></filter></defs>',
        f'<path fill="url(#canvas)" d="M0 0h{width}v{height}H0z"/>',
        f'<rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" rx="14" fill="none" stroke="#204b7d" stroke-width="5" opacity=".35" filter="url(#glow)"/>',
        f'<rect x="{frame_x}" y="{frame_y}" width="{frame_w}" height="{frame_h}" rx="14" fill="url(#terminal)" stroke="#4983b1" stroke-width="1.5"/>',
        f'<rect x="{frame_x+16}" y="{frame_y+52}" width="{frame_w-32}" height="{frame_h-72}" rx="8" fill="none" stroke="#243f56" stroke-width="1.5"/>',
        '<g font-family="Menlo, Consolas, Liberation Mono, monospace">',
    ]
    for offset, color in [(36, "#ff605e"), (74, "#ffcb3d"), (112, "#52ec6c")]:
        svg.append(f'<circle cx="{frame_x+offset}" cy="{frame_y+30}" r="10" fill="{color}"/>')
    svg.append(f'<image x="{art_x}" y="{art_y}" width="{art_w}" height="{art_h}" preserveAspectRatio="none" xlink:href="data:image/png;base64,{illustration}"/>')
    svg += [text(panel_x, panel_y, USERNAME, "green", 28, 600),
            text(panel_x + 152, panel_y, "@github", "blue", 28, 600),
            line(panel_x, panel_y + 18, panel_right)]
    y = panel_y + 56
    for name, label, value in FIELDS:
        color = "green" if label == "Status" else "text"
        glyph_color = {"Status": "gold", "Interests": "red"}.get(label, "blue")
        svg += [icon(name, panel_x + 1, y - 21, glyph_color, 25),
                text(label_x, y, label, "blue", size),
                text(value_x - (24 if mobile else 36), y, ":", "text", size)]
        values = (value.split(", ") if label == "Tools" else wrap(value, width=24)) if mobile else [value]
        for part in values:
            svg.append(text(value_x, y, part, color, size))
            y += step
    y += 32
    svg += [icon("stats", panel_x, y - 23, "green", 26),
            text(label_x, y, "GitHub Stats", "blue", 26, 600),
            line(panel_x, y + 16, panel_right)]
    rows = [
        (("monitor", "Repos", "repos"), ("people", "Followers", "followers")),
        (("commit", "Commits", "commits"), ("branch", "Following", "following")),
        (("code", "Lines of Code", "lines_of_code"), ("clock", "Since", "since")),
        (("star", "Stars", "stars"), ("trophy", "Contribution", "contributions")),
    ]
    divider = 303 if mobile else 1219
    svg.append(f'<path d="M{divider} {y+40}v123" stroke="{COLORS["muted"]}" stroke-width="1" stroke-dasharray="7 4"/>')
    for row, pair in enumerate(rows):
        for column, (glyph, label, key) in enumerate(pair):
            x = panel_x + column * (280 if mobile else 324)
            baseline = y + 54 + row * 34
            label_offset = 34 if mobile else (56 if column == 0 else 44)
            colon_x = x + (177 if mobile else (204 if column == 0 else 184))
            number_x = x + (198 if mobile else (224 if column == 0 else 208))
            value = stats.get(key)
            display = "—" if value is None else str(value) if key == "since" else f"{value:,}"
            glyph_color = "gold" if glyph in {"star", "code"} else "text" if column == 0 else "blue"
            tooltip = {
                "commits": "Sum of GitHub commit contributions since account creation; excludes commits not counted by GitHub's contribution graph.",
                "lines_of_code": "Current source lines measured by cloc across owned public non-fork default branches, excluding dependencies, generated output, comments and blank lines. Not an authorship total.",
                "contributions": "Contributions during the last 12 months, as returned by GitHub.",
            }.get(key, label)
            svg += ['<g><title>' + escape(tooltip) + '</title>',
                    icon(glyph, x + 3, baseline - 20, glyph_color, 23 if mobile else 25),
                    text(x + label_offset, baseline, label, "blue", 17 if mobile else 18),
                    text(colon_x, baseline, ":", "text", 18),
                    text(number_x, baseline, display, "text", 18 if mobile else 19), '</g>']
            if key == "contributions" and not mobile:
                svg.append(text(number_x + len(display)*11.5 + 10, baseline, "(last year)", "muted", 15))
    cat_x, cat_y = (350, 1260) if mobile else (1360, 780)
    cat_lines = ["  /\\_/\\", " / ^ ^ \\", "(  ·ω·  )", " \\_____/"]
    # SVG collapses leading spaces by default, shifting the ears and chin left.
    svg.append('<g id="cat-art">')
    for row, value in enumerate(cat_lines):
        svg.append(text(cat_x, cat_y + row*21, value, "text", 20))
    svg.append('</g>')
    for row, value in enumerate(["Good", "Search", "Better", "Answers."]):
        svg.append(text(cat_x + 127, cat_y + row*20, value, "text", 18))
    if mobile:
        svg += [text(36, y + 209, "Contribution: last year", "muted", 16),
                text(36, 1290, "// still searching", "muted", 16),
                text(36, 1316, "// for a better tomorrow ...", "muted", 16),
                '<g font-style="italic">' + text(40, 1384, '“ A search engine for my second brain. ”', "muted", 19) + '</g>']
    else:
        svg += [text(70, 834, "// still searching for a better tomorrow ...", "muted", 20),
                f'<path d="M599 815h11v26h-11z" fill="{COLORS["muted"]}"/>',
                '<g font-style="italic">' + text(806, 834, '“ A search engine for my second brain. ”', "muted", 19) + '</g>']
    svg += ['</g>', '</svg>']
    return "\n".join(svg) + "\n"

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Fetch current public GitHub statistics")
    args = parser.parse_args()
    stats_path = ASSETS / "stats.json"
    # A failed refresh exits before writing, preserving the last successful cards.
    stats = fetch_stats() if args.refresh else json.loads(stats_path.read_text())
    illustration = base64.b64encode((ASSETS / "workspace.png").read_bytes()).decode("ascii")
    cards = {"hero.svg": render(stats, illustration), "hero-mobile.svg": render(stats, illustration, True)}
    for filename, contents in cards.items():
        (ASSETS / filename).write_text(contents, encoding="utf-8")
    if args.refresh:
        stats_path.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print("Built assets/hero.svg and assets/hero-mobile.svg")


if __name__ == "__main__":
    main()
