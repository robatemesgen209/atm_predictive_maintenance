# ATM Sentinel — Predictive Maintenance & Incident Management

A Streamlit application for tracking ATM incidents, identifying repeated faults, and estimating which component category deserves the next maintenance inspection.

## Included data

`data/ncr_report.csv` is the supplied NCR incident export (2,461 rows, 14 source columns). It is imported automatically on first launch. The app preserves original problem text and adds a normalized component category for analysis.

## Features

- Role-based access: **admin**, **manager**, and **district**.
- First-run administrator setup; secure PBKDF2-SHA256 password hashes.
- Admin user provisioning, district assignment, activation/deactivation.
- District users see only their assigned district's incident records.
- Managers and administrators see all districts.
- Historical ATM incident register with status/notes updates, machine explorer, CSV import/export.
- Per-terminal forecast ranking using recency-weighted incident history and district-level smoothing.
- District exposure reports, repeat incident ranking, audit log.
- SQLite database with WAL and indexes; Docker deployment support.

## Run locally (Windows / VS Code)

1. Install Python 3.11 or 3.12.
2. Extract the ZIP and open the `atm_predictive_maintenance` folder in VS Code.
3. Open the terminal:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
```

4. Open the local URL Streamlit prints (normally `http://localhost:8501`).
5. On first launch, create the first administrator account. Use a strong password of at least 10 characters.

## Production deployment

### Docker

```bash
docker build -t atm-sentinel .
docker run -d --name atm-sentinel \
  -p 8501:8501 \
  -v atm_sentinel_data:/app/data \
  --restart unless-stopped \
  atm-sentinel
```

The Docker volume preserves the SQLite database and uploaded historical data across container restarts.

### Production checklist

- Put the app behind HTTPS using a reverse proxy (Nginx, Caddy, or a managed ingress).
- Restrict network access to authorized staff/VPN; do not expose the first-run setup to the public internet.
- Persist `/app/data` (or set `ATM_DB_PATH`) and back it up regularly.
- Use a managed PostgreSQL database instead of SQLite for multiple app replicas or high write concurrency. This starter uses SQLite and is suitable for a single app instance with modest concurrent use.
- Configure TLS, firewall rules, monitoring, backups, and a recovery test.
- Change temporary passwords out-of-band. The app currently supports admin activation/deactivation, not self-service password reset.
- Do not store sensitive customer card/PIN data in incident comments or CSV exports.

## Forecast interpretation — important

The forecast is a **maintenance prioritization signal**, not a certified failure prediction and not a calibrated probability. It ranks component categories from:
1. The selected terminal's historical incidents, weighted so more recent incidents contribute more.
2. A small district-level component baseline to stabilize limited machine history.

The relative percentages are normalized ranking scores, not a guarantee that a part will fail. The dataset is an incident/call log; it does not include machine telemetry, component age, maintenance actions, uptime exposure, or confirmed root-cause labels. A technician must inspect and confirm before replacing hardware.

For a stronger predictive model, collect structured root-cause diagnosis, replaced part, failure start/end, preventive maintenance, ATM age/model, counters, downtime, and component-level exposure. Then evaluate time-based holdout performance, calibration, recall for high-cost failures, and false-alarm rate.

## Data mapping

The source export contains 47 distinct raw `problem` labels. The app maps them into normalized categories (for example, `Card Reade` → Card Reader, `Power Supp` → Power Supply, `3rd Casset` → Cassette 3). Unrecognized categories remain `Other / Unclassified`. Review `predictor.py`'s `normalize_component()` to adapt mapping rules to your organization's NCR terminology.

## Important security / operational notes

- Passwords are stored as PBKDF2 hashes, never plaintext.
- District access is filtered server-side in the database query used by the application.
- Admin user management is available after the first admin has been created.
- This is a deployable application foundation, but your bank's IT/security team should conduct penetration testing, privacy review, backup validation, and load testing before production approval.
