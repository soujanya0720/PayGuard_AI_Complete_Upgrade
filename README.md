# PayGuard AI — Fraud Awareness and Message Screening

A student-project Flask application with account registration/login, SQLite persistence, an administrator dashboard, an educational scikit-learn text classifier, and CSV exports.

> **Important limitation:** the bundled model is trained on a small illustrative dataset included in `ml_detector.py`. It is for demonstrating an ML workflow, not real-world financial decisions. Its score is not a calibrated fraud probability and has not been validated against a representative test set. Do not use this project to approve payments or determine whether a message is definitely safe.

## Features

- User registration and sign-in with hashed passwords
- Flask session-based authentication and logout
- Separate per-user analysis history
- Admin dashboard with account counts, risk counts, recent analyses, and registered accounts
- Admin-only all-record CSV export
- User-only CSV export of their own analysis history
- SQLite database created automatically and migrated from the previous database format
- scikit-learn TF-IDF + Logistic Regression text model blended with explainable rule signals
- Input validation and formula-safe CSV values

## Requirements

- Python 3.10 or newer recommended
- pip
- Internet access only to install Python packages; no separate database server is required

## Run on Windows

1. Extract the ZIP and open the `PayGuard_AI` folder in VS Code.
2. Open Terminal in that folder.
3. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   ```

4. Install packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

5. (Recommended before sharing) Set your own secret key and admin credentials in PowerShell:

   ```powershell
   $env:PAYGUARD_SECRET_KEY = "replace-with-a-long-random-secret"
   $env:PAYGUARD_ADMIN_EMAIL = "your-admin-email@example.com"
   $env:PAYGUARD_ADMIN_PASSWORD = "choose-a-strong-admin-password"
   ```

6. Start the app:

   ```powershell
   python app.py
   ```

7. Open `http://127.0.0.1:5000`.

## Demo credentials

If you do not set environment variables before the first run, the app creates this local demo admin account:

- Email: `admin@payguard.local`
- Password: `Admin@12345`

Change these defaults before sharing the app. Admin credentials are seeded only if that email does not already exist in the database. If you want to change an existing seeded account, update its password in the database or use a new database/email. The secret key must be stable between restarts and must not be shared publicly.

## How to use

1. Create a normal account at **Create an account**.
2. Sign in and paste a sample message into the checker.
3. View the score, signals, and recent history. Each account can access only its own history.
4. Select **Export CSV** to download your own analysis records.
5. Sign out and sign in as the administrator to visit **Admin dashboard**. Use **Export all CSV** to download all saved analyses.

## Project structure

```text
PayGuard_AI/
├── app.py
├── detector.py            # Explainable text-pattern signals
├── ml_detector.py         # Small educational TF-IDF + Logistic Regression model
├── payguard.db            # Created automatically on first run; do not commit
├── requirements.txt
├── README.md
├── templates/
│   ├── auth.html
│   ├── index.html
│   └── admin.html
└── static/
    ├── app.js
    └── style.css
```

## Database tables

- `users`: name, unique email, password hash, role, and creation timestamp.
- `analysis_history`: user association, submitted message, combined score, ML score, risk label, warning signals, safety tips, and timestamp.

Existing `payguard.db` files are migrated when the application starts. Earlier history rows without an owner remain visible to admins but are not shown in any regular user's private history.

## Routes

- `GET/POST /register` — create a normal user account
- `GET/POST /login` — sign in
- `POST /logout` — sign out
- `GET /` — authenticated user message checker
- `POST /analyze` — analyze and save a message
- `GET /history` and `GET /history/<id>` — current user's records
- `DELETE /history` — clear the current user's records
- `GET /export.csv` — export current user's records
- `GET /admin` — admin dashboard
- `GET /admin/export.csv` — admin-only export of all records

## Security and privacy notes

- Passwords are hashed with Werkzeug; raw passwords are never stored.
- Admin access is checked server-side.
- Never paste real OTPs, passwords, card details, or account numbers.
- CSV exports contain submitted message text, so handle them as sensitive data.
- The built-in secret key and demo admin credentials are for local demonstration only. Configure strong environment values before sharing or deploying.
- For a real deployment, add CSRF protection, rate limiting, account recovery, secure HTTPS cookies, logging/monitoring, and security review. Do not expose Flask's development server to the public internet.

## ML notes

`ml_detector.py` trains a TF-IDF + Logistic Regression pipeline on a small, bundled set of example messages at runtime. The app combines its score with the existing rule-based detector. The sample set is intentionally small and illustrative; it is not a validated or representative fraud dataset. For meaningful evaluation, use a legally obtained, privacy-reviewed, labeled dataset and report precision, recall, F1, false-positive rates, and performance on an untouched test set.
