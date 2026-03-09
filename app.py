import os, json, re, time, random, smtplib, threading, uuid, secrets
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, session, redirect, render_template, Response, stream_with_context
from functools import wraps
import urllib.request, urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, 'templates'))
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

DATA_DIR = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_DIR, exist_ok=True)

LEADS_FILE  = os.path.join(DATA_DIR, 'found_leads.json')
SENT_FILE   = os.path.join(DATA_DIR, 'sent.json')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'stylarx2024')

SEED_SENT_FILE = os.path.join(BASE_DIR, 'seed_sent.json')

# ... [Keep your existing helper functions: seed_sent_history, load_json, save_json, etc.] ...
def load_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return default

def save_json(path, data):
    with open(path, 'w') as f: json.dump(data, f, indent=2)

def load_leads():   return load_json(LEADS_FILE, [])
def save_leads(d):  save_json(LEADS_FILE, d)
def load_sent():    return load_json(SENT_FILE, [])
def save_sent(d):   save_json(SENT_FILE, d)
def load_config():  return load_json(CONFIG_FILE, {})
def save_config(d): save_config(CONFIG_FILE, d)

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('authed'):
            if request.is_json or 'text/event' in request.headers.get('Accept',''):
                return jsonify({'error':'unauthorized'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper

# --- PASTE YOUR DICTIONARIES HERE (SP_LABELS, SPECIALTY_KEYWORDS, TEMPLATES) ---
# ... [INSERT YOUR LARGE DICTIONARIES HERE] ...
# ... [INSERT YOUR HELPER FUNCTIONS (detect_specialty, add_lead, get_template) HERE] ...

# ---------------------------------------------------------------------------------

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("password","") == APP_PASSWORD:
            session["authed"] = True; return redirect("/")
        return render_template("login.html", error="Incorrect password.")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/")
@require_auth
def index():
    return render_template("index.html")

# ... [Keep your existing API routes for stats, leads, config, etc.] ...
# ... [I am omitting them for brevity, but keep them in your file] ...

# ── FIXED SENDING LOGIC ────────────────────────────────────────
def send_stream(recipients, subj_override, body_override, is_followup, tmpl_index=None):
    cfg = load_config()
    smtp_host = cfg.get("smtp_host","smtp.gmail.com")
    smtp_port = int(cfg.get("smtp_port",587))
    smtp_user = cfg.get("smtp_user","")
    smtp_pass = cfg.get("smtp_pass","")
    from_name = cfg.get("from_name","Stylarx")
    tracking_url = cfg.get("tracking_url","")
    
    # Check config before starting loop
    if not smtp_user or not smtp_pass:
        yield f"data: {json.dumps({'error':'config', 'msg':'SMTP User or Password missing in Config'})}\n\n"
        yield f"data: {json.dumps({'done':True})}\n\n"
        return

    sent_list = load_sent()
    sent_emails = {s["email"].lower() for s in sent_list}
    
    for item in recipients:
        email = item["email"].lower()
        specialty = item.get("specialty","unknown")
        
        if email in sent_emails:
            yield f"data: {json.dumps({'skip':email})}\n\n"
            continue
            
        try:
            if subj_override and body_override:
                subj,body = subj_override,body_override
            else:
                # Ensure get_template is defined in your pasted section
                subj,body = get_template(specialty, is_followup, tmpl_index)
            
            name = email.split("@")[0].replace("."," ").replace("_"," ").title()
            body = body.replace("{name}", name)
            
            token = str(uuid.uuid4()).replace("-","")
            if tracking_url:
                pixel = f'<img src="{tracking_url.rstrip("/")}/track/{token}" width="1" height="1" style="display:none">'
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body,"plain"))
                msg.attach(MIMEText(body.replace("\n","<br>")+pixel,"html"))
            else:
                msg = MIMEMultipart(); msg.attach(MIMEText(body,"plain"))
            
            msg["Subject"] = subj
            msg["From"] = f"{from_name} <{smtp_user}>"
            msg["To"] = email
            
            # Attempt to send
            with smtplib.SMTP(smtp_host,smtp_port, timeout=20) as s:
                s.ehlo(); s.starttls(); s.ehlo()
                s.login(smtp_user,smtp_pass)
                s.send_message(msg)
            
            # SUCCESS
            entry = {"email":email,"subject":subj,"sent_at":datetime.now().isoformat(),"token":token,"opened":False,"specialty":specialty,"followup":is_followup}
            sent_list.append(entry); sent_emails.add(email); save_sent(sent_list)
            
            # Remove from leads
            leads = [l for l in load_leads() if l["email"].lower() != email]; save_leads(leads)
            
            yield f"data: {json.dumps({'sent':email,'specialty':specialty})}\n\n"
            
            # DELAY LOGIC: Wait 90-120s ONLY on success to protect domain
            delay = random.uniform(90, 120)
            for i in range(int(delay)):
                yield f"data: {json.dumps({'wait':int(delay-i)})}\n\n"
                time.sleep(1)

        except Exception as e:
            # ERROR: Report immediately, NO waiting
            yield f"data: {json.dumps({'error':email,'msg':str(e)[:100]})}\n\n"
            
    yield f"data: {json.dumps({'done':True})}\n\n"

@app.route("/api/send", methods=["POST"])
@require_auth
def api_send():
    d = request.json or {}
    return Response(stream_with_context(send_stream(d.get("emails",[]),d.get("subject",""),d.get("body",""),d.get("followup",False),d.get("tmpl_index"))),
        mimetype="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.route("/track/<token>")
def track(token):
    sl = load_sent()
    for s in sl:
        if s.get("token")==token: s["opened"]=True; s["opened_at"]=datetime.now().isoformat()
    save_sent(sl)
    return Response(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",mimetype="image/gif")

# ... [Keep your remaining routes like change-password, custom templates, etc.] ...

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",8080)),debug=False)