#!/usr/bin/env python3
"""
HKTA tutor-posting notifier for Toby — GitHub Actions edition.

Runs once per invocation (the workflow schedules it every 30 min).
- Polls HKTA's "Latest case" feed (all subjects).
- Filters: student level K1–P6 (local, UK and US labels), located on
  Hong Kong Island, hourly fee >= MIN_FEE.
- Dedupes against seen_toby.json in the repo.
- Sends one email per batch of new matches via Gmail SMTP.

Why this script polls the generic latest-case feed instead of HKTA's own
grade/district filter pages: those pages are NOT filtered server-side
(they return the same generic list with only the page title changed —
the real filtering happens client-side after login). Subject pages like
/jobcase/subject/english ARE filtered, which is why the original English
notifier uses them; but there is no working grade or district page, so
this script filters locally instead.

Environment variables required:
  GMAIL_USER          sending Gmail address
  GMAIL_APP_PASSWORD  16-char Gmail app password
  TO_EMAIL_TOBY       destination address
  MIN_FEE_TOBY        optional, default 250
"""
import json
import os
import re
import smtplib
import ssl
import sys
from email.mime.text import MIMEText
from pathlib import Path

FEED_URL = "https://www.hkta.edu.hk/en/jobcase"
UA   = "Mozilla/5.0 (compatible; HKTA-Personal-Notifier/1.0)"
SEEN = Path(__file__).resolve().parent / "seen_toby.json"

# ─── Grade filter: K1 to P6, any school system ───────────────────────────
# Job titles look like "Primary 2,English" or "K2,preschool chinese",
# sometimes several pairs joined by "|" ("Form 2,All Subjects|Primary 5,...").
# The part before the first comma of each pair is the grade label.
GRADE_RES = [
    re.compile(r"^k[1-3]$", re.I),                       # K1, K2, K3
    re.compile(r"^primary( [1-6])?$", re.I),             # Primary 1–6 / bare "Primary"
    re.compile(r"^p[1-6]$", re.I),                       # P1–P6 shorthand
    re.compile(r"^year [1-6]$", re.I),                   # UK Year 1–6
    re.compile(r"^grade [1-6]$", re.I),                  # US Grade 1–6
    re.compile(r"^(reception|pre[- ]?school|kindergarten|preschool)$", re.I),
]

# ─── Hong Kong Island areas (HKTA's own area list, incl. legacy combos) ──
HK_ISLAND_AREAS = {
    "mid-levels", "pok fu lam", "central and sheung wan", "central",
    "sheung wan", "sai wan", "wan chai", "causeway bay", "happy valley",
    "north point", "quarry bay", "tai koo", "shau kei wan", "sai wan ho",
    "chai wan", "siu sai wan", "aberdeen", "ap lei chau", "stanley",
    # legacy combined names still used on some postings
    "quarry bay and tai koo", "shau kei wan and sai wan ho",
    "chai wan and siu sai wan",
    "mid-levels central, pokfulam, central, sheung wan and western district",
}

JOB_RE = re.compile(
    r'<a href="/en/jobdetail/(?P<id>[A-Z]\d+)"[^>]*>(?P<title>[^<]+)</a>'
    r'(?P<body>.*?)'
    r'\$(?P<fee>\d+)\s*</div>\s*<div[^>]*>/</div>\s*<div[^>]*>(?P<unit>hr|\d+min|min)</div>',
    re.S,
)

def fetch(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def extract_after_icon(body, icon_name):
    m = re.search(rf'svg/{icon_name}[^"]*"[^>]*>\s*<div[^>]*>([^<]+)</div>', body)
    return m.group(1).strip() if m else ""

def parse(html):
    out = []
    for m in JOB_RE.finditer(html):
        jid = m.group("id")
        out.append({
            "id":    jid,
            "title": m.group("title").strip(),
            "url":   f"https://www.hkta.edu.hk/en/jobdetail/{jid}",
            "location":      extract_after_icon(m.group("body"), "dizhi"),
            "schedule":      extract_after_icon(m.group("body"), "Isolation_Mode"),
            "qualification": extract_after_icon(m.group("body"), "hat"),
            "fee":  int(m.group("fee")),
            "unit": m.group("unit"),
        })
    return out

def grade_matches(title):
    """True if any 'Grade,Subject' pair in the title has a K1–P6 grade label."""
    for pair in title.split("|"):
        grade = pair.split(",", 1)[0].strip()
        # strip trailing Chinese/bracket annotations e.g. "Form 1,English(升中一)"
        grade = re.sub(r"[（(].*$", "", grade).strip()
        if any(rx.match(grade) for rx in GRADE_RES):
            return True
    return False

def area_of(location):
    """Location text looks like '1 to 1 tutoring-Tai Koo' → 'tai koo'."""
    return location.rsplit("-", 1)[-1].strip().lower() if location else ""

def matches(p, min_fee):
    return (
        p["unit"] == "hr"
        and p["fee"] >= min_fee
        and grade_matches(p["title"])
        and area_of(p["location"]) in HK_ISLAND_AREAS
    )

def render_body(new_matches):
    lines = []
    for p in new_matches:
        lines += [
            f"• {p['title']}  —  ${p['fee']}/{p['unit']}",
            f"  Location:      {p['location']}",
            f"  Schedule:      {p['schedule']}",
            f"  Tutor wanted:  {p['qualification']}",
            f"  Link:          {p['url']}",
            "",
        ]
    lines.append("— HKTA Notifier for Toby (GitHub Actions)")
    return "\n".join(lines)

def send_email(user, password, to_addr, subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"]    = user
    msg["To"]      = to_addr
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as s:
        s.login(user, password.replace(" ", ""))
        s.send_message(msg)

def main():
    user     = os.environ.get("GMAIL_USER", "").strip()
    password = os.environ.get("GMAIL_APP_PASSWORD", "").strip()
    to_addr  = os.environ.get("TO_EMAIL_TOBY", "").strip()
    min_fee  = int(os.environ.get("MIN_FEE_TOBY", "250"))

    if not user or not password or not to_addr:
        print("ERROR: GMAIL_USER, GMAIL_APP_PASSWORD and TO_EMAIL_TOBY env vars must be set.",
              file=sys.stderr)
        sys.exit(1)

    posts = parse(fetch(FEED_URL))
    hits  = [p for p in posts if matches(p, min_fee)]

    seen = set()
    if SEEN.exists():
        try: seen = set(json.loads(SEEN.read_text(encoding="utf-8")))
        except Exception: pass

    new = [p for p in hits if p["id"] not in seen]
    print(f"Postings on feed: {len(posts)} | K1–P6 + HK Island + >= ${min_fee}/hr: {len(hits)} | new: {len(new)}")

    if not new:
        return

    subj = (f"HKTA: {len(new)} new K1–P6 posting{'s' if len(new) != 1 else ''} "
            f"on HK Island (${min_fee}+/hr)")
    send_email(user, password, to_addr, subj, render_body(new))
    print(f"Emailed {len(new)} new posting(s) to {to_addr}.")

    seen.update(p["id"] for p in hits)
    seen_list = sorted(seen)[-2000:]  # cap to last 2000 IDs
    SEEN.write_text(json.dumps(seen_list, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
