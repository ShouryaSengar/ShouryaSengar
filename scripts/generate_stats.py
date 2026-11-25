"""Generate themed SVG stat cards from the GitHub GraphQL API (stdlib only).

Env:
  GH_TOKEN   classic PAT (repo + read:user) -> includes private contributions
  GH_USER    GitHub username (default: ShouryaSengar)
  MOCK=1     use fake data (for local preview)
"""
import json, os, random, time, urllib.request, html
from datetime import date, datetime, timedelta, timezone

USER = os.environ.get("GH_USER", "ShouryaSengar")
TOKEN = os.environ.get("GH_TOKEN", "")
OUT = os.path.join(os.path.dirname(__file__), "..", "assets")

QUERY = """
query($login:String!){ user(login:$login){
  followers{ totalCount }
  contributionsCollection{
    totalCommitContributions totalIssueContributions
    totalPullRequestContributions totalPullRequestReviewContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } }
  }
  repositories(ownerAffiliations:OWNER, isFork:false, first:100){
    totalCount
    nodes{ stargazerCount languages(first:6, orderBy:{field:SIZE, direction:DESC}){ edges{ size node{ name color } } } }
  }
}}"""

def fetch():
    if not TOKEN:
        raise SystemExit("GH_TOKEN is not set. Set it (or use MOCK=1 for a local preview only).")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json"},
    )
    last = None
    for attempt in range(3):  # transient API errors should not leave the cards stale
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            break
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    else:
        raise SystemExit(f"GitHub API request failed: {last}")
    if "errors" in data or not data.get("data", {}).get("user"):
        raise SystemExit(data.get("errors") or "user not found")
    return data["data"]["user"]

def mock():
    random.seed(7)
    start = date.today() - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    weeks, d = [], start
    while d <= date.today():
        days = []
        for _ in range(7):
            if d <= date.today():
                n = 0 if random.random() < .35 else random.choice([1, 1, 2, 3, 4, 6, 9, 14])
                days.append({"date": d.isoformat(), "contributionCount": n})
            d += timedelta(days=1)
        weeks.append({"contributionDays": days})
    total = sum(x["contributionCount"] for w in weeks for x in w["contributionDays"])
    langs = [("TypeScript", 52, "#3178c6"), ("JavaScript", 24, "#f1e05a"), ("CSS", 9, "#563d7c"),
             ("HTML", 7, "#e34c26"), ("C++", 5, "#f34b7d"), ("Python", 3, "#3572A5")]
    return {
        "followers": {"totalCount": 12},
        "contributionsCollection": {
            "totalCommitContributions": 812, "totalIssueContributions": 14,
            "totalPullRequestContributions": 96, "totalPullRequestReviewContributions": 31,
            "contributionCalendar": {"totalContributions": total, "weeks": weeks}},
        "repositories": {"totalCount": 24, "nodes": [{"stargazerCount": 9, "languages": {"edges": [
            {"size": s * 1000, "node": {"name": n, "color": c}} for n, s, c in langs]}}]},
    }

def esc(s): return html.escape(str(s))
def fmt(n): return f"{n:,}"
FONT = "'Segoe UI',Ubuntu,Arial,sans-serif"
MONO = "'JetBrains Mono','SFMono-Regular',Consolas,monospace"
STAMP = datetime.now(timezone.utc).strftime("%d %b %Y")

def streaks(days):
    counts = [d["contributionCount"] for d in days]
    longest = cur = 0
    for c in counts:
        cur = cur + 1 if c > 0 else 0
        longest = max(longest, cur)
    cur, i = 0, len(counts) - 1
    if i >= 0 and counts[i] == 0: i -= 1  # today may not be done yet
    while i >= 0 and counts[i] > 0:
        cur += 1; i -= 1
    return cur, longest

def frame(w, h, body, extra_css=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b1220"/><stop offset="1" stop-color="#111a2e"/></linearGradient>
<linearGradient id="bd" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#22d3ee"/><stop offset=".5" stop-color="#6366f1"/><stop offset="1" stop-color="#ec4899"/>
<animateTransform attributeName="gradientTransform" type="rotate" from="0 .5 .5" to="360 .5 .5" dur="8s" repeatCount="indefinite"/></linearGradient>
</defs>
<style>
text{{font-family:{FONT}}}
.mono{{font-family:{MONO}}}
.title{{font-size:15px;font-weight:700;fill:#f8fafc}}
.sub{{font-size:11px;fill:#94a3b8}}
.fade{{animation:fade .7s ease backwards}}
@keyframes fade{{from{{opacity:0;transform:translateY(6px)}}}}
{extra_css}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<rect x=".8" y=".8" width="{w-1.6}" height="{h-1.6}" rx="16" fill="url(#bg)"/>
<rect x=".8" y=".8" width="{w-1.6}" height="{h-1.6}" rx="16" fill="none" stroke="url(#bd)" stroke-width="1.4"/>
{body}
</svg>'''

def contributions_svg(cal):
    W, H = 900, 250
    cell, gap, x0, y0 = 12, 3, 52, 78
    weeks = cal["weeks"]
    allc = sorted(d["contributionCount"] for w in weeks for d in w["contributionDays"] if d["contributionCount"] > 0)
    q = [allc[int(len(allc) * p)] if allc else 1 for p in (.25, .5, .75)]
    colors = ["#131c2e", "#0e7490", "#06b6d4", "#22d3ee", "#a5f3fc"]
    def lvl(n):
        if n == 0: return 0
        return 1 if n <= q[0] else 2 if n <= q[1] else 3 if n <= q[2] else 4
    rects, months, last_m, month_marks = [], [], None, []
    for wi, w in enumerate(weeks):
        for d in w["contributionDays"]:
            dt = date.fromisoformat(d["date"]); row = (dt.weekday() + 1) % 7
            x = x0 + wi * (cell + gap); y = y0 + row * (cell + gap)
            L = lvl(d["contributionCount"])
            rects.append(f'<rect class="c" x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" fill="{colors[L]}" style="animation-delay:{wi*0.025:.2f}s"><title>{d["contributionCount"]} contributions on {d["date"]}</title></rect>')
        first = date.fromisoformat(w["contributionDays"][0]["date"])
        if first.month != last_m and wi < len(weeks) - 2:
            month_marks.append((wi, first.strftime("%b")))
            last_m = first.month
    # a label needs about 3 columns of room: when two collide, keep the later one (the first column is often a stub week)
    for i, (wi, name) in enumerate(month_marks):
        if i + 1 < len(month_marks) and month_marks[i + 1][0] - wi < 3:
            continue
        months.append(f'<text x="{x0 + wi*(cell+gap)}" y="{y0-10}" class="sub mono">{name}</text>')
    labels = "".join(f'<text x="{x0-10}" y="{y0 + r*(cell+gap) + 10}" text-anchor="end" class="sub mono">{n}</text>' for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))
    legend_x = W - 24 - 5 * 17 - 70
    legend = f'<text x="{legend_x}" y="{H-20}" class="sub mono" text-anchor="end">Less</text>' + "".join(
        f'<rect x="{legend_x+8+i*17}" y="{H-30}" width="12" height="12" rx="3" fill="{c}"/>' for i, c in enumerate(colors)) + \
        f'<text x="{legend_x+8+5*17+4}" y="{H-20}" class="sub mono">More</text>'
    total = cal["totalContributions"]
    body = f'''<g class="fade">
<circle cx="30" cy="34" r="5" fill="#22d3ee" class="pulse"/>
<text x="46" y="39" class="title">Contribution activity</text>
<text x="{W-24}" y="39" text-anchor="end" class="sub mono">{fmt(total)} contributions in the last year · public + private</text>
</g>
{labels}{months}{"".join(rects)}{legend}
<text x="24" y="{H-20}" class="sub mono">updated {STAMP}</text>'''
    return frame(W, H, body, ".c{animation:pop .5s ease backwards}@keyframes pop{from{opacity:0;transform:scale(.4)}}.c{transform-box:fill-box;transform-origin:center}.pulse{animation:pl 2.4s ease-in-out infinite}@keyframes pl{50%{opacity:.35}}")

def stats_svg(u):
    cc = u["contributionsCollection"]; days = [d for w in cc["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    cur, longest = streaks(days)
    stars = sum(r["stargazerCount"] for r in u["repositories"]["nodes"])
    extra = cc["totalPullRequestContributions"] + cc["totalPullRequestReviewContributions"] + cc["totalIssueContributions"]
    top = top_languages(u, 1)
    top_name, top_pct = (top[0][0], f"{top[0][2]:.0f}% of code") if top else ("n/a", "")
    tiles = [("⚡", "Contributions", fmt(cc["contributionCalendar"]["totalContributions"]), "last 12 months", "#22d3ee"),
             ("🔨", "Commits", fmt(cc["totalCommitContributions"]), f"+{fmt(extra)} PRs, reviews, issues" if extra else "last 12 months", "#6366f1"),
             ("🧠", "Top language", esc(top_name), top_pct, "#a78bfa"),
             ("🔥", "Current streak", f"{cur}d", f"longest {longest}d", "#f59e0b"),
             ("📦", "Repositories", fmt(u["repositories"]["totalCount"]), f"{fmt(stars)} stars", "#ec4899")]
    W, tw, gap, H = 900, 168, 15, 120
    g = ""
    for i, (ic, t, v, s, c) in enumerate(tiles):
        x = i * (tw + gap)
        g += f'''<g transform="translate({x},0)"><g class="fade" style="animation-delay:{i*.12:.2f}s">
<rect width="{tw}" height="{H-2}" y="1" rx="14" fill="#0b1220" stroke="{c}" stroke-opacity=".5"/>
<rect width="{tw}" height="{H-2}" y="1" rx="14" fill="url(#g{i})"/>
<text x="16" y="30" font-size="16">{ic}</text><text x="40" y="29" class="sub">{t}</text>
<text x="16" y="72" class="big mono" style="font-size:{30 if len(v) <= 6 else 20}px">{v}</text>
<text x="16" y="98" class="sub mono">{s}</text></g></g>'''
    defs = "".join(f'<linearGradient id="g{i}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{c}" stop-opacity=".18"/><stop offset="1" stop-color="{c}" stop-opacity="0"/></linearGradient>' for i, (*_, c) in enumerate(tiles))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"><defs>{defs}</defs>
<style>text{{font-family:{FONT}}}.mono{{font-family:{MONO}}}.sub{{font-size:11px;fill:#94a3b8}}.big{{font-size:30px;font-weight:700;fill:#f8fafc}}
.fade{{animation:fade .7s ease backwards}}@keyframes fade{{from{{opacity:0;transform:translateY(8px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}</style>{g}</svg>'''

def top_languages(u, n=6):
    """[(name, color, percent)] by code size, largest first."""
    tot = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]; t = tot.setdefault(name, [0, e["node"]["color"] or "#64748b"]); t[0] += e["size"]
    items = sorted(tot.items(), key=lambda kv: -kv[1][0])[:6]  # same top 6 the language bar shows
    s = sum(v[0] for _, v in items) or 1
    return [(name, v[1], v[0] * 100 / s) for name, v in items][:n]

def langs_svg(u):
    tot = {}
    for r in u["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]; t = tot.setdefault(n, [0, e["node"]["color"] or "#64748b"]); t[0] += e["size"]
    items = sorted(tot.items(), key=lambda kv: -kv[1][0])[:6]
    s = sum(v[0] for _, v in items) or 1
    W, H, bx, bw = 900, 170, 24, 852
    bars, x, legend = "", bx, ""
    for i, (n, (sz, c)) in enumerate(items):
        w = bw * sz / s
        bars += f'<rect class="seg" x="{x:.1f}" y="62" width="{max(w-2,2):.1f}" height="14" rx="4" fill="{c}" style="animation-delay:{i*.12:.2f}s"/>'
        x += w
        col, row = i % 3, i // 3
        lx, ly = 24 + col * 290, 108 + row * 28
        legend += f'<g class="fade" style="animation-delay:{.4+i*.08:.2f}s"><circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{c}"/><text x="{lx+18}" y="{ly}" class="lg">{esc(n)}</text><text x="{lx+270}" y="{ly}" text-anchor="end" class="sub mono">{sz*100/s:.1f}%</text></g>'
    body = f'''<g class="fade"><circle cx="30" cy="34" r="5" fill="#a78bfa"/><text x="46" y="39" class="title">Most used languages</text>
<text x="{W-24}" y="39" text-anchor="end" class="sub mono">by code size across my repos</text></g>{bars}{legend}'''
    return frame(W, H, body, ".lg{font-size:13px;fill:#e2e8f0}.seg{transform-box:fill-box;transform-origin:left;animation:grow .9s ease backwards}@keyframes grow{from{transform:scaleX(0)}}")

def main():
    u = mock() if os.environ.get("MOCK") else fetch()
    cal = u["contributionsCollection"]["contributionCalendar"]
    for name, svg in (("contributions.svg", contributions_svg(cal)), ("stats.svg", stats_svg(u)), ("languages.svg", langs_svg(u))):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f: f.write(svg)
    print("generated", USER)

if __name__ == "__main__":
    main()
