"""Refresh the README charts from public GitHub data. Run from any directory."""

from collections import Counter
from datetime import date, datetime
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

USER = "RishiiShah"
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "stats"
COLORS = {
    "TypeScript": ("79b8ff", "005a9c"), "Python": ("f2c861", "806000"),
    "JavaScript": ("ff9f68", "a54700"), "HTML": ("f1a1c7", "9f2366"),
    "Jupyter Notebook": ("c7a4ff", "7040a0"), "CSS": ("6bd4c8", "006e66"),
    "Java": ("ff8989", "a52d34"), "C++": ("a3d68a", "397722"),
    "Dart": ("7ad7ee", "006b80"), "C": ("7ad7ee", "006b80"), "Shell": ("a1b7d1", "455d7b"),
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
            "contributions": days, "repositories": repositories}


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


def top_rows(counter):
    rows = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    if len(rows) > 8:
        rows = rows[:7] + [("Other", sum(value for _, value in rows[7:]))]
    assert sum(value for _, value in rows) == sum(counter.values())
    return rows


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
    bg, ink, border = ("0e1116", "f0f6fc", "687a90") if dark else ("f6f7f8", "1f2937", "7a8797")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title" fill="#{ink}">'
            f'<title id="title">{escape(title)}</title><style>text{{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Arial,sans-serif}}</style>'
            f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="12" fill="#{bg}" stroke="#{border}"/>{body}</svg>')


def overview(snapshot, months, mode, compact=False):
    accent, teal, muted = ("ffad8f", "57d3d5", "b5c2d0") if mode == "dark" else ("9c3a20", "087780", "4b596b")
    year = snapshot["date"][:4]
    total = sum(months.values())
    width = 480 if compact else 1000
    baseline = 278 if compact else 298
    body = text(28, 40, "Rishi / GitHub activity", 22 if compact else 24, accent, bold=True)
    body += text(28, 66, f'{snapshot["start"]} to {snapshot["date"]} · year to date', 14, muted)
    if not compact:
        body += text(970, 40, f'Updated {snapshot["date"]}', 13, muted, end=True)
    body += text(28, 112, f"{total:,}", 30, bold=True) + text(28, 138, f"profile contributions in {year}", 15)
    body += text(245 if compact else 470, 112, len(snapshot["repositories"]), 30, bold=True) + text(245 if compact else 470, 138, "public original repos" if compact else "public repositories, excluding forks", 14 if compact else 15)
    body += text(28, 173, "Profile contributions by month" if compact else "Monthly profile contributions: commits, pull requests, issues, and reviews", 14, muted)
    maximum = max(months.values(), default=0) or 1
    step = (width - 56) / len(months)
    for index, (month, count) in enumerate(months.items()):
        x = 28 + index * step + 8
        bar_width = step - 16
        height = count / maximum * 92
        body += f'<rect x="{x:.1f}" y="{baseline-height:.1f}" width="{bar_width:.1f}" height="{height:.1f}" rx="3" fill="#{teal}"/>'
        body += text(round(x), round(baseline-7-height), count, 13)
        body += text(round(x), 300 if compact else 322, date.fromisoformat(month + "-01").strftime("%b"), 14, muted)
    if compact:
        body += text(452, 327, f'Updated {snapshot["date"]}', 12, muted, end=True)
    return svg(width, 340, f"Rishi's {year} profile contributions and public repository count", body, mode)


def language_chart(snapshot, counter, by_bytes, mode):
    title = "Language share of code" if by_bytes else "Repositories by main language"
    accent, muted = ("ffad8f", "b5c2d0") if mode == "dark" else ("9c3a20", "4b596b")
    rows = top_rows(counter)
    total = sum(counter.values())
    shares = percentages([value for _, value in rows])
    body = text(22, 36, title, 21, accent, bold=True)
    body += text(22, 61, f'{len(snapshot["repositories"])} public repositories · forks excluded', 13, muted)
    body += text(22, 82, "By GitHub language bytes" if by_bytes else "One primary language per repository", 13, muted)
    if not total:
        body += text(22, 130, "No language data available yet.")
    for index, ((language, value), share) in enumerate(zip(rows, shares)):
        y = 118 + index * 31
        color = COLORS.get(language, ("b8c2cc", "596470"))[mode == "light"]
        body += text(22, y, language, 16)
        bar_width = value / total * 205 if total else 0
        body += f'<rect x="185" y="{y-12}" width="{bar_width:.2f}" height="14" rx="3" fill="#{color}"><title>{escape(language)}: {value:,} {"bytes" if by_bytes else "repositories"}</title></rect>'
        label = f"{share/10:.1f}%" if by_bytes else str(value)
        body += text(456, y, label, 16, end=True)
    if by_bytes:
        body += text(22, 374, f"{total:,} language bytes · shares total 100%", 12, muted)
    else:
        body += text(22, 374, f"Counts total {total} repositories", 12, muted)
    body += text(22, 395, f'Updated {snapshot["date"]}', 12, muted)
    return svg(480, 415, title, body, mode)


def main():
    snapshot = collect()
    months, primary, languages = summarize(snapshot)
    rendered = {}
    for mode in ("dark", "light"):
        rendered[f"activity-{mode}.svg"] = overview(snapshot, months, mode)
        rendered[f"activity-compact-{mode}.svg"] = overview(snapshot, months, mode, compact=True)
        rendered[f"languages-repos-{mode}.svg"] = language_chart(snapshot, primary, False, mode)
        rendered[f"languages-bytes-{mode}.svg"] = language_chart(snapshot, languages, True, mode)
    for image in rendered.values():
        ET.fromstring(image)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for filename, image in rendered.items():
        (OUTPUT / filename).write_text(image)
    (OUTPUT / "snapshot.json").write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f'Generated consistent charts for {snapshot["date"]}: {sum(months.values())} profile contributions, {sum(primary.values())} public non-fork repositories.')


if __name__ == "__main__":
    main()
