# KLEAR IQ — Football Performance Grading

**Purpose:** Grade players during practices linked to a specific opponent/game week and grade the game itself. Compare practice and game results without blending the two together.

## Included
- Admin password-protected dashboard
- Season → week → opponent game-week organization
- Multiple practice sessions and one game session per opponent
- Roster and 5-category scores (Align, Assign, Tech, Effort, Overall), each 0–3
- One grade per player per session; saving a new grade for that player updates the existing one
- Default tier display: T4 13–15, T3 10–12, T2 7–9, T1 0–6 (verify against your approved workbook)
- Weekly practice average, game average, and difference by player
- Full grades CSV, weekly summary CSV, season practice/game averages
- Responsive dark theme with red accents

**Not included yet:** XLSX import, BOSS automatic scoring rules from the workbooks, per-play grading, multi-coach accounts, opponent file attachments, rubric customization, audit logs, granular permissions, backups UI. This release intentionally focuses on grading performance. It is a functional MVP, not a production security audit.

## Free-tier warning
Render Free web services sleep after 15 minutes of inactivity and may start slowly on the next visit. Free PostgreSQL expires 30 days after creation, with no managed backups. **Export weekly grades and summaries after every grading session** from the week page and keep those CSV files securely outside Render. CSV downloads are not a complete restorable database backup (they do not include all metadata/roster links). Treat this deployment as testing only. The web service has no persistent local disk. Upgrade or move to another persistent data store before the free database expires. Free-tier quotas or other usage can still lead to charges in some circumstances; check Render billing and quotas.

## GitHub deployment
1. Sign in to GitHub. Create **private** repository `klear-iq` (do not initialize README).
2. Download and extract `klear-iq-render-github.zip`; open the inner `klear-iq` folder.
3. Upload **all contents** of the inner folder to your repository's root. Preserve `templates/`, `static/`, and `render.yaml`.
4. Commit the files. Do NOT upload `.env` or real passwords.

## Render deployment (Blueprint)
1. Connect the Render account to GitHub and permit access to the private `klear-iq` repository.
2. In Render, choose **New → Blueprint** and select the `klear-iq` repository.
3. Render should discover `render.yaml`. Verify both web service and PostgreSQL plans show **free** and the estimated monthly charge is **$0** before approval. Do not approve a paid plan accidentally.
4. Provide a strong `ADMIN_PASSWORD` when Render requests the unsynced environment variable. `SECRET_KEY` is generated automatically.
5. Deploy and open the HTTPS `.onrender.com` URL shown by Render. Sign in with your password.
6. Create a player on Roster, then create a game week, add Monday/Tuesday/etc. practices and game day, and grade players.

**Important:** The app stores player names and performance scores. Limit access, follow your school's data policy, and do not enter protected student information or unnecessary personal details. Repository privacy is NOT application access control. For team-wide use, implement individual coach accounts, backups, role permissions, password rotation, rate limiting, CSRF/security audit, and retention policy.

## Run locally
```bash
python -m venv .venv
# Activate your environment, then:
pip install -r requirements.txt
export ADMIN_PASSWORD='a-new-strong-password' # macOS/Linux; use set on Windows cmd or $env: on PowerShell
export SECRET_KEY='long-random-string'
python app.py
```
Visit http://127.0.0.1:5000. Local SQLite is used when DATABASE_URL is absent.

## Original rubric
The user-provided grading explanation defines Align, Assign, Technique, Effort, and Overall/Trust, scored 0–3. Those five categories are implemented without changing the stated scoring semantics. The displayed numeric tier bands are **working defaults** and should be reconciled with the original Excel tier rules before they drive personnel decisions. Weekly performance is explicitly separated into practice and game rather than assigning an unsupported weighting.
