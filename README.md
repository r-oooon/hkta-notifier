# HKTA Notifier — GitHub Actions setup

Runs in GitHub's cloud, every 15 minutes, forever. Free, no credit card,
no PC needed.

## What it does

1. Every 15 min, GitHub spins up a tiny Linux VM.
2. The VM runs `hkta_notifier.py`, which fetches the HKTA latest-cases page.
3. Filters for English postings at HK$350/hr or higher.
4. Sends you one email per new posting (dedup'd against `seen.json` in the repo).
5. Commits the updated `seen.json` back so the next run remembers what's seen.

---

## One-time setup (~10 minutes)

### Step 1 — Create a GitHub account
If you don't have one: <https://github.com/signup>. Free account is fine.

### Step 2 — Create a new repository

1. Go to <https://github.com/new>.
2. Repository name: `hkta-notifier` (or whatever you want).
3. **Visibility: Public** is recommended (see "About cost" below). Private also works but eats your free Actions minutes.
4. Tick **"Add a README file"**.
5. Click **Create repository**.

### Step 3 — Upload these files

In the new repo:

1. Click **Add file → Upload files**.
2. Drag in **all four files from this folder**:
   - `hkta_notifier.py`
   - `seen.json`
   - `.gitignore`
   - `README.md` (this file, overwriting the one GitHub created)
3. **Don't drag in `config.json`** — your password lives in Secrets instead.
4. At the bottom, click **Commit changes**.

Then upload the workflow file:

1. Click **Add file → Create new file**.
2. In the filename box type exactly: `.github/workflows/hkta-notifier.yml`
   (the slashes create the folders)
3. Paste in the contents of `hkta-notifier.yml` from this package.
4. Click **Commit changes**.

### Step 4 — Add your secrets

1. In the repo, go to **Settings → Secrets and variables → Actions**.
2. Click **New repository secret**. Add these three, one at a time:

   | Name                  | Value                                          |
   |-----------------------|------------------------------------------------|
   | `GMAIL_USER`          | `official.ron.hk@gmail.com`                    |
   | `GMAIL_APP_PASSWORD`  | `llmw gkee wvhy pzzx`                          |
   | `TO_EMAIL`            | `official.ron.hk@gmail.com`                    |

3. (Optional) To change the fee threshold without editing code: same page, switch to the **Variables** tab, add a variable named `MIN_FEE` with value `350` (or whatever you want).

### Step 5 — Enable Actions and trigger a first run

1. Go to the **Actions** tab. If GitHub asks to enable workflows, click the green button.
2. In the left sidebar, click **HKTA Notifier**.
3. Click **Run workflow → Run workflow** (top right). This triggers an immediate run instead of waiting for the next 15-min slot.
4. After ~30 seconds, a run appears in the list. Click it to see the logs.
5. You should see a line like `Parsed 20 | meets criteria: 1 | new: 1` and `Emailed 1 new posting(s)…`. Check your inbox.

You're done. It'll keep running every 15 min from now on.

---

## About cost

- **Public repo**: GitHub Actions minutes are **unlimited and free**. This is why we recommend public.
- **Private repo**: 2000 min/month free. 96 runs/day × 30 days × ~1 min billed = ~2900 min, which exceeds free. You'd either pay (~$8/mo) or drop cadence to every 30 min.

Your **secrets are never visible in a public repo** — they're stored encrypted by GitHub and only injected into the workflow's environment at run time. The `seen.json` file is public (just a list of opaque job IDs — not sensitive).

---

## Day-to-day use

- **See what it's doing**: Actions tab → HKTA Notifier → click any run for logs.
- **Pause it**: Actions tab → HKTA Notifier → ⋯ menu (top right) → Disable workflow.
- **Resume**: same menu → Enable workflow.
- **Change criteria**: edit `hkta_notifier.py` in GitHub's web editor (line ~63, the `matches()` function), commit. Next run picks it up.
- **Change fee threshold**: Settings → Variables → edit `MIN_FEE`.
- **Forget all seen postings and re-notify**: edit `seen.json` in GitHub's web editor, replace contents with `[]`, commit.

---

## Timing notes

- GitHub's `*/15 * * * *` schedule is **best-effort**. Runs are sometimes delayed 5–15 min during peak load. Don't expect second-level precision.
- The workflow has a 5-min timeout — plenty for our ~10-sec script.

---

## Rotating the Gmail password

If you ever revoke the app password:

1. Generate a new one at <https://myaccount.google.com/apppasswords>.
2. In the repo: Settings → Secrets → click `GMAIL_APP_PASSWORD` → **Update**.

Done. No code changes needed.
