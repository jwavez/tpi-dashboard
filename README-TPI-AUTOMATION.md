# Daily TPI Discord Poster

This GitHub Action runs the TPI calculation every day and posts a PNG summary + login link to Discord.

## Setup

1. Put the updated `TPIindi.py` in the root of your GitHub repo (same repo as the Streamlit app).
2. Add this workflow file: `.github/workflows/tpi-daily.yml`
3. In your GitHub repo go to **Settings → Secrets and variables → Actions**.
4. Create a secret named `DISCORD_WEBHOOK` and paste your Discord webhook URL.
5. Push the files. The Action will run every day at 08:00 UTC.
6. You can also run it manually from the Actions tab → Daily TPI Discord Update → Run workflow.

## What it posts

- Current verdict, regime, and allocation
- The full TPI PNG dashboard
- A direct link to the Streamlit login page

No laptop needed. No manual run.
