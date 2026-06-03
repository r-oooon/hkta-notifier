#!/usr/bin/env python3
"""
HKTA tutor-posting notifier — GitHub Actions edition.

Runs once per invocation (the workflow schedules it every 15 min).
- Reads credentials from environment variables (set as GitHub Secrets).
- Reads/writes seen.json in the repo root for dedup across runs.
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
import urllib.error
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

URL  = "https://www.hkta.edu.hk/en/jobcase"
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

def matches(p, min_fee):
    if p["unit"] != "hr":               return False
    if p["fee"]  < min_fee:             return False
    if not re.search(r'\benglish\b', p["title"], re.I): return False
    return True

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

    try:
        html = fetch(URL)
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"Fetch failed: {e}", file=sys.stderr)
        sys.exit(0)  # non-fatal — try again next run

    posts = parse(html)
    hits  = [p for p in posts if matches(p, min_fee)]

    seen = set()
    if SEEN.exists():
        try: seen = set(json.loads(SEEN.read_text(encoding="utf-8")))
        except Exception: pass

    new = [p for p in hits if p["id"] not in seen]
    print(f"Parsed {len(posts)} | meets criteria: {len(hits)} | new: {len(new)}")

    if not new:
        return

    subj = f"HKTA: {len(new)} new English posting{'s' if len(new) != 1 else ''} (${min_fee}+/hr)"
    body = render_body(new)

    send_email(user, password, to_addr, subj, body)
    print(f"Emailed {len(new)} new posting(s) to {to_addr}.")

    seen.update(p["id"] for p in hits)
    seen_list = sorted(seen)[-1000:]
    SEEN.write_text(json.dumps(seen_list, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
