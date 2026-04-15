from flask import Flask, render_template, request, jsonify, Response
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
import os
import smtplib
import csv
from io import StringIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from collections import OrderedDict

app = Flask(__name__)
CTF_MAX_PARTICIPANTS = 15
ADMIN_USERNAME = 'openday'
ADMIN_PASSWORD = 'opendayzoui404'

DB_PATH = os.path.join(app.instance_path, 'database.db')


def load_env_file():
    env_path = os.path.join(app.root_path, '.env')
    if not os.path.exists(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as env_file:
        for raw_line in env_file:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()


def get_email_settings():
    return {
        'host': os.getenv('SMTP_HOST', '').strip(),
        'port': int(os.getenv('SMTP_PORT', '587')),
        'username': os.getenv('SMTP_USERNAME', '').strip(),
        'password': os.getenv('SMTP_PASSWORD', '').strip(),
        'from_email': os.getenv('SMTP_FROM_EMAIL', '').strip() or os.getenv('SMTP_USERNAME', '').strip(),
        'use_tls': os.getenv('SMTP_USE_TLS', 'true').strip().lower() != 'false',
    }


def send_invitation_email(recipient_email, first_name, team_name, team_members):
    settings = get_email_settings()
    if not settings['host'] or not settings['from_email']:
        raise RuntimeError('SMTP is not configured correctly.')

    css_path = os.path.join(app.root_path, 'static', 'css', 'email_invite.css')
    email_css = ''
    if os.path.exists(css_path):
        with open(css_path, 'r', encoding='utf-8') as css_file:
            email_css = css_file.read()

    html_body = render_template(
        'email_invite.html',
        first_name=first_name,
        event_date='19 April',
        team_name=team_name,
        team_members=team_members,
        email_css=email_css
    )

    plain_members = ', '.join(team_members) if team_members else 'N/A'
    plain_text = (
        f"Hello {first_name},\n\n"
        f"You are invited to Open Day on 19 April.\n"
        f"Team: {team_name or 'N/A'}\n"
        f"Team Members: {plain_members}\n\n"
        "Please arrive 15 minutes early."
    )

    message = MIMEMultipart('alternative')
    message['Subject'] = 'Open Day Invitation - 19 April'
    message['From'] = settings['from_email']
    message['To'] = recipient_email
    message.attach(MIMEText(plain_text, 'plain', 'utf-8'))
    message.attach(MIMEText(html_body, 'html', 'utf-8'))

    with smtplib.SMTP(settings['host'], settings['port'], timeout=20) as server:
        server.ehlo()
        if settings['use_tls']:
            server.starttls()
            server.ehlo()
        if settings['username'] and settings['password']:
            server.login(settings['username'], settings['password'])
        server.sendmail(settings['from_email'], [recipient_email], message.as_string())

    return True, None


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                leader_email TEXT,
                leader_first_name TEXT,
                leader_last_name TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        conn.execute('''
            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT NOT NULL,
                major TEXT NOT NULL,
                games TEXT NOT NULL,
                ctf_mode TEXT,
                team_name TEXT,
                team_id INTEGER,
                is_team_leader BOOLEAN DEFAULT 0,
                suggestion TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        columns = [row[1] for row in conn.execute('PRAGMA table_info(registrations)').fetchall()]
        if 'team_id' not in columns:
            conn.execute('ALTER TABLE registrations ADD COLUMN team_id INTEGER')
        if 'is_team_leader' not in columns:
            conn.execute('ALTER TABLE registrations ADD COLUMN is_team_leader BOOLEAN DEFAULT 0')

        # Backfill teams from legacy registrations that only had team_name.
        legacy_team_names = conn.execute('''
            SELECT DISTINCT team_name
            FROM registrations
            WHERE team_name IS NOT NULL AND TRIM(team_name) <> ''
        ''').fetchall()
        for (team_name,) in legacy_team_names:
            if team_name:
                conn.execute(
                    'INSERT OR IGNORE INTO teams (name) VALUES (?)',
                    (team_name.strip(),)
                )

        # Backfill team leader metadata from the earliest registration per legacy team.
        conn.execute('''
            UPDATE teams
            SET
                leader_email = COALESCE(leader_email, (
                    SELECT email
                    FROM registrations
                    WHERE registrations.team_name = teams.name
                    ORDER BY timestamp ASC
                    LIMIT 1
                )),
                leader_first_name = COALESCE(leader_first_name, (
                    SELECT first_name
                    FROM registrations
                    WHERE registrations.team_name = teams.name
                    ORDER BY timestamp ASC
                    LIMIT 1
                )),
                leader_last_name = COALESCE(leader_last_name, (
                    SELECT last_name
                    FROM registrations
                    WHERE registrations.team_name = teams.name
                    ORDER BY timestamp ASC
                    LIMIT 1
                ))
            WHERE EXISTS (
                SELECT 1
                FROM registrations
                WHERE registrations.team_name = teams.name
            )
        ''')

        conn.execute('''
            UPDATE registrations
            SET team_id = (
                SELECT id FROM teams WHERE teams.name = registrations.team_name
            )
            WHERE team_name IS NOT NULL AND TRIM(team_name) <> '' AND team_id IS NULL
        ''')

        conn.commit()


def check_admin_auth(username, password):
    return username == ADMIN_USERNAME and password == ADMIN_PASSWORD


def auth_required_response():
    return Response(
        'Authentication required.',
        401,
        {'WWW-Authenticate': 'Basic realm="OpenDay Admin"'}
    )


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/ctf-count')
def ctf_count():
    with sqlite3.connect(DB_PATH) as conn:
        count = conn.execute("SELECT COUNT(*) FROM registrations WHERE games LIKE '%CTF%'").fetchone()[0]
    full = count >= CTF_MAX_PARTICIPANTS
    message = f'تم الوصول إلى الحد الأقصى ({CTF_MAX_PARTICIPANTS}/{CTF_MAX_PARTICIPANTS})' if full else f'Capture the Flag - {CTF_MAX_PARTICIPANTS} participants (5 teams x 3)'
    return jsonify({'count': count, 'full': full, 'message': message})


@app.route('/available-teams')
def available_teams():
    """جلب قائمة الفرق المتاحة التي يقودها القادة المسجلون"""
    with sqlite3.connect(DB_PATH) as conn:
        teams = conn.execute('''
            SELECT
                teams.id,
                teams.name,
                teams.leader_first_name,
                teams.leader_last_name,
                COUNT(registrations.id) AS member_count
            FROM teams
            LEFT JOIN registrations ON registrations.team_id = teams.id
            GROUP BY teams.id, teams.name, teams.leader_first_name, teams.leader_last_name
            HAVING member_count < 3 OR member_count IS NULL
            ORDER BY teams.name ASC
        ''').fetchall()
    
    teams_list = [
        {
            'id': row[0],
            'name': row[1],
            'leader': f"{row[2] or ''} {row[3] or ''}".strip(),
            'member_count': row[4] or 0,
        }
        for row in teams
    ]
    return jsonify(teams_list)


def fetch_ctf_team_rows():
    """جلب جميع تسجيلات CTF مجمعة حسب اسم الفريق تلقائيًا"""
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute('''
            SELECT
                registrations.id,
                registrations.first_name,
                registrations.last_name,
                registrations.email,
                registrations.phone,
                registrations.major,
                registrations.team_name,
                registrations.is_team_leader,
                registrations.timestamp,
                teams.id AS team_id,
                teams.name AS team_name_resolved
            FROM registrations
            LEFT JOIN teams ON teams.id = registrations.team_id
            WHERE games LIKE '%CTF%' AND ctf_mode = 'team'
            ORDER BY LOWER(COALESCE(teams.name, registrations.team_name, '')), registrations.is_team_leader DESC, registrations.timestamp ASC
        ''').fetchall()


@app.route('/ayad/test/khenchela/dz/log')
def admin_log():
    auth = request.authorization
    if not auth or not check_admin_auth(auth.username, auth.password):
        return auth_required_response()

    rows = fetch_ctf_team_rows()

    grouped_teams = OrderedDict()
    for row in rows:
        team_name = (row['team_name_resolved'] or row['team_name'] or 'Unnamed Team').strip() or 'Unnamed Team'

        if team_name not in grouped_teams:
            grouped_teams[team_name] = []

        grouped_teams[team_name].append({
            'id': row['id'],
            'name': f"{row['first_name']} {row['last_name']}",
            'email': row['email'],
            'phone': row['phone'],
            'major': row['major'],
            'is_leader': bool(row['is_team_leader']),
            'timestamp': row['timestamp']
        })

    return render_template('admin_log.html', grouped_teams=grouped_teams, total_count=len(rows))


@app.route('/ayad/test/khenchela/dz/log/export.csv')
def admin_log_export_csv():
    auth = request.authorization
    if not auth or not check_admin_auth(auth.username, auth.password):
        return auth_required_response()

    rows = fetch_ctf_team_rows()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['team_name', 'member_name', 'email', 'phone', 'major', 'role', 'timestamp'])

    for row in rows:
        team_name = (row['team_name_resolved'] or row['team_name'] or 'Unnamed Team').strip() or 'Unnamed Team'
        member_name = f"{row['first_name']} {row['last_name']}"
        role = 'قائد الفريق' if row['is_team_leader'] else 'عضو'
        writer.writerow([
            team_name,
            member_name,
            row['email'],
            row['phone'],
            row['major'],
            role,
            row['timestamp']
        ])

    csv_data = output.getvalue()
    output.close()

    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=ctf_teams_log.csv'}
    )


@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.form
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        email = data['email'].strip().lower()
        phone = data['phone'].strip()
        major = data['major'].strip()
        games_list = data.getlist('games')
        games = ','.join(games_list)
        ctf_mode = data.get('ctf_mode')
        ctf_role = data.get('ctf_role')  # 'leader' or 'member'
        team_name = data.get('team_name', '').strip() if ctf_mode == 'team' else None
        suggestion = data.get('suggestion', '').strip()
        team_id = None
        is_leader = 0
        team_members = []

        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row

            if 'CTF' in games_list:
                if ctf_mode != 'team':
                    return jsonify({'success': False, 'error': 'CTF requires team mode (3 participants per team).'}), 400

                if not team_name:
                    return jsonify({'success': False, 'error': 'Please enter or select a team name.'}), 400

                current_ctf = conn.execute("SELECT COUNT(*) FROM registrations WHERE games LIKE '%CTF%'").fetchone()[0]
                if current_ctf >= CTF_MAX_PARTICIPANTS:
                    return jsonify({'success': False, 'error': 'تم الوصول إلى الحد الأقصى'}), 400

                team_row = conn.execute('SELECT id FROM teams WHERE name = ?', (team_name,)).fetchone()

                if ctf_role == 'leader':
                    if team_row:
                        return jsonify({'success': False, 'error': 'Team name already exists. Choose another name.'}), 400

                    team_cursor = conn.execute(
                        'INSERT INTO teams (name, leader_email, leader_first_name, leader_last_name) VALUES (?, ?, ?, ?)',
                        (team_name, email, first_name, last_name)
                    )
                    team_id = team_cursor.lastrowid
                    is_leader = 1

                elif ctf_role == 'member':
                    if not team_row:
                        return jsonify({'success': False, 'error': 'Please select a valid team.'}), 400

                    team_id = team_row['id']
                    team_member_count = conn.execute(
                        'SELECT COUNT(*) FROM registrations WHERE team_id = ?',
                        (team_id,)
                    ).fetchone()[0]
                    if team_member_count >= 3:
                        return jsonify({'success': False, 'error': 'This team is already full.'}), 400
                else:
                    return jsonify({'success': False, 'error': 'Please select your role (Team Leader or Team Member).'}), 400

                conn.execute('''
                    INSERT INTO registrations (first_name, last_name, email, phone, major, games, ctf_mode, team_name, team_id, is_team_leader, suggestion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, phone, major, games, ctf_mode, team_name, team_id, is_leader, suggestion))

                members = conn.execute('''
                    SELECT first_name, last_name
                    FROM registrations
                    WHERE team_id = ? AND games LIKE '%CTF%' AND ctf_mode = 'team'
                    ORDER BY is_team_leader DESC, timestamp ASC
                ''', (team_id,)).fetchall()
                team_members = [f"{member['first_name']} {member['last_name']}" for member in members]

                try:
                    send_invitation_email(email, first_name, team_name, team_members)
                except Exception as email_error:
                    raise RuntimeError('Registration failed: could not deliver confirmation email. Please try again.') from email_error

            else:
                conn.execute('''
                    INSERT INTO registrations (first_name, last_name, email, phone, major, games, ctf_mode, team_name, team_id, is_team_leader, suggestion)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (first_name, last_name, email, phone, major, games, ctf_mode, None, None, 0, suggestion))

                try:
                    send_invitation_email(email, first_name, None, [])
                except Exception as email_error:
                    raise RuntimeError('Registration failed: could not deliver confirmation email. Please try again.') from email_error

        return jsonify({'success': True, 'message': 'Registration successful! Check your email for confirmation.'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'error': 'Email already registered.'}), 400
    except RuntimeError as e:
        return jsonify({'success': False, 'error': str(e)}), 503
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    init_db()
    app.run(debug=False, host='0.0.0.0', port=5000)

