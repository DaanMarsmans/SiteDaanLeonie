import os
import threading
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename
import sqlite3
import csv
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'super-secret-key'

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME='daanmarsmans@gmail.com',
    MAIL_PASSWORD='jbix aidl hacc quwx',
    MAIL_DEFAULT_SENDER='daanmarsmans@gmail.com'
)

mail = Mail(app)


# Function to send email asynchronously
def send_async_email(app, msg):
    with app.app_context():
        try:
            mail.send(msg)
        except Exception as e:
            print(f"Failed to send email: {e}")


# Upload path
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

DB = 'forms.db'


def init_db():
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                id INTEGER PRIMARY KEY,
                naam TEXT, email TEXT, straat TEXT,
                plaats TEXT, postcode TEXT, telefoon TEXT,
                submitted_at TEXT
            )
        ''')
        cur.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        cur.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('background_image', 'default.jpg'))
        cur.execute('INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)', ('form_opacity', '0.8'))
        conn.commit()


init_db()


def get_setting(key):
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute('SELECT value FROM settings WHERE key=?', (key,))
        row = cur.fetchone()
        return row[0] if row else None


def set_setting(key, value):
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute('REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
        conn.commit()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data = {
            'naam': request.form['naam'],
            'email': request.form['email'],
            'straat': request.form['straat'],
            'plaats': request.form['plaats'],
            'postcode': request.form['postcode'],
            'telefoon': request.form['telefoon'],
            'submitted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with sqlite3.connect(DB) as conn:
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO submissions 
                (naam, email, straat, plaats, postcode, telefoon, submitted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', tuple(data.values()))
            conn.commit()

        # Send notification to yourself asynchronously
        try:
            msg = Message("Nieuwe formulierinzending", recipients=["daanmarsmans@gmail.com"])
            msg.body = "\n".join(f"{k}: {v}" for k, v in data.items())

            # Send email in a background thread
            threading.Thread(target=send_async_email, args=(app, msg)).start()
        except Exception as e:
            print(f"Error preparing email: {e}")
            # Continue with the form submission even if email fails

        # Flash visible confirmation
        flash("Dank je wel, hopelijk zijn we je op de bruiloft!", "success")

    background = get_setting('background_image')
    opacity = get_setting('form_opacity')
    return render_template('index.html', background=background, opacity=opacity)


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        if 'background' in request.files:
            file = request.files['background']
            if file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                set_setting('background_image', filename)

        if 'opacity' in request.form:
            set_setting('form_opacity', request.form['opacity'])

    background = get_setting('background_image')
    opacity = get_setting('form_opacity')

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM submissions ORDER BY submitted_at DESC")
        rows = cur.fetchall()

    return render_template('admin.html', submissions=rows, background=background, opacity=opacity)


@app.route('/download')
def download():
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM submissions")
        rows = cur.fetchall()

    filepath = 'submissions.csv'
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Naam', 'Email', 'Straat', 'Plaats', 'Postcode', 'Telefoon', 'Inzenddatum'])
        writer.writerows(rows)

    return send_file(filepath, as_attachment=True)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if (request.form['username'] == 'Daan' and request.form['password'] == 'GeefJeHartNietZoMaarWeg2!') or \
                (request.form['username'] == 'Leonie' and request.form['password'] == 'GeefJeHartNietZoMaarWeg2!'):
            session['logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash("Ongeldige inloggegevens", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))

    try:
        with sqlite3.connect(DB) as conn:
            cur = conn.cursor()
            # First, verify the entry exists
            cur.execute("SELECT id FROM submissions WHERE id=?", (entry_id,))
            if not cur.fetchone():
                flash("Inzending niet gevonden", "danger")
                return redirect(url_for('admin'))

            # Delete the entry
            cur.execute("DELETE FROM submissions WHERE id=?", (entry_id,))
            conn.commit()
            flash("Inzending succesvol verwijderd", "success")
    except Exception as e:
        flash(f"Fout bij verwijderen: {str(e)}", "danger")

    return redirect(url_for('admin'))


if __name__ == '__main__':
    app.run(debug=True)
