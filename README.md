# HKTA Notifier — GitHub Actions setup

Runs in GitHub's cloud, every 30 minutes, forever. Free, no credit card,
no PC needed.

## What it does

Every 30 min, a GitHub-hosted VM polls **12 English-related subject pages**
on HKTA, merges the results, filters for postings paying **HK$350/hr or
higher**, dedupes against `seen.json` in the repo, and emails new matches
via Gmail SMTP.

### Categories monitored

- `english` — general English (all levels)
- `english-literature`
- `english-phonics`
- `english-oral`
- `preschool-english`
- `cambridge-english`
- `english-hl` (IB English HL)
- `english-literature-hl` / `english-literature-sl` (IB)
- `ielts`
- `toefl`
- `the-critical-reading-section` (SAT)

To add or remove categories, edit the `SUBJECTS` list near the top of
`hkta_notifier.py` and commit.

---

## One-time setup (~10 minutes)

### Step 1 — Create a GitHub account
If you don't have one: <https://github.com/signup>. Free account is fine.

### Step 2 — Create a new repository

1. Go to <https://github.com/new>.
2. Repository name: `hkta-notifier` (or whatever you want).
3. **Visibility: Public** is recommended (Actions minutes are unlimited for public repos).
4. Tick **"Add a README file"**.
5. Click **Create repository**.

### Step 3 — Upload these files

In the new repo:

1. Click **Add file → Upload files**.
2. Drag in `hkta_notifier.py`, `seen.json`, and this `README.md` (overwriting the one GitHub created).
3. Optional: `.gitignore` (your OS may hide it; not strictly needed).
4. Click **Commit changes**.

Then create the workflow file:

1. Click **Add file → Create new file**.
2. Filename: exactly `.github/workflows/hkta-notifier.yml`
   (the slashes create the folders).
3. Paste in the contents of `hkta-notifier.yml` from this package.
4. Click **Commit changes**.

### Step 4 — Add your secrets

1. In the repo: **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**. Add these three:

   | Name                  | Value                                          |
   |-----------------------|------------------------------------------------|
   | `GMAIL_USER`          | `official.ron.hk@gmail.com`                    |
   | `GMAIL_APP_PASSWORD`  | your 16-char app password — paste it only here, never into this README |
   | `TO_EMAIL`            | `official.ron.hk@gmail.com`                    |

3. (Optional) To change the fee threshold without editing code: switch to the **Variables** tab → add `MIN_FEE` = `350` (or any number).

### Step 5 — Enable Actions and trigger a first run

1. Go to the **Actions** tab. If asked, click the green button to enable workflows.
2. Click **HKTA Notifier** in the left sidebar.
3. Click **Run workflow → Run workflow** (top right).
4. After ~30 seconds, a run appears. Click it for logs.
5. The first run will report `~150 unique postings, ~46 match $350+/hr, new: 0` — that's expected (see below).

Done. It'll keep running every 30 min from now on.

---

## About the `seen.json` you uploaded

This file is **pre-populated with every currently-listed posting** (~150 IDs)
at the time the package was built. That's intentional — without it, the very
first run would email you ~46 old listings that have been sitting on the
site for weeks or months.

By starting "everything is seen", only *genuinely new* postings that appear
*after* deployment will trigger emails.

If you'd rather get the backlog flood once (to catch any old postings still
open that you want to reply to), just edit `seen.json` in the GitHub web
editor and replace its contents with `[]`, then commit. Next run will
email all current matches.

---

## About cost

- **Public repo**: Actions minutes are unlimited and free.
- **Private repo**: 2000 min/month free. At 30-min cadence (48 runs/day × 30 = 1440 min) you'd stay under, but barely. Public is safer.

Your secrets are encrypted by GitHub and never appear in logs. `seen.json`
is just a list of opaque job IDs.

---

## Day-to-day use

- **See what it's doing**: Actions tab → HKTA Notifier → click any run for logs.
- **Pause**: Actions tab → ⋯ menu (top right) → Disable workflow.
- **Resume**: same menu → Enable workflow.
- **Change fee threshold**: Settings → Variables → edit `MIN_FEE`.
- **Add/remove subject categories**: open `hkta_notifier.py` → edit the `SUBJECTS` list near the top → commit.
- **Reset and get all current matches once**: edit `seen.json` to `[]` → commit.

---

## Timing notes

- GitHub's cron is best-effort. Runs are sometimes delayed 5–15 min during peak load.
- A full run hits 12 URLs with a small polite delay between each — total runtime ~10–15 seconds. The workflow has a 5-min timeout.

---

## Rotating the Gmail password

If you ever revoke the app password:

1. Generate a new one at <https://myaccount.google.com/apppasswords>.
2. Repo → Settings → Secrets → click `GMAIL_APP_PASSWORD` → **Update**.

No code changes needed.
