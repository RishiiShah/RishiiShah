"""Refresh the README charts from public GitHub data. Run from any directory."""

from collections import Counter
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

USER = "RishiiShah"
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "stats"
COLORS = {
    "TypeScript": ("83b4e8", "326ba8"), "Python": ("dbbf78", "806000"),
    "Dart": ("7fc9c8", "267b7a"), "HTML": ("d79b85", "a05237"),
    "JavaScript": ("c5bc89", "756a2d"), "CSS": ("b4a1d3", "72549e"),
}


def fetch(url):
    headers = {"User-Agent": "Rishi-profile-stats", "Accept-Language": "en-US"}
    if urlparse(url).hostname == "api.github.com":
        headers["Accept"] = "application/vnd.github+json"
        if os.environ.get("GITHUB_TOKEN"):
            headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urlopen(Request(url, headers=headers), timeout=30) as response:
        return response.read().decode("utf-8")


# shortcut: GitHub's calendar HTML can change; use GraphQL if its markup stops matching.
class Calendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.dates, self.tips = {}, {}
        self.target = None
        self.buffer = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-date" in attrs:
            self.dates[attrs["id"]] = date.fromisoformat(attrs["data-date"])
        if tag == "tool-tip":
            self.target = attrs.get("for")
            self.buffer = ""

    def handle_data(self, data):
        if self.target:
            self.buffer += data

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.target:
            self.tips[self.target] = self.buffer.strip()
            self.target = None

    def days(self, start, end):
        days = {}
        for identifier, day in self.dates.items():
            if start <= day <= end:
                match = re.fullmatch(r"(No|[\d,]+) contributions? on .+\.", self.tips.get(identifier, ""))
                if not match or day.isoformat() in days:
                    raise ValueError(f"Invalid contribution data for {day}")
                days[day.isoformat()] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
        if len(days) != (end - start).days + 1:
            raise ValueError("GitHub returned an incomplete contribution calendar")
        return dict(sorted(days.items()))


def collect_metrics(start, end):
    period = f"{start}..{end}"
    queries = {
        "commits": ("commits", f"committer-date:{period}"),
        "prs": ("issues", f"is:pr created:{period}"),
        "merged_prs": ("issues", f"is:pr is:merged created:{period}"),
    }
    metrics = {}
    for name, (endpoint, filters) in queries.items():
        query = urlencode({"q": f"author:{USER} is:public {filters}", "per_page": 1})
        result = json.loads(fetch(f"https://api.github.com/search/{endpoint}?{query}"))
        count = result.get("total_count")
        if result.get("incomplete_results") is not False or type(count) is not int or count < 0:
            raise ValueError(f"GitHub returned incomplete or invalid {name} counts")
        metrics[name] = count
    if metrics["merged_prs"] > metrics["prs"]:
        raise ValueError("Inconsistent PR totals; retry the refresh")
    return metrics


def collect():
    today = datetime.now(ZoneInfo("America/New_York")).date()
    start = date(today.year, 1, 1)
    calendar = Calendar()
    calendar.feed(fetch(f"https://github.com/users/{USER}/contributions?from={start}&to={today.year}-12-31"))
    days = calendar.days(start, today)
    repos, page = [], 1
    while True:
        batch = json.loads(fetch(f"https://api.github.com/users/{USER}/repos?type=owner&per_page=100&page={page}"))
        if not isinstance(batch, list):
            raise ValueError("GitHub did not return a repository list")
        repos.extend(r for r in batch if not r["private"] and not r["fork"] and r["owner"]["login"].lower() == USER.lower())
        if len(batch) < 100:
            break
        page += 1
    repositories = []
    for repo in sorted(repos, key=lambda r: r["name"].lower()):
        languages = json.loads(fetch(f'https://api.github.com/repos/{USER}/{quote(repo["name"], safe="")}/languages'))
        if not isinstance(languages, dict) or any(type(v) is not int or v < 0 for v in languages.values()):
            raise ValueError("GitHub returned invalid language byte counts")
        repositories.append({"name": repo["name"], "primary_language": repo["language"], "language_bytes": languages})
    return {"username": USER, "date": today.isoformat(), "start": start.isoformat(),
            "scope": "Public repositories owned by RishiiShah, excluding forks. Profile calendar counts include all activity GitHub makes visible.",
            "contributions": days, "repositories": repositories,
            "metrics": collect_metrics(start, today),
            "metrics_scope": "Public indexed commits by committer date; PRs created in the period, with merged PRs a subset of those PRs."}


def summarize(snapshot):
    end = date.fromisoformat(snapshot["date"])
    months = {f"{end.year}-{month:02d}": 0 for month in range(1, end.month + 1)}
    for day, count in snapshot["contributions"].items():
        months[day[:7]] += count
    primary, languages = Counter(), Counter()
    for repo in snapshot["repositories"]:
        primary[repo["primary_language"] or "Unclassified"] += 1
        languages.update(repo["language_bytes"])
    assert sum(months.values()) == sum(snapshot["contributions"].values())
    assert sum(primary.values()) == len(snapshot["repositories"])
    return months, primary, languages


def percentages(values):
    total = sum(values)
    if not total:
        return [0] * len(values)
    parts = [value * 1000 // total for value in values]
    order = sorted(range(len(values)), key=lambda i: -(values[i] * 1000 % total))
    for index in order[:1000 - sum(parts)]:
        parts[index] += 1
    assert sum(parts) == 1000
    return parts


def text(x, y, value, size=15, color=None, end=False, bold=False):
    attrs = f' fill="#{color}"' if color else ""
    attrs += ' text-anchor="end"' if end else ""
    attrs += ' font-weight="600"' if bold else ""
    return f'<text x="{x}" y="{y}" font-size="{size}"{attrs}>{escape(str(value))}</text>'


def svg(width, height, title, body, mode):
    dark = mode == "dark"
    bg, ink, border = ("0e141b", "e6edf3", "26313e") if dark else ("f6f8fa", "1f2937", "d8dee4")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title" fill="#{ink}">'
            f'<title id="title">{escape(title)}</title><style>text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif}}</style>'
            f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" fill="#{bg}" stroke="#{border}"/>{body}</svg>')


def overview(snapshot, mode, compact=False):
    width, cols = (480, 2) if compact else (1000, 4)
    panel, muted = ("151f2a", "a7b3c2") if mode == "dark" else ("e9eef4", "526171")
    body = text(28, 43, "GitHub, at a glance", 26, bold=True)
    body += text(28, 72, f'{snapshot["start"]} — {snapshot["date"]} · year to date', 13, muted)
    metrics = snapshot["metrics"]
    cards = [(sum(snapshot["contributions"].values()), "Contributions", "Profile calendar"),
             (metrics["commits"], "Commits", "Public search index"),
             (metrics["prs"], "Pull requests", "Opened this period"),
             (metrics["merged_prs"], "Merged PRs", "From those opened")]
    step = (width - 56 + 16) / cols
    for i, (value, label, detail) in enumerate(cards):
        x, y = 28 + i % cols * step, 98 + i // cols * 146
        color = ("83b4e8", "7fc9c8", "b4a1d3", "dbbf78")[i] if mode == "dark" else ("326ba8", "267b7a", "72549e", "806000")[i]
        body += f'<rect x="{x}" y="{y}" width="{step-16}" height="130" rx="10" fill="#{panel}"/>'
        body += f'<rect x="{x+18}" y="{y+18}" width="22" height="3" rx="1" fill="#{color}"/>'
        body += text(x+18, y+63, f"{value:,}", 32, bold=True)
        body += text(x+18, y+92, label, 15)
        body += text(x+18, y+114, detail, 12, muted)
    footer = 406 if compact else 262
    body += text(28, footer, f'{len(snapshot["repositories"])} public repositories · forks excluded', 13, muted)
    body += text(28, footer+25, "Different counting scopes; these totals are not additive.", 12, muted)
    return svg(width, footer+46, "GitHub contributions, public commits, and pull requests", body, mode)


def language_mix(snapshot, counter, mode, compact=False):
    width, cols = (480, 2) if compact else (1000, 4)
    muted = "a7b3c2" if mode == "dark" else "526171"
    rows = sorted(((k, v) for k, v in counter.items() if v), key=lambda item: (-item[1], item[0]))
    if len(rows) > 7:
        rows = rows[:6] + [("Other", sum(v for _, v in rows[6:]))]
    total = sum(counter.values())
    assert sum(v for _, v in rows) == total
    shares = percentages([v for _, v in rows])
    body = text(28, 43, "Language mix", 26, bold=True)
    body += text(28, 72, f'Public code · forks excluded · {snapshot["date"]}', 13, muted)
    x = 28
    for i, ((language, value), share) in enumerate(zip(rows, shares)):
        color = COLORS.get(language, ("75818f", "526171"))[mode == "light"]
        bar_width = (width-56) * value / total
        body += f'<rect x="{x:.3f}" y="98" width="{bar_width:.3f}" height="24" fill="#{color}"><title>{escape(language)}: {value:,} bytes</title></rect>'
        x += bar_width
        lx, ly = 28 + (i % cols) * (width-56) / cols, 159 + (i // cols) * 55
        body += f'<rect x="{lx}" y="{ly-10}" width="9" height="9" rx="3" fill="#{color}"/>'
        body += text(lx+18, ly, language, 14)
        body += text(lx+18, ly+22, f"{share/10:.1f}%", 17, bold=True)
    if not total:
        body += text(28, 120, "No language data available yet.", 15, muted)
    footer = 390 if compact else 283
    body += text(28, footer, "Share of language bytes, not proficiency.", 13, muted)
    body += text(28, footer+22, "Larger repositories carry more weight.", 13, muted)
    return svg(width, footer+43, "Language share across public non-fork repositories", body, mode)


def main():
    snapshot = collect()
    months, primary, languages = summarize(snapshot)
    rendered = {}
    for mode in ("dark", "light"):
        for compact in (False, True):
            suffix = f'{"compact-" if compact else ""}{mode}.svg'
            rendered[f"activity-{suffix}"] = overview(snapshot, mode, compact)
            rendered[f"language-mix-{suffix}"] = language_mix(snapshot, languages, mode, compact)
    for image in rendered.values():
        ET.fromstring(image)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, image in rendered.items():
        (OUTPUT / filename).write_text(image)
    (OUTPUT / "snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f'Generated consistent charts for {snapshot["date"]}: {sum(months.values())} profile contributions, {sum(primary.values())} public non-fork repositories.')


if __name__ == "__main__":
    main()
