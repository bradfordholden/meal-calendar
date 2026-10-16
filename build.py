#!/usr/bin/env python3
"""Build the meal calendar site from data/.

Reads data/recipes/<slug>.json and data/weeks/<YYYY-MM-DD>.json and writes:
  meals.ics          calendar feed (subscribe to this)
  index.html         this week's dinners
  r/<slug>/index.html  one page per recipe

Standard library only. Run: python3 build.py
"""
import datetime as dt
import html
import json
import pathlib
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE_URL = "https://bradfordholden.github.io/meal-calendar"
CAL_NAME = "Holden dinners"
TZ = ZoneInfo("America/New_York")
DINNER_AT = "17:30"
DINNER_MINUTES = 60
START_MINUTES = 15
KEEP_WEEKS = 8
UID_DOMAIN = "meal-calendar.bradfordholden.github.io"


def load(path):
    return json.loads(path.read_text())


def recipe_url(slug):
    return f"{SITE_URL}/r/{slug}/"


# ---------- calendar feed ----------

def ics_escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def ics_fold(line):
    """Fold a content line to 75 octets per RFC 5545."""
    out, cur = [], b""
    for ch in line:
        b = ch.encode()
        if len(cur) + len(b) > (75 if not out else 74):
            out.append(cur)
            cur = b""
        cur += b
    out.append(cur)
    return "\r\n ".join(part.decode() for part in out)


def utc(date_str, hhmm):
    local = dt.datetime.fromisoformat(f"{date_str}T{hhmm}").replace(tzinfo=TZ)
    return local.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def plus_minutes(hhmm, minutes):
    t = dt.datetime.strptime(hhmm, "%H:%M") + dt.timedelta(minutes=minutes)
    return t.strftime("%H:%M")


def event(uid, stamp, date_str, start, minutes, summary, description, url):
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{stamp}",
        f"DTSTART:{utc(date_str, start)}",
        f"DTEND:{utc(date_str, plus_minutes(start, minutes))}",
        f"SUMMARY:{ics_escape(summary)}",
        f"DESCRIPTION:{ics_escape(description)}",
        f"URL:{url}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]
    return lines


def build_ics(weeks, recipes):
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//bradfordholden//meal-calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{CAL_NAME}",
        "X-WR-TIMEZONE:America/New_York",
        "REFRESH-INTERVAL;VALUE=DURATION:PT4H",
        "X-PUBLISHED-TTL:PT4H",
    ]
    for week in weeks:
        for d in week["dinners"]:
            r = recipes[d["recipe"]]
            url = recipe_url(d["recipe"])
            desc = [f"Recipe: {url}"]
            if d.get("heads_up"):
                desc.append(d["heads_up"])
            times = " / ".join(x for x in (r.get("prep") and f"Prep {r['prep']}",
                                          r.get("cook") and f"Cook {r['cook']}") if x)
            if times:
                desc.append(times)
            if r.get("source"):
                desc.append(f"Original: {r['source']['url']}")
            lines += event(f"dinner-{d['date']}@{UID_DOMAIN}", stamp, d["date"],
                           d.get("time", DINNER_AT), DINNER_MINUTES,
                           f"Dinner: {r['title']}", "\n".join(desc), url)
            if d.get("start_at"):
                lines += event(f"start-{d['date']}@{UID_DOMAIN}", stamp, d["date"],
                               d["start_at"], START_MINUTES,
                               f"Start dinner: {r['title']}",
                               f"{d.get('heads_up', '')}\nRecipe: {url}".strip(), url)
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(l) for l in lines) + "\r\n"


# ---------- web pages ----------

CSS = """
:root{--bg:#fbfaf7;--fg:#1f1d1a;--muted:#6b665e;--card:#fff;--line:#e6e1d8;--accent:#b4532a}
@media (prefers-color-scheme:dark){:root{--bg:#171614;--fg:#ece8e1;--muted:#a39d93;--card:#211f1c;--line:#35322d;--accent:#e08a5f}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:680px;margin:0 auto;padding:24px 16px 48px}
a{color:var(--accent)}
h1{font-size:1.6rem;line-height:1.25;margin:0 0 8px}
h2{font-size:1.1rem;margin:28px 0 8px}
.meta{color:var(--muted);font-size:.92rem;margin:0 0 16px}
.photo{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:12px;display:block;background:var(--line)}
.credit{color:var(--muted);font-size:.8rem;margin:4px 0 0}
.nophoto{border:1px dashed var(--line);border-radius:12px;padding:28px;text-align:center;color:var(--muted)}
ul,ol{padding-left:1.3rem}li{margin:4px 0}
.changes{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px 16px}
.day{display:flex;gap:14px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:10px;margin:10px 0;text-decoration:none;color:inherit}
.day img,.day .ph{width:72px;height:72px;border-radius:8px;object-fit:cover;flex:none;background:var(--line)}
.day b{display:block}.day span{color:var(--muted);font-size:.9rem}
.tag{font-size:.75rem;text-transform:uppercase;letter-spacing:.04em;color:var(--accent)}
"""


def photo_src(slug, ph):
    """Web photos are shown from their own site; our own photos live in r/<slug>/."""
    return ph["url"] if ph["url"].startswith("http") else f"{SITE_URL}/r/{slug}/{ph['url']}"


def page(title, body):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style></head>
<body><main>{body}</main></body></html>
"""


def recipe_page(slug, r):
    e = html.escape
    parts = [f'<p class="meta"><a href="{SITE_URL}/">This week</a></p>']
    if r.get("photo"):
        ph = r["photo"]
        src = photo_src(slug, ph)
        parts.append(f'<img class="photo" src="{e(src)}" alt="{e(r["title"])}" referrerpolicy="no-referrer" onerror="this.style.visibility=&#39;hidden&#39;">')
        if ph.get("credit"):
            link = r.get("source", {}).get("url", "")
            parts.append(f'<p class="credit">Photo: <a href="{e(link)}">{e(ph["credit"])}</a></p>' if link
                         else f'<p class="credit">Photo: {e(ph["credit"])}</p>')
    else:
        parts.append('<div class="nophoto">No photo yet. Send one in the project thread.</div>')
    parts.append(f'<h1 style="margin-top:16px">{e(r["title"])}</h1>')
    meta = [f"{r['portions']} portions" if r.get("portions") else "",
            f"Prep {r['prep']}" if r.get("prep") else "",
            f"Cook {r['cook']}" if r.get("cook") else "",
            r.get("equipment", ""), r.get("protein", "")]
    parts.append(f'<p class="meta">{" · ".join(e(m) for m in meta if m)}</p>')
    if r.get("changes"):
        parts.append('<div class="changes"><b>Our changes</b><ul>'
                     + "".join(f"<li>{e(c)}</li>" for c in r["changes"]) + "</ul></div>")
    parts.append("<h2>Ingredients</h2><ul>" + "".join(f"<li>{e(i)}</li>" for i in r["ingredients"]) + "</ul>")
    parts.append("<h2>Steps</h2><ol>" + "".join(f"<li>{e(s)}</li>" for s in r["steps"]) + "</ol>")
    if r.get("source"):
        parts.append(f'<p class="meta">Adapted from <a href="{e(r["source"]["url"])}">{e(r["source"]["name"])}</a>.</p>')
    return page(r["title"], "\n".join(parts))


def index_page(week, recipes):
    e = html.escape
    start = dt.date.fromisoformat(week["week_start"])
    rows = []
    for d in week["dinners"]:
        r = recipes[d["recipe"]]
        day = dt.date.fromisoformat(d["date"]).strftime("%a %b %-d")
        img = (f'<img src="{e(photo_src(d["recipe"], r["photo"]))}" alt="" referrerpolicy="no-referrer" onerror="this.style.visibility=&#39;hidden&#39;">'
               if r.get("photo") else '<div class="ph"></div>')
        tag = "Favorite" if r.get("kind") == "favorite" else "New"
        rows.append(f'<a class="day" href="r/{d["recipe"]}/">{img}<div><span class="tag">{tag}</span>'
                    f'<b>{e(r["title"])}</b><span>{e(day)}</span></div></a>')
    feed = SITE_URL.replace("https://", "webcal://") + "/meals.ics"
    body = (f"<h1>Dinners, week of {start.strftime('%b %-d')}</h1>"
            f'<p class="meta">Fri and Sat: leftovers or out.</p>' + "".join(rows)
            + f'<h2>Add to your calendar</h2><p class="meta">Subscribe to <a href="{feed}">{SITE_URL}/meals.ics</a>. '
            "On Google Calendar: Other calendars, +, From URL.</p>")
    return page(f"Dinners, week of {start.strftime('%b %-d')}", body)


def main():
    recipes = {p.stem: load(p) for p in sorted((DATA / "recipes").glob("*.json"))}
    weeks = [load(p) for p in sorted((DATA / "weeks").glob("*.json"))]
    cutoff = dt.date.today() - dt.timedelta(weeks=KEEP_WEEKS)
    weeks = [w for w in weeks if dt.date.fromisoformat(w["week_start"]) >= cutoff]
    for w in weeks:
        for d in w["dinners"]:
            if d["recipe"] not in recipes:
                raise SystemExit(f"{w['week_start']}: unknown recipe {d['recipe']!r}")

    (ROOT / "meals.ics").write_text(build_ics(weeks, recipes), newline="")
    for slug, r in recipes.items():
        out = ROOT / "r" / slug
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.html").write_text(recipe_page(slug, r))
    if weeks:
        (ROOT / "index.html").write_text(index_page(weeks[-1], recipes))
    (ROOT / ".nojekyll").write_text("")
    n = sum(len(w["dinners"]) for w in weeks)
    print(f"Built {n} dinners across {len(weeks)} week(s), {len(recipes)} recipe pages.")


if __name__ == "__main__":
    main()
