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

    # Generate QR codes
    domain = request.host_url.rstrip('/')
    # If it's a vCard, we might want to link directly or use the redirector
    # Using the redirector allows tracking, but the mobile device must handle the text as a vCard after redirect
    redirect_url = f"{domain}/r/{code}"
    
    logo_path = None
    if logo and logo.filename:
        logo_path = os.path.join('static', 'qr_codes', f"logo_{code}.png")
        logo.save(logo_path)

    qr_utils.generate_all_formats(code, redirect_url, fg_color, bg_color, logo_path)
    
    return redirect(url_for('dashboard', code=code))

@app.route('/r/<code>')
def redirect_to_url(code):
    conn = get_db_connection()
    link = conn.execute('SELECT * FROM links WHERE code = ?', (code,)).fetchone()
    
    if not link:
        return "Not Found", 404

    if link['expires_at'] and datetime.fromisoformat(link['expires_at']) < datetime.now():
        return render_template('expired.html', link=link)

    # Log scan
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    ua_string = request.headers.get('User-Agent')
    ua = parse(ua_string)
    
    device = "Desktop"
    if ua.is_mobile: device = "Mobile"
    elif ua.is_tablet: device = "Tablet"
    
    country = qr_utils.get_country(ip)

    conn.execute('INSERT INTO scans (link_code, country, device, ip) VALUES (?, ?, ?, ?)',
                 (code, country, device, ip))
    conn.execute('UPDATE links SET total_scans = total_scans + 1 WHERE code = ?', (code,))
    conn.commit()
    conn.close()

    # If target_url starts with BEGIN:VCARD, it's a vCard
    if link['target_url'].startswith('BEGIN:VCARD'):
        # For vCards, we return the text content with correct MIME type so phones pick it up
        from flask import Response
        return Response(link['target_url'], mimetype='text/vcard', headers={'Content-Disposition': f'attachment; filename={code}.vcf'})

    return redirect(link['target_url'])

@app.route('/dashboard/<code>')
def dashboard(code):
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
    return render_template('dashboard.html', link=link, stats=stats)

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

@app.route('/vcard-viewer')
def vcard_viewer():
    return render_template('vcard_viewer.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)