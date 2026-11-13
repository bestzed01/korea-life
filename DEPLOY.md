# Deploying KOREA-LIFE to Railway — step by step

No command line required. Two phases: put the code on GitHub, then deploy on Railway.

---

## Phase 1 — Put the project on GitHub (web, no git needed)

1. Go to **https://github.com** and sign in (create a free account if needed).
2. Click the **+** (top right) → **New repository**.
3. Name it `korea-life`. Leave it **Public** or **Private** (either works). Do **not**
   add a README or .gitignore (the project already has them). Click
   **Create repository**.
4. On the new repo page, click the link **“uploading an existing file”**
   (under “…or get started by”).
5. Open your `korea-life` folder on your computer. **Select everything inside it**
   (app.py, the `korealife` folder, the `pages` folder, `data`, requirements.txt,
   Procfile, etc.) and **drag it all** onto the GitHub upload page.
   - Make sure you upload the **contents** of `korea-life`, so that `app.py` sits at
     the top level of the repo (not inside a nested `korea-life/korea-life` folder).
   - Do **not** upload any `.env` file or `korea_life.db`. (If you don’t see them,
     good — the `.gitignore` hides them.)
6. Wait for the files to finish uploading, then click **Commit changes**.

Your code is now on GitHub.

---

## Phase 2 — Deploy on Railway

1. Go to **https://railway.app** and sign in with **GitHub** (easiest — it links your
   repos automatically).
2. Click **New Project** → **Deploy from GitHub repo**.
3. Authorize Railway to see your repos if it asks, then pick **`korea-life`**.
4. Railway starts building automatically. It detects Python from `requirements.txt`
   and launches the app using the included `Procfile`. (No start command to type.)

### 2a. Add your Claude API key

5. Open the service (the box Railway created) → **Variables** tab → **New Variable**:
   - Name: `ANTHROPIC_API_KEY`  Value: `sk-ant-...` (your key)
   - (optional) add `ANTHROPIC_MODEL` = `claude-sonnet-4-5`
6. Railway redeploys. Without this, the app still runs — just in offline demo mode.

### 2b. Keep data between deploys (recommended)

Railway wipes the disk on each redeploy, so without a volume your reminders and
inquiries reset. To keep them:

7. Service → **Volumes** → **New Volume** → mount path: `/data`.
8. Service → **Variables** → add `KOREA_LIFE_DB` = `/data/korea_life.db`.
   (The app reads this and stores its database on the volume. Demo organizations
   re-seed automatically, so KOREA-LIFE Connect is never empty.)

### 2c. Get your public link

9. Service → **Settings** → **Networking** → **Generate Domain**.
10. Open the generated URL. You should see the KOREA-LIFE Home page.
    In the sidebar, the badge should read **“AI · live Claude”** (confirming the key).

---

## Checks & troubleshooting

- **Build/boot failed?** Open the service → **Deployments** → click the latest →
  read the **Deploy Logs**. A healthy start shows Streamlit booting with no
  tracebacks. Copy any error if you need help.
- **Sidebar says “offline demo” instead of “live Claude”?** The `ANTHROPIC_API_KEY`
  variable isn’t set or is misspelled. Fix it in **Variables**; Railway redeploys.
- **Data resets after a redeploy?** The volume/`KOREA_LIFE_DB` step (2b) isn’t set.
- **Cost note:** a public URL in live mode means anyone with the link can ask
  questions, and each one uses your Anthropic credits. Keep the link private for a
  demo, and consider a spending limit in the Anthropic console.

---

## Updating the app later

Change a file on GitHub (or re-upload), commit, and Railway automatically rebuilds
and redeploys. Your volume data is preserved.
