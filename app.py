import os
import sqlite3
import base64
from flask import Flask, redirect, url_for, request, render_template, send_from_directory, Response
import uuid
from datetime import datetime, timedelta
import qr_utils
from user_agents import parse

app = Flask(__name__)
DB_FILE = 'database.db'

def encrypt_code(code):
    return base64.urlsafe_b64encode(code.encode()).decode().rstrip('=')

def decrypt_code(encoded):
    padding = '=' * (4 - len(encoded) % 4)
    return base64.urlsafe_b64decode((encoded + padding).encode()).decode()

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
        phones = request.form.getlist('phone[]')
        emails = request.form.getlist('email[]')
        org = request.form.get('org', '')
        
        vcard_lines = [
            "BEGIN:VCARD",
            "VERSION:3.0",
            f"N:{ln};{fn};;;",
            f"FN:{fn} {ln}",
            f"ORG:{org}"
        ]
        
        for phone in phones:
            if phone.strip():
                vcard_lines.append(f"TEL;TYPE=CELL:{phone.strip()}")
        
        for email in emails:
            if email.strip():
                vcard_lines.append(f"EMAIL:{email.strip()}")
                
        vcard_lines.append("END:VCARD")
        target_url = "\n".join(vcard_lines)
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

    encrypted_code = encrypt_code(code)
    domain = request.host_url.rstrip('/')
    
    if qr_type == 'vcard':
        vcf_filename = f"{code}.vcf"
        vcf_path = os.path.join('static', 'qr_codes', vcf_filename)
        with open(vcf_path, 'w') as f:
            f.write(target_url)
        return redirect(url_for('dashboard', encoded_code=encrypted_code, is_vcard='1'))

    redirect_url = f"{domain}/r/{encrypted_code}"
    
    logo_path = None
    if logo and logo.filename:
        logo_path = os.path.join('static', 'qr_codes', f"logo_{code}.png")
        logo.save(logo_path)

    qr_utils.generate_all_formats(code, redirect_url, fg_color, bg_color, logo_path)
    
    return redirect(url_for('dashboard', encoded_code=encrypted_code))

@app.route('/dashboard/<encoded_code>')
def dashboard(encoded_code):
    try:
        code = decrypt_code(encoded_code)
    except:
        return "Invalid Code", 400
        
    is_vcard = request.args.get('is_vcard') == '1'
    conn = get_db_connection()
    link = conn.execute('SELECT * FROM links WHERE code = ?', (code,)).fetchone()
    if not link:
        return "Not Found", 404
        
    scans = conn.execute('SELECT * FROM scans WHERE link_code = ? ORDER BY timestamp DESC', (code,)).fetchall()
    
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
    return render_template('dashboard.html', link=link, stats=stats, is_vcard=is_vcard, encoded_code=encoded_code)

@app.route('/r/<encoded_code>')
def redirect_to_url(encoded_code):
    try:
        code = decrypt_code(encoded_code)
    except:
        return "Invalid Code", 400
        
    conn = get_db_connection()
    link = conn.execute('SELECT * FROM links WHERE code = ?', (code,)).fetchone()
    
    if not link:
        return "Not Found", 404

    if link['expires_at'] and datetime.fromisoformat(link['expires_at']) < datetime.now():
        return render_template('expired.html', link=link)

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

    if link['target_url'].startswith('BEGIN:VCARD'):
        return Response(link['target_url'], mimetype='text/vcard', headers={'Content-Disposition': f'attachment; filename={code}.vcf'})

    return redirect(link['target_url'])

@app.route('/viewer')
def viewer():
    return render_template('viewer.html')

@app.route('/vcard-viewer')
def vcard_viewer():
    return render_template('vcard_viewer.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)