import os, json, re, secrets
from datetime import datetime
from flask import Flask, request, jsonify, session, redirect, render_template
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=False)
