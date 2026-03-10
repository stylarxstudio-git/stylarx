import os, json, re, secrets, smtplib, uuid, time
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, session, redirect, render_template, Response, stream_with_context
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

LEADS_FILE     = os.path.join(DATA_DIR, 'leads.json')
TEMPLATES_FILE = os.path.join(DATA_DIR, 'templates.json')
APP_PASSWORD   = os.environ.get('APP_PASSWORD', 'stylarx2024')

CATEGORIES = {
    'character_artist':   'Character Artist',
    'texture_artist':     'Texture Artist',
    'environment_artist': 'Environment Artist',
    'vfx_artist':         'VFX Artist',
    'animator':           'Animator',
    'motion_graphics':    'Motion Graphics',
    'technical_artist':   'Technical Artist',
    'game_developer':     'Game Developer',
    '3d_generalist':      '3D Generalist',
    'concept_artist':     'Concept Artist',
    'unknown':            'General',
}

STATUS_LABELS = {
    'pending':  'Pending',
    'sent':     'Sent',
    'fake':     'Fake / Invalid',
    'no_reply': 'No Reply',
    'replied':  'Replied',
    'bounced':  'Bounced',
}

def load_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def load_leads():      return load_json(LEADS_FILE, [])
def save_leads(d):     save_json(LEADS_FILE, d)
def load_templates():  return load_json(TEMPLATES_FILE, {})
def save_templates(d): save_json(TEMPLATES_FILE, d)

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('authed'):
            if request.is_json: return jsonify({'error': 'unauthorized'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper

# ── Auth ──────────────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET','POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == APP_PASSWORD:
            session['authed'] = True
            return redirect('/')
        error = 'Wrong password'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@require_auth
def index():
    return render_template('index.html')

# ── Leads ─────────────────────────────────────────────────────────────────────
@app.route('/api/leads')
@require_auth
def api_leads():
    return jsonify(load_leads())

@app.route('/api/leads/import', methods=['POST'])
@require_auth
def api_import():
    d        = request.json or {}
    raw      = d.get('emails', [])
    category = d.get('category', 'unknown')
    if category not in CATEGORIES: category = 'unknown'
    leads    = load_leads()
    existing = {l['email'].lower() for l in leads}
    added    = 0
    for e in raw:
        email = e.strip().lower()
        if not re.match(r'[^@]+@[^@]+\.[^@]{2,}', email): continue
        if email in existing: continue
        leads.append({
            'id':       secrets.token_hex(8),
            'email':    email,
            'category': category,
            'status':   'pending',
            'note':     '',
            'added_at': datetime.now().isoformat(),
            'sent_at':  None,
        })
        existing.add(email)
        added += 1
    save_leads(leads)
    return jsonify({'added': added, 'total': len(leads)})

@app.route('/api/leads/update', methods=['POST'])
@require_auth
def api_update():
    d     = request.json or {}
    lid   = d.get('id')
    field = d.get('field')
    value = d.get('value')
    leads = load_leads()
    for l in leads:
        if l['id'] == lid:
            if field in ('status', 'note', 'category'):
                l[field] = value
                if field == 'status' and value == 'sent' and not l.get('sent_at'):
                    l['sent_at'] = datetime.now().isoformat()
            break
    save_leads(leads)
    return jsonify({'ok': True})

@app.route('/api/leads/delete', methods=['POST'])
@require_auth
def api_delete():
    ids   = set((request.json or {}).get('ids', []))
    leads = [l for l in load_leads() if l['id'] not in ids]
    save_leads(leads)
    return jsonify({'ok': True})

@app.route('/api/leads/clear', methods=['POST'])
@require_auth
def api_clear():
    save_leads([])
    return jsonify({'ok': True})

@app.route('/api/stats')
@require_auth
def api_stats():
    leads     = load_leads()
    by_status = {}
    by_cat    = {}
    for l in leads:
        s = l.get('status', 'pending')
        c = l.get('category', 'unknown')
        by_status[s] = by_status.get(s, 0) + 1
        by_cat[c]    = by_cat.get(c, 0) + 1
    return jsonify({'total': len(leads), 'by_status': by_status, 'by_cat': by_cat})

# ── Templates ─────────────────────────────────────────────────────────────────
@app.route('/api/templates')
@require_auth
def api_get_templates():
    return jsonify(load_templates())

@app.route('/api/templates/save', methods=['POST'])
@require_auth
def api_save_template():
    d       = request.json or {}
    cat     = d.get('category')
    subject = d.get('subject', '')
    body    = d.get('body', '')
    if not cat or cat not in CATEGORIES:
        return jsonify({'error': 'invalid category'}), 400
    templates = load_templates()
    if cat not in templates: templates[cat] = []
    templates[cat].append({'subject': subject, 'body': body, 'saved_at': datetime.now().isoformat()})
    save_templates(templates)
    return jsonify({'ok': True})

@app.route('/api/templates/update', methods=['POST'])
@require_auth
def api_update_template():
    d       = request.json or {}
    cat     = d.get('category')
    idx     = d.get('index')
    subject = d.get('subject', '')
    body    = d.get('body', '')
    templates = load_templates()
    if cat in templates and isinstance(idx, int) and 0 <= idx < len(templates[cat]):
        templates[cat][idx]['subject'] = subject
        templates[cat][idx]['body']    = body
    save_templates(templates)
    return jsonify({'ok': True})

@app.route('/api/templates/delete', methods=['POST'])
@require_auth
def api_delete_template():
    d   = request.json or {}
    cat = d.get('category')
    idx = d.get('index')
    templates = load_templates()
    if cat in templates and isinstance(idx, int) and 0 <= idx < len(templates[cat]):
        templates[cat].pop(idx)
    save_templates(templates)
    return jsonify({'ok': True})

@app.route('/api/categories')
@require_auth
def api_categories():
    return jsonify(CATEGORIES)

CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')

def load_config():  return load_json(CONFIG_FILE, {})
def save_config(d): save_json(CONFIG_FILE, d)

# ── Config API ────────────────────────────────────────────────────────────────
@app.route('/api/config', methods=['GET'])
@require_auth
def api_get_config():
    c = load_config()
    return jsonify({k: v for k, v in c.items() if k != 'smtp_pass'})

@app.route('/api/config', methods=['POST'])
@require_auth
def api_save_config():
    c = load_config()
    c.update(request.json or {})
    save_config(c)
    return jsonify({'ok': True})

# ── Send API ──────────────────────────────────────────────────────────────────
def send_emails_stream(recipients, subject, body):
    cfg       = load_config()
    smtp_user = cfg.get('smtp_user', '')
    smtp_pass = cfg.get('smtp_pass', '').replace(' ', '')
    from_name = cfg.get('from_name', 'Stylarx')

    if not smtp_user or not smtp_pass:
        yield "data: " + json.dumps({'error': 'config', 'msg': 'Gmail credentials not set — go to Settings'}) + "\n\n"
        yield "data: " + json.dumps({'done': True}) + "\n\n"
        return

    leads     = load_leads()
    leads_map = {l['id']: l for l in leads}

    # Connect ONCE before the loop — same as the working version
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(smtp_user, smtp_pass)
    except Exception as e:
        yield "data: " + json.dumps({'error': 'login', 'msg': f'Gmail login failed — {str(e)}'}) + "\n\n"
        yield "data: " + json.dumps({'done': True}) + "\n\n"
        return

    success = fail = skip = 0
    for item in recipients:
        lid   = item.get('id')
        email = item.get('email', '').lower().strip()
        if not email or '@' not in email:
            continue

        name          = email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        body_personal = body.replace('{name}', name)

        try:
            msg = MIMEMultipart()
            msg['From']    = f'{from_name} <{smtp_user}>'
            msg['To']      = email
            msg['Subject'] = subject
            msg.attach(MIMEText(body_personal, 'plain'))
            server.send_message(msg)

            if lid and lid in leads_map:
                leads_map[lid]['status']  = 'sent'
                leads_map[lid]['sent_at'] = datetime.now().isoformat()
            save_leads(list(leads_map.values()))

            success += 1
            yield "data: " + json.dumps({'sent': email}) + "\n\n"
        except Exception as e:
            fail += 1
            yield "data: " + json.dumps({'error': email, 'msg': str(e)[:120]}) + "\n\n"

        time.sleep(2)

    try:
        server.quit()
    except:
        pass

    yield "data: " + json.dumps({'done': True, 'success': success, 'fail': fail}) + "\n\n"


@app.route('/api/send', methods=['POST'])
@require_auth
def api_send():
    d          = request.json or {}
    recipients = d.get('recipients', [])
    subject    = d.get('subject', '')
    body       = d.get('body', '')
    return Response(
        stream_with_context(send_emails_stream(recipients, subject, body)),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
    )


    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
