# OpenDay Registration Platform

A Flask-based registration platform for Open Day events, with:

- Multi-game registration
- CTF team flow (leader/member)
- CTF capacity limit (max 15 participants)
- Email invitation after successful registration (SMTP)
- Password-protected admin page
- CSV export for CTF registrations

## Project Structure

- `app.py`: Flask backend and routes
- `templates/index.html`: Main landing and registration page
- `templates/email_invite.html`: Invitation email template
- `templates/admin_log.html`: Admin dashboard for CTF teams
- `static/js/main.js`: Frontend logic
- `static/css/style.css`: Main page styles
- `static/css/email_invite.css`: Email styles
- `instance/database.db`: SQLite database (generated at runtime)

## Requirements

- Python 3.9+
- Flask

Install dependencies:

```bash
pip install flask
```

## Environment Variables (.env)

Create `.env` in project root:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your_email@example.com
SMTP_PASSWORD=your_app_password
SMTP_FROM_EMAIL=your_email@example.com
SMTP_USE_TLS=true
```

Notes:

- Use an app password for Gmail SMTP.
- Registration returns an error if confirmation email cannot be delivered.

## Run the App

```bash
python3 app.py
```

Open in browser:

- `http://127.0.0.1:5000/`

## CTF Rules Implemented

- Maximum total CTF participants: 15
- Team size: up to 3
- Team leader creates team name
- Team members join an existing team
- If limit is reached, users see: `تم الوصول إلى الحد الأقصى`

## Admin Access

Admin page:

- `/ayad/test/khenchela/dz/log`

CSV export:

- `/ayad/test/khenchela/dz/log/export.csv`

HTTP Basic Auth credentials:

- Username: `openday`
- Password: `opendayzoui404`

## API Endpoints

- `GET /ctf-count`: current CTF count and full status
- `GET /available-teams`: available teams for joining
- `POST /register`: submit registration

## Database Overview

### `teams`

- `id`
- `name` (unique)
- `leader_email`
- `leader_first_name`
- `leader_last_name`
- `created_at`

### `registrations`

- `id`
- `first_name`, `last_name`
- `email` (unique)
- `phone`, `major`
- `games`
- `ctf_mode`
- `team_name`
- `team_id`
- `is_team_leader`
- `suggestion`
- `timestamp`

## Quick Validation

Syntax check:

```bash
python3 -m py_compile app.py
```

CTF status check:

```bash
python3 - <<'PY'
from app import app
client = app.test_client()
print(client.get('/ctf-count').get_json())
PY
```
