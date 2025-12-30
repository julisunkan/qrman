import os
import sqlite3
from flask import Flask, redirect, url_for, request, render_template, send_from_directory
import uuid
from datetime import datetime, timedelta
import qr_utils
from user_agents import parse

app = Flask(__name__)
DB_FILE = 'database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_FILE):
        with open('models.sql', 'r') as f:
            sql = f.read()
        conn = get_db_connection()
        conn.executescript(sql)
        conn.commit()
        conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    qr_type = request.form.get('type', 'url')
    fg_color = request.form.get('fg_color', '#000000')
    bg_color = request.form.get('bg_color', '#ffffff')
    expiry_days = request.form.get('expiry_days')
    logo = request.files.get('logo')

    if qr_type == 'vcard':
        fn = request.form.get('first_name', '')
        ln = request.form.get('last_name', '')
        tel = request.form.get('phone', '')
        email = request.form.get('email', '')
        org = request.form.get('org', '')
        # Simple vCard 3.0 format
        target_url = f"BEGIN:VCARD\nVERSION:3.0\nN:{ln};{fn};;;\nFN:{fn} {ln}\nORG:{org}\nTEL;TYPE=CELL:{tel}\nEMAIL:{email}\nEND:VCARD"
    else:
        target_url = request.form.get('url')

    code = str(uuid.uuid4())[:8]
    expires_at = None
    if expiry_days:
        expires_at = (datetime.now() + timedelta(days=int(expiry_days))).isoformat()

    conn = get_db_connection()
    conn.execute('INSERT INTO links (code, target_url, expires_at) VALUES (?, ?, ?)',
                 (code, target_url, expires_at))
    conn.commit()
    conn.close()

    # If it's a vCard, we'll save the .vcf file and provide a download option
    if qr_type == 'vcard':
        vcf_filename = f"{code}.vcf"
        vcf_path = os.path.join('static', 'qr_codes', vcf_filename)
        with open(vcf_path, 'w') as f:
            f.write(target_url)
        return redirect(url_for('dashboard', code=code, is_vcard='1'))

    # Generate QR codes for non-vCard types (e.g., URL)
    domain = request.host_url.rstrip('/')
    redirect_url = f"{domain}/r/{code}"
    
    logo_path = None
    if logo and logo.filename:
        logo_path = os.path.join('static', 'qr_codes', f"logo_{code}.png")
        logo.save(logo_path)

    qr_utils.generate_all_formats(code, redirect_url, fg_color, bg_color, logo_path)
    
    return redirect(url_for('dashboard', code=code))

@app.route('/dashboard/<code>')
def dashboard(code):
    is_vcard = request.args.get('is_vcard') == '1'
    conn = get_db_connection()
    link = conn.execute('SELECT * FROM links WHERE code = ?', (code,)).fetchone()
    if not link:
        return "Not Found", 404
        
    scans = conn.execute('SELECT * FROM scans WHERE link_code = ? ORDER BY timestamp DESC', (code,)).fetchall()
    
    # Simple aggregation for charts
    stats = {
        'total': link['total_scans'],
        'countries': {},
        'devices': {'Mobile': 0, 'Tablet': 0, 'Desktop': 0},
        'daily': {}
    }
    
    for scan in scans:
        stats['countries'][scan['country']] = stats['countries'].get(scan['country'], 0) + 1
        stats['devices'][scan['device']] = stats['devices'].get(scan['device'], 0) + 1
        day = scan['timestamp'].split(' ')[0]
        stats['daily'][day] = stats['daily'].get(day, 0) + 1
    
    conn.close()
    return render_template('dashboard.html', link=link, stats=stats, is_vcard=is_vcard)

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

@app.route('/vcard-viewer')
def vcard_viewer():
    return render_template('vcard_viewer.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)