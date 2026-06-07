#!/usr/bin/env python3
"""
HKTA tutor-posting notifier — GitHub Actions edition.

Runs once per invocation (the workflow schedules it every 30 min).
- Polls HKTA's subject-category pages for English-related work.
- Filters by minimum hourly fee.
- Dedupes against seen.json in the repo.
- Sends one email per batch of new matches via Gmail SMTP.

Environment variables required:
  GMAIL_USER          your Gmail address
  GMAIL_APP_PASSWORD  16-char Gmail app password
  TO_EMAIL            destination (usually same as GMAIL_USER)
  MIN_FEE             optional, default 350
"""
import json
import os
import re
import smtplib
import ssl
import sys
import time
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

# ─── HKTA English-related subject pages ──────────────────────────────────
# To add or remove categories, edit this list. The script polls each URL,
# merges + dedupes the postings, and applies the fee filter.
SUBJECTS = [
    "english",                    # general English (all levels)
    "english-literature",         # English Literature
    "english-phonics",            # Phonics
    "english-oral",               # Spoken / Oral English
    "preschool-english",          # Pre-K English
    "cambridge-english",          # Cambridge English exams
    "english-hl",                 # IB English HL
    "english-literature-hl",      # IB English Literature HL
    "english-literature-sl",      # IB English Literature SL
    "ielts",                      # IELTS exam prep
    "toefl",                      # TOEFL exam prep
    "the-critical-reading-section",  # SAT Critical Reading
]

URL_TEMPLATE = "https://www.hkta.edu.hk/en/jobcase/subject/{slug}"
UA   = "Mozilla/5.0 (compatible; HKTA-Personal-Notifier/1.0)"
SEEN = Path(__file__).resolve().parent / "seen.json"

JOB_RE = re.compile(
    r'<a href="/en/jobdetail/(?P<id>[A-Z]\d+)"[^>]*>(?P<title>[^<]+)</a>'
    r'(?P<body>.*?)'
    r'\$(?P<fee>\d+)\s*</div>\s*<div[^>]*>/</div>\s*<div[^>]*>(?P<unit>hr|\d+min|min)</div>',
    re.S,
)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")

def extract_after_icon(body, icon_name):
    m = re.search(rf'svg/{icon_name}[^"]*"[^>]*>\s*<div[^>]*>([^<]+)</div>', body)
    return m.group(1).strip() if m else ""

def parse(html, source_subject):
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
            "source_subject": source_subject,
        })
    return out

def collect_all():
    """Fetch every subject page, merge + dedupe by job ID, track which subject(s) each came from."""
    by_id = {}
    for slug in SUBJECTS:
        url = URL_TEMPLATE.format(slug=slug)
        try:
            html = fetch(url)
        except (urllib.error.URLError, TimeoutError) as e:
            print(f"  WARN: failed to fetch {slug}: {e}", file=sys.stderr)
            continue
        posts = parse(html, slug)
        for p in posts:
            if p["id"] in by_id:
                by_id[p["id"]]["source_subject"] += f", {slug}"
            else:
                by_id[p["id"]] = p
        time.sleep(0.4)  # polite spacing between requests
    return list(by_id.values())

def matches(p, min_fee):
    """Only hourly pricing, at or above the threshold. Subject is already English-related by construction."""
    return p["unit"] == "hr" and p["fee"] >= min_fee

def render_body(new_matches):
    lines = []
    for p in new_matches:
        lines += [
            f"• {p['title']}  —  ${p['fee']}/{p['unit']}",
            f"  Category:      {p['source_subject']}",
            f"  Location:      {p['location']}",
            f"  Schedule:      {p['schedule']}",
            f"  Tutor wanted:  {p['qualification']}",
            f"  Link:          {p['url']}",
            "",
        ]
    lines.append("— HKTA Notifier (GitHub Actions)")
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
    to_addr  = os.environ.get("TO_EMAIL", user).strip()
    min_fee  = int(os.environ.get("MIN_FEE", "350"))

    if not user or not password:
        print("ERROR: GMAIL_USER and GMAIL_APP_PASSWORD env vars must be set.", file=sys.stderr)
        sys.exit(1)

    posts = collect_all()
    hits  = [p for p in posts if matches(p, min_fee)]

    seen = set()
    if SEEN.exists():
        try: seen = set(json.loads(SEEN.read_text(encoding="utf-8")))
        except Exception: pass

    new = [p for p in hits if p["id"] not in seen]
    print(f"Subjects polled: {len(SUBJECTS)} | Unique postings: {len(posts)} | "
          f">= ${min_fee}/hr: {len(hits)} | new: {len(new)}")

    if not new:
        return

    subj = f"HKTA: {len(new)} new English posting{'s' if len(new) != 1 else ''} (${min_fee}+/hr)"
    body = render_body(new)

    send_email(user, password, to_addr, subj, body)
    print(f"Emailed {len(new)} new posting(s) to {to_addr}.")

    seen.update(p["id"] for p in hits)
    seen_list = sorted(seen)[-2000:]  # cap to last 2000 IDs
    SEEN.write_text(json.dumps(seen_list, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
