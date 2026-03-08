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

def seed_sent_history():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE) as f:
                existing = json.load(f)
            if existing: return
    except Exception: pass
    if os.path.exists(SEED_SENT_FILE):
        import shutil
        shutil.copy(SEED_SENT_FILE, SENT_FILE)

seed_sent_history()

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
def save_config(d): save_json(CONFIG_FILE, d)

def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('authed'):
            if request.is_json or 'text/event' in request.headers.get('Accept',''):
                return jsonify({'error':'unauthorized'}), 401
            return redirect('/login')
        return f(*args, **kwargs)
    return wrapper

SP_LABELS = {
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

SPECIALTY_KEYWORDS = {
    'character_artist': {
        'strong': ["character artist", "character design", "zbrush sculpt", "creature design", "character modeling", "character sculpt", "character portfolio", "npc design", "humanoid", "character art"],
        'weak':   ["sculpt", "anatomy", "figure", "portrait", "creature", "character", "bust", "stylized", "zbrush", "skin", "face"],
    },
    'texture_artist': {
        'strong': ["texture artist", "substance painter", "pbr texturing", "material artist", "texturing portfolio", "surface artist", "texture painting", "substance designer", "material creation", "quixel", "megascans", "udim", "tileable", "mari"],
        'weak':   ["pbr", "texture", "material", "albedo", "roughness", "normal map", "bake", "baking", "surfacing", "texel"],
    },
    'environment_artist': {
        'strong': ["environment artist", "env artist", "environment art", "level art", "world building", "environment design", "landscape artist", "terrain artist", "prop artist", "environment portfolio", "archviz", "architectural visualization"],
        'weak':   ["environment", "landscape", "terrain", "foliage", "prop", "modular", "kitbash", "diorama", "biome", "exterior", "interior", "scene"],
    },
    'vfx_artist': {
        'strong': ["vfx artist", "visual effects", "houdini fx", "fx artist", "destruction fx", "simulation artist", "fluid simulation", "pyro fx", "vfx portfolio", "compositor", "nuke compositing", "vfx breakdown"],
        'weak':   ["vfx", "houdini", "simulation", "destruction", "fluid", "fire", "smoke", "explosion", "particles", "pyro", "compositing", "nuke"],
    },
    'animator': {
        'strong': ["character animator", "3d animator", "animation portfolio", "rigging artist", "motion capture", "mocap", "keyframe animation", "facial animation", "walk cycle", "animation reel", "rig artist", "animator"],
        'weak':   ["animation", "rig", "rigging", "skinning", "mocap", "keyframe", "facial", "blend shape", "bones", "weight paint"],
    },
    'motion_graphics': {
        'strong': ["motion designer", "motion graphics", "mograph", "motion design portfolio", "broadcast design", "title sequence", "logo animation", "explainer video", "kinetic typography", "after effects artist"],
        'weak':   ["motion", "c4d", "cinema 4d", "after effects", "mograph", "broadcast", "kinetic", "explainer", "loop animation"],
    },
    'technical_artist': {
        'strong': ["technical artist", "tech art", "pipeline td", "technical director", "shader artist", "hlsl", "glsl", "vex", "tool developer", "pipeline tool", "technical art portfolio"],
        'weak':   ["shader", "pipeline", "technical", "scripting", "python tool", "automation", "optimization", "lod", "performance"],
    },
    'game_developer': {
        'strong': ["game developer", "indie developer", "unity developer", "unreal developer", "game design", "indie game", "game jam", "steam game", "mobile game", "game portfolio", "game studio", "godot developer"],
        'weak':   ["unity", "unreal", "godot", "ue4", "ue5", "game", "gameplay", "indie", "steam", "mobile game", "game engine"],
    },
    '3d_generalist': {
        'strong': ["3d generalist", "freelance 3d", "3d artist", "blender artist", "maya artist", "3d visualization", "product visualization", "product render", "3d printing", "freelance render", "3d portfolio", "cgi artist", "3d modeler"],
        'weak':   ["blender", "maya", "3ds max", "freelance", "render", "visualization", "cgi", "3d", "modeler", "generalist"],
    },
    'concept_artist': {
        'strong': ["concept artist", "concept art", "visual development", "vis dev", "production designer", "storyboard artist", "concept design", "creature concept", "vehicle design", "environment concept", "digital painting"],
        'weak':   ["concept", "illustration", "digital painting", "2d", "sketching", "ideation", "storyboard", "visual development"],
    },
}

def detect_specialty_from_text(text):
    blob = text.lower()
    scores = {}
    for sp, kw in SPECIALTY_KEYWORDS.items():
        score = sum(4 for k in kw['strong'] if k in blob) + sum(1 for k in kw['weak'] if k in blob)
        if score > 0: scores[sp] = score
    return max(scores, key=scores.get) if scores else 'unknown'

def fetch_url(url, timeout=12):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/121 Safari/537.36'}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode('utf-8', errors='ignore')
    except Exception: return ''

def detect_specialty(source='', url='', text='', try_fetch=False):
    combined = ' '.join([source, url, text])
    if try_fetch and url and url.startswith('http'):
        page = fetch_url(url, timeout=10)
        if page: combined += ' ' + page[:5000]
    return detect_specialty_from_text(combined)

def extract_emails(text):
    raw = re.findall(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return list(set(raw))

SKIP_EMAILS = ['noreply','no-reply','donotreply','support@','abuse@','postmaster@','webmaster@','newsletter@','notifications@','mailer@','info@reddit','contact@reddit','admin@reddit','bounce@','unsubscribe@']

def add_lead(email, source, url='', text='', specialty=None):
    email = email.lower().strip()
    if not re.match(r'[^@]+@[^@]+\.[^@]{2,}', email): return False
    if any(s in email for s in SKIP_EMAILS): return False
    leads = load_leads()
    existing = {l['email'].lower() for l in leads}
    sent_emails = {s['email'].lower() for s in load_sent()}
    if email in existing or email in sent_emails: return False
    if specialty is None: specialty = detect_specialty(source, url, text)
    leads.append({'email':email,'source':source,'url':url,'specialty':specialty,'text':text[:400],'found_at':datetime.now().isoformat()})
    save_leads(leads)
    return True


TEMPLATES = {
    'character_artist': {
        'initial': [
            ('Your character work caught our eye — Stylarx',
             'Hey {name},\n\nCame across your character work and genuinely had to reach out — the sculpt quality and anatomy detail are seriously impressive.\n\nI run Stylarx — a platform built specifically for character artists. 140+ premium 3D assets, 10+ AI tools, one-time Founder price: $59–$149 (no subscriptions, ever).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Quick note from a fellow creator — Stylarx',
             'Hi {name},\n\nSaw your character portfolio — the range and quality really stood out.\n\nBuilding Stylarx for artists like you — premium assets, AI-powered tools, one-time Founder deal at $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers,\nStylarx'),
            ('Character artists are loving Stylarx',
             'Hey {name},\n\nYour character sculpts are incredible. Wanted to let you know about Stylarx — built specifically for 3D character artists. 140+ premium assets and 10+ AI tools.\n\nFounder launch pricing: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('The asset library built for character artists',
             'Hi {name},\n\nFound your work and immediately thought of Stylarx. We built a premium 3D asset + AI tool platform made specifically for professional character artists.\n\nFounder tier: $59–$149 lifetime (no recurring fees, ever).\n\nhttps://stylarx.app\n\nBest,\nStylarx'),
            ('Your characters deserve better tools — Stylarx',
             'Hey {name},\n\nYour character work is seriously impressive. Reaching out because Stylarx was built for artists at your level — 140+ 3D assets, AI texturing, AI concept tools.\n\nFounder pricing: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx Founder deal still open',
             'Hey {name},\n\nFollowing up on my note about Stylarx. The Founder window ($59–$149 lifetime) is still open but closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about Stylarx?',
             'Hi {name},\n\nJust checking back — Stylarx Founder deal ($59–$149 lifetime) is still live. Lots of character artists have been jumping on it lately.\n\nhttps://stylarx.app\n\nBest,\nStylarx'),
            ('Last chance — Stylarx Founder pricing',
             'Hey {name},\n\nOne last note on Stylarx. The Founder deal ($59–$149 lifetime) is wrapping up soon — after that it goes to monthly pricing.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Stylarx is getting traction — looping back',
             'Hi {name},\n\nLooping back on Stylarx — character artists specifically have been getting a ton of value from the AI texture and concept tools.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nQuick follow-up. Stylarx Founder pricing ($59–$149 lifetime) is still live for now.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'texture_artist': {
        'initial': [
            ('Your texture work is exactly what Stylarx is built for',
             'Hey {name},\n\nCame across your PBR/texture work — really clean material output. The substance workflow quality stood out immediately.\n\nI run Stylarx — we built an AI texture generation tool alongside 140+ 3D assets. Made for surface artists like you. Founder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('The AI texture tool texture artists have been asking for',
             'Hi {name},\n\nSaw your material work — top tier output. Wanted to share Stylarx — specifically our AI texture generator which surface artists have been loving.\n\nFounder deal: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx'),
            ('Built for surface and material artists — Stylarx',
             'Hey {name},\n\nYour texturing work really stood out. Stylarx has an AI texture pipeline + 140+ 3D assets built specifically for material and surface artists.\n\nFounder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Your PBR skills + Stylarx AI tools',
             'Hi {name},\n\nFound your texture portfolio — the PBR output is excellent. Our AI texture tool generates Substance-ready materials and pairs perfectly with your existing workflow.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for texture and material artists',
             'Hey {name},\n\nImpressive material work. Stylarx — AI texture tools + full 3D asset library. Founder launch: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx AI texture tools',
             'Hey {name},\n\nFollowing up on Stylarx. AI texture generator + 140+ assets still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Stylarx — still open for texture artists',
             'Hi {name},\n\nCircling back on Stylarx. The AI texture pipeline has been getting great feedback from surfacing artists.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder deal',
             'Hey {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking in on Stylarx. Built specifically for texture/material artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. AI texture tools + full asset library.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'environment_artist': {
        'initial': [
            ('Your environment art caught our eye — Stylarx',
             'Hey {name},\n\nYour environment and world-building work is excellent — the composition and atmosphere in your scenes really come through.\n\nI run Stylarx — modular 3D prop kits + AI layout tools for environment artists. Founder pricing: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('The modular kit library env artists have been waiting for',
             'Hi {name},\n\nSaw your environment/level art — really strong scene-building instincts. Stylarx has modular prop kits + AI scene tools built specifically for env artists.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Built for environment and level artists — Stylarx',
             'Hey {name},\n\nYour environment work stood out immediately. Stylarx — modular 3D asset library + AI composition tools for environment and level artists.\n\nFounder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Your worlds deserve better assets — Stylarx',
             'Hi {name},\n\nFound your environment portfolio — love the world-building approach. Stylarx — 140+ modular 3D assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for environment artists',
             'Hey {name},\n\nImpressive environment and scene work. Stylarx — modular asset library + AI layout tools. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx env tools',
             'Hey {name},\n\nFollowing up on Stylarx. Modular kits + AI scene tools still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder pricing',
             'Hey {name},\n\nLast note on Stylarx — Founder deal ($59–$149 lifetime) wrapping up soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking back. Built specifically for environment artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. Modular 3D assets + AI scene tools.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'vfx_artist': {
        'initial': [
            ('Your VFX work is exactly what Stylarx is for',
             'Hey {name},\n\nCame across your VFX work — simulation quality and breakdowns are seriously impressive.\n\nI run Stylarx — 3D assets + AI tools built for VFX artists. Founder pricing: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Built for VFX and simulation artists',
             'Hi {name},\n\nSaw your VFX reel — really strong destruction and fluid work. Stylarx has assets and AI tools that speed up VFX pipeline work.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Rapid iteration tools for VFX artists — Stylarx',
             'Hey {name},\n\nYour FX work stood out. Stylarx — AI tools for rapid VFX iteration + 140+ 3D assets. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('For Houdini and VFX artists — Stylarx',
             'Hi {name},\n\nFound your VFX portfolio. Stylarx has a 3D asset library + AI tools that work well alongside Houdini and comp pipelines.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for VFX artists',
             'Hey {name},\n\nImpressive VFX work. Stylarx — AI tools + 140+ 3D assets for VFX pipelines. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx VFX tools',
             'Hey {name},\n\nFollowing up on Stylarx. Still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking back on Stylarx. Built for VFX artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'animator': {
        'initial': [
            ('Your animation work is exactly what Stylarx is for',
             'Hey {name},\n\nCame across your animation portfolio — the motion quality and character performance are really impressive.\n\nI run Stylarx — rig-ready 3D assets + AI motion tools for animators. Founder pricing: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Rig-ready assets for animators — Stylarx',
             'Hi {name},\n\nSaw your animation reel — really expressive work. Stylarx has a rig-ready 3D asset library + AI motion tools built for animators.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('The animation toolkit you have been looking for',
             'Hey {name},\n\nYour animation work stood out. Stylarx — 140+ rig-ready 3D assets + AI motion tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('For character and motion animators — Stylarx',
             "Hi {name},\n\nFound your animation portfolio. Stylarx assets are rig-ready out of the box — built for animators who don't want to wrestle with geometry.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ('Quick note for animators',
             'Hey {name},\n\nImpressive animation work. Stylarx — rig-ready assets + AI tools for animators. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx animation tools',
             'Hey {name},\n\nFollowing up on Stylarx. Rig-ready asset library still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking back. Rig-ready 3D assets + AI tools for animators. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. Rig-ready assets + motion tools.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'motion_graphics': {
        'initial': [
            ('Your motion design work caught our eye — Stylarx',
             'Hey {name},\n\nYour motion design work is fantastic — the visual rhythm, transitions, and polish are top level.\n\nI run Stylarx — 3D assets + AI tools that plug straight into Cinema 4D, Blender, and After Effects workflows. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Built for motion designers — Stylarx',
             'Hi {name},\n\nSaw your mograph work — really strong design sensibility. Stylarx has a 3D asset library that works natively with C4D and AE pipelines.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('The 3D asset toolkit motion designers need',
             'Hey {name},\n\nYour motion work stood out. Stylarx — 140+ 3D assets + AI tools built for motion designers. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('For mograph and broadcast designers — Stylarx',
             'Hi {name},\n\nFound your motion design portfolio. Stylarx is specifically built to slot into mograph pipelines.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for motion designers',
             'Hey {name},\n\nImpressive mograph work. Stylarx — 3D library + AI tools for motion designers. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx motion tools',
             'Hey {name},\n\nFollowing up on Stylarx. 3D library + AI tools for motion designers still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking back on Stylarx. Built for motion designers. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. 3D assets + motion tools.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'technical_artist': {
        'initial': [
            ('For technical artists — Stylarx',
             'Hey {name},\n\nYour technical art work is impressive — building solid pipelines and shader systems is genuinely hard to do well.\n\nI run Stylarx — pipeline-compatible 3D assets + AI tools. Founder pricing: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Pipeline-ready tools for tech artists — Stylarx',
             'Hi {name},\n\nSaw your tech art work. Stylarx has a modular 3D asset library + AI tools built to integrate with existing pipelines.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Built with technical artists in mind — Stylarx',
             'Hey {name},\n\nYour technical art portfolio stood out. Stylarx — pipeline-ready 3D assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('For shader and pipeline artists — Stylarx',
             'Hi {name},\n\nFound your tech art work. Stylarx assets are pipeline-ready and built to slot into existing tool setups.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for technical artists',
             'Hey {name},\n\nSolid technical art work. Stylarx — pipeline-ready 3D assets + AI tools. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx pipeline tools',
             'Hey {name},\n\nFollowing up on Stylarx. Pipeline-ready assets + AI tools still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking back on Stylarx. Built for technical artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'game_developer': {
        'initial': [
            ('Game-ready assets for indie devs — Stylarx',
             'Hey {name},\n\nYour game project looks great — love the indie dev hustle. Shipping your own game is genuinely hard.\n\nI run Stylarx — 140+ game-ready 3D assets + AI tools. Unity, Unreal, Godot compatible. Founder: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('The asset library indie game devs have been asking for',
             'Hi {name},\n\nSaw your game project — really solid indie production. Stylarx has 140+ game-ready assets + AI tools that save serious dev time.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Built for indie game developers — Stylarx',
             'Hey {name},\n\nYour game dev work stood out. Stylarx — 140+ Unity/Unreal/Godot-ready 3D assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Stop building assets, start building games — Stylarx',
             'Hi {name},\n\nFound your game dev work. Stylarx gives you 140+ game-ready assets so you can focus on gameplay, not asset production.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for indie developers',
             'Hey {name},\n\nSolid game dev work. Stylarx — 140+ game-ready 3D assets + AI tools. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx game assets',
             'Hey {name},\n\nFollowing up on Stylarx. 140+ game-ready assets still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still building?',
             'Hi {name},\n\nJust checking back on Stylarx. Game-ready assets for Unity/Unreal/Godot. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. 140+ game-ready assets.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    '3d_generalist': {
        'initial': [
            ('Your 3D work stood out — Stylarx',
             'Hey {name},\n\nYour 3D work is impressive — great range across modeling, texturing, and rendering.\n\nI run Stylarx — 140+ premium 3D assets + 10+ AI tools built for generalist 3D artists. Founder: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('The generalist 3D toolkit — Stylarx',
             'Hi {name},\n\nSaw your 3D portfolio — solid all-round skills. Stylarx is built for generalists who need a complete asset + AI toolkit.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Built for 3D generalists — Stylarx',
             'Hey {name},\n\nYour 3D work stood out. Stylarx — 140+ premium 3D assets + AI tools for generalist artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Everything a freelance 3D artist needs — Stylarx',
             'Hi {name},\n\nFound your 3D portfolio. Stylarx gives you a complete asset library + AI tools so you can take on more freelance work, faster.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for 3D artists',
             'Hey {name},\n\nSolid 3D work across the board. Stylarx — 140+ premium assets + AI tools. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx 3D toolkit',
             'Hey {name},\n\nFollowing up on Stylarx. 140+ assets + AI tools still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about Stylarx?',
             'Hi {name},\n\nJust checking back. Stylarx Founder: $59–$149 lifetime. 140+ assets + AI tools.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. Full 3D asset + AI toolkit.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'concept_artist': {
        'initial': [
            ('Your concept work is stunning — Stylarx',
             'Hey {name},\n\nYour concept art is exceptional — the ideation, visual development, and production quality are all top tier.\n\nI run Stylarx — 3D assets + AI tools that accelerate the concept-to-3D pipeline. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Built for concept artists — Stylarx',
             'Hi {name},\n\nSaw your concept portfolio — production design quality is excellent. Stylarx has AI concept tools + 3D library built for artists like you.\n\nFounder deal: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('AI concept tools for professional artists — Stylarx',
             'Hey {name},\n\nYour concept work stood out immediately. Stylarx — AI-powered concept and visualization tools + 140+ 3D assets. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('For concept and visual development artists',
             'Hi {name},\n\nFound your concept art portfolio. Stylarx specifically accelerates the 2D concept to 3D handoff with AI tools built for that workflow.\n\nFounder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick note for concept artists',
             'Hey {name},\n\nImpressive concept art. Stylarx — AI concept tools + 3D asset library. Founder launch: $59–$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx concept tools',
             'Hey {name},\n\nFollowing up on Stylarx. AI concept tools + assets still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still open.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx Founder',
             'Hey {name},\n\nLast note — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about Stylarx?',
             'Hi {name},\n\nJust checking back. Stylarx Founder: $59–$149 lifetime. AI concept tools + 3D assets.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
    'unknown': {
        'initial': [
            ('Your work caught our eye — Stylarx',
             'Hey {name},\n\nCame across your work and genuinely had to reach out — it really stood out.\n\nI run Stylarx — 140+ premium 3D assets and 10+ AI tools built for working artists. Founder tier: $59–$149 one-time lifetime access (no subscriptions, ever).\n\nhttps://stylarx.app\n\nBest,\nStylarx'),
            ('A quick note from Stylarx',
             'Hi {name},\n\nSaw your work — impressive stuff. Building Stylarx for serious 3D artists — premium assets + AI tools. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers,\nStylarx'),
            ('Built for 3D artists — Stylarx',
             'Hey {name},\n\nYour work stood out. Stylarx — 140+ 3D assets, 10+ AI tools, one-time Founder price of $59–$149. No subscriptions.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Found your work — wanted to share Stylarx',
             'Hi {name},\n\nFound your portfolio and thought of Stylarx. We built a premium 3D asset + AI tool platform for working artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Stylarx — for working 3D artists',
             'Hey {name},\n\nWanted to share Stylarx — 140+ 3D assets + AI tools at a one-time Founder price of $59–$149. No monthly fees.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
        'followup': [
            ('Following up — Stylarx Founder deal',
             'Hey {name},\n\nFollowing up on Stylarx. Founder pricing ($59–$149 lifetime) still open but closing soon.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Looping back on Stylarx',
             'Hi {name},\n\nCircling back — Stylarx Founder deal ($59–$149 lifetime) still available.\n\nhttps://stylarx.app'),
            ('Last note — Stylarx',
             'Hey {name},\n\nLast note on Stylarx — Founder deal ($59–$149 lifetime) closing soon. After that, monthly pricing.\n\nhttps://stylarx.app\n\n— Stylarx'),
            ('Still thinking about it?',
             'Hi {name},\n\nJust checking back on Stylarx. 140+ assets + AI tools at $59–$149 lifetime.\n\nhttps://stylarx.app'),
            ('Quick follow-up — Stylarx',
             'Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. One-time fee, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx'),
        ],
    },
}

def get_template(specialty, is_followup, index=None):
    pool = TEMPLATES.get(specialty, TEMPLATES['unknown'])
    variants = pool['followup'] if is_followup else pool['initial']
    if index is not None and 0 <= index < len(variants): return variants[index]
    return random.choice(variants)

REDDIT_SOURCES = [
    ("r/gameDevClassifieds","r/gameDevClassifieds","https://www.reddit.com/r/gameDevClassifieds/search.json?q=3d+artist&sort=new&limit=50"),
    ("r/forhire 3D","r/forhire","https://www.reddit.com/r/forhire/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/forhire texture","r/forhire","https://www.reddit.com/r/forhire/search.json?q=texture+artist&sort=new&limit=25"),
    ("r/forhire animator","r/forhire","https://www.reddit.com/r/forhire/search.json?q=animator&sort=new&limit=25"),
    ("r/forhire vfx","r/forhire","https://www.reddit.com/r/forhire/search.json?q=vfx+artist&sort=new&limit=25"),
    ("r/forhire concept","r/forhire","https://www.reddit.com/r/forhire/search.json?q=concept+artist&sort=new&limit=25"),
    ("r/blender freelance","r/blender","https://www.reddit.com/r/blender/search.json?q=freelance+commission&sort=new&limit=25"),
    ("r/3Dartists","r/3Dartists","https://www.reddit.com/r/3Dartists/search.json?q=freelance&sort=new&limit=25"),
    ("r/ZBrush","r/ZBrush","https://www.reddit.com/r/ZBrush/search.json?q=commission&sort=new&limit=25"),
    ("r/SubstancePainter","r/SubstancePainter","https://www.reddit.com/r/SubstancePainter/search.json?q=artist&sort=new&limit=25"),
    ("r/Houdini","r/Houdini","https://www.reddit.com/r/Houdini/search.json?q=freelance&sort=new&limit=25"),
    ("r/characterdesign","r/characterdesign","https://www.reddit.com/r/characterdesign/search.json?q=commission&sort=new&limit=25"),
    ("r/vfx","r/vfx","https://www.reddit.com/r/vfx/search.json?q=freelance&sort=new&limit=25"),
    ("r/gamedev","r/gamedev","https://www.reddit.com/r/gamedev/search.json?q=hiring+3d+artist&sort=new&limit=25"),
    ("r/Unity3D","r/Unity3D","https://www.reddit.com/r/Unity3D/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/unrealengine","r/unrealengine","https://www.reddit.com/r/unrealengine/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/artcommissions","r/artcommissions","https://www.reddit.com/r/artcommissions/search.json?q=3d&sort=new&limit=25"),
    ("r/indiegamedev","r/indiegamedev","https://www.reddit.com/r/indiegamedev/search.json?q=artist&sort=new&limit=25"),
    ("r/conceptart","r/conceptart","https://www.reddit.com/r/conceptart/search.json?q=freelance&sort=new&limit=25"),
    ("r/Freelance","r/Freelance","https://www.reddit.com/r/Freelance/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/Maya","r/Maya","https://www.reddit.com/r/Maya/search.json?q=freelance&sort=new&limit=25"),
    ("r/Cinema4D","r/Cinema4D","https://www.reddit.com/r/Cinema4D/search.json?q=freelance&sort=new&limit=25"),
    ("r/shaders","r/shaders","https://www.reddit.com/r/shaders/search.json?q=freelance&sort=new&limit=25"),
    ("r/lowpoly","r/lowpoly","https://www.reddit.com/r/lowpoly/search.json?q=artist&sort=new&limit=25"),
    ("r/HungryArtists","r/HungryArtists","https://www.reddit.com/r/HungryArtists/search.json?q=3d&sort=new&limit=25"),
    ("r/commissions","r/commissions","https://www.reddit.com/r/commissions/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/stylizedstation","r/stylizedstation","https://www.reddit.com/r/stylizedstation/search.json?q=artist&sort=new&limit=25"),
    ("r/daz3d","r/daz3d","https://www.reddit.com/r/daz3d/search.json?q=artist&sort=new&limit=25"),
    ("r/computergraphics","r/computergraphics","https://www.reddit.com/r/computergraphics/search.json?q=freelance&sort=new&limit=25"),
    ("r/leveldesign","r/leveldesign","https://www.reddit.com/r/leveldesign/search.json?q=artist&sort=new&limit=25"),
]

BING_QUERIES = [
    "site:gumroad.com 3d models blender artist email",
    "site:gumroad.com substance painter texture artist email",
    "site:gumroad.com character 3d zbrush email",
    "site:gumroad.com environment 3d artist email",
    "site:gumroad.com vfx houdini artist email",
    "site:gumroad.com indie game 3d assets email",
    "site:itch.io freelance 3d artist contact email",
    "site:itch.io 3d game assets developer email",
    "site:carrd.co 3d artist portfolio email",
    "site:behance.net 3d artist contact email",
    "site:behance.net character artist contact email",
    "site:behance.net texture artist contact email",
    "site:dribbble.com 3d artist contact email",
    "site:deviantart.com 3d artist commissions email",
    "site:artstation.com 3d artist available hire email",
    "site:artstation.com character artist freelance email",
    "site:artstation.com environment artist freelance email",
    "site:sketchfab.com 3d artist contact email",
    "site:cgtrader.com 3d artist contact email",
    "freelance 3d character artist for hire email",
    "freelance texture artist pbr substance hire email",
    "freelance environment artist 3d hire email",
    "freelance vfx artist houdini hire email",
    "stylized 3d artist commission open email",
    "3d animator rigger freelance email",
    "blender freelance artist portfolio email",
    "maya 3d artist freelance email",
    "zbrush sculptor character freelance email",
    "substance painter texture artist hire email",
    "unreal engine 3d artist hire email",
    "unity 3d artist freelance email",
    "houdini vfx artist freelance email",
    "cinema 4d motion graphics artist hire email",
    "concept artist freelance hire email",
    "3d product visualization artist hire email",
    "indie game dev 3d artist hire email",
    "low poly 3d artist hire email",
    "3d generalist freelance portfolio email",
]

DIRECT_SOURCES = [
    ("BlenderArtists Jobs","blenderartists","https://blenderartists.org/c/jobs/job-listings/27.json?page=1"),
    ("BlenderArtists Jobs p2","blenderartists","https://blenderartists.org/c/jobs/job-listings/27.json?page=2"),
    ("itch.io 3D free","itch.io","https://itch.io/game-assets/free/tag-3d?page=1"),
    ("itch.io 3D paid","itch.io","https://itch.io/game-assets/tag-3d?page=1"),
    ("ArtStation Jobs","artstation","https://www.artstation.com/jobs?page=1"),
    ("ArtStation Jobs p2","artstation","https://www.artstation.com/jobs?page=2"),
    ("80.lv Jobs","80.lv","https://80.lv/jobs/"),
    ("Polycount Jobs","polycount","https://polycount.com/categories/job-board"),
    ("Renderosity","renderosity","https://www.renderosity.com/marketplace/"),
    ("Sketchfab Popular","sketchfab","https://sketchfab.com/3d-models/popular?features=downloadable"),
    ("CGTrader Designers","cgtrader","https://www.cgtrader.com/designers"),
    ("TurboSquid Artists","turbosquid","https://www.turbosquid.com/Search/Artists"),
    ("GameDev.net Jobs","gamedev.net","https://www.gamedev.net/classifieds/"),
    ("ZBrushCentral","zbrushcentral","https://www.zbrushcentral.com/c/work-in-progress/"),
    ("DeviantArt 3D","deviantart","https://www.deviantart.com/tag/3dart?page=1"),
    ("DeviantArt blender","deviantart","https://www.deviantart.com/tag/blender3d?page=1"),
    ("DeviantArt character","deviantart","https://www.deviantart.com/tag/characterdesign?page=1"),
    ("Behance 3D","behance","https://www.behance.net/search/projects?field=3d-modeling"),
    ("Behance character","behance","https://www.behance.net/search/projects?field=character-design"),
    ("OpenGameArt","opengameart","https://opengameart.org/art-search-advanced?keys=&field_art_type_tid[]=9"),
    ("Fiverr 3D","fiverr","https://www.fiverr.com/search/gigs?query=3d+artist"),
    ("Upwork 3D","upwork","https://www.upwork.com/search/profiles/?q=3d+artist"),
    ("SideFX Forum","sidefx","https://www.sidefx.com/forum/topic/houdini-lounge/"),
    ("Unity Forum Jobs","unity","https://forum.unity.com/forums/jobs-offerings.22/"),
    ("TIGSource","tigsource","https://forums.tigsource.com/index.php?board=10.0"),
    ("Dribbble 3D","dribbble","https://dribbble.com/tags/3d"),
    ("Dribbble character","dribbble","https://dribbble.com/tags/character_design"),
    ("Fab.com","fab.com","https://www.fab.com/listings?category=3d-assets&sort_by=-created_at"),
]

scrape_progress = {"running":False,"log":[],"found":0,"total_sources":0,"done_sources":0}
scrape_lock = threading.Lock()

def slog(msg):
    with scrape_lock:
        scrape_progress["log"].append({"time":datetime.now().strftime("%H:%M:%S"),"msg":msg})

def run_scrape(selected_sources):
    with scrape_lock:
        scrape_progress.update({"running":True,"log":[],"found":0,"done_sources":0,"total_sources":len(selected_sources)})
    found_total = 0
    for src_key in selected_sources:
        if not scrape_progress["running"]: break
        try:
            if src_key.startswith("reddit_"):
                idx = int(src_key.split("_")[1])
                if idx < len(REDDIT_SOURCES):
                    label,sname,url = REDDIT_SOURCES[idx]
                    slog(f"Scanning {label}...")
                    html = fetch_url(url)
                    if html:
                        try:
                            data = json.loads(html)
                            for post in data.get("data",{}).get("children",[]):
                                pd = post.get("data",{})
                                text = pd.get("selftext","") + " " + pd.get("title","")
                                post_url = pd.get("url","")
                                sp = detect_specialty_from_text(label+" "+text)
                                if sp == "unknown" and post_url and post_url.startswith("http"):
                                    page = fetch_url(post_url, timeout=8)
                                    if page: sp = detect_specialty_from_text(text+" "+page[:3000])
                                for e in extract_emails(text):
                                    if add_lead(e, label, post_url, text, specialty=sp):
                                        found_total += 1
                                        slog(f"Found: {e} [{SP_LABELS.get(sp,sp)}]")
                        except Exception: pass
                    time.sleep(random.uniform(1.5,3.0))
            elif src_key.startswith("bing_"):
                idx = int(src_key.split("_")[1])
                if idx < len(BING_QUERIES):
                    query = BING_QUERIES[idx]
                    url = "https://www.bing.com/search?q="+urllib.parse.quote(query)+"&count=20"
                    slog(f"Searching: {query[:55]}...")
                    html = fetch_url(url)
                    sp = detect_specialty_from_text(query+" "+html[:3000])
                    for e in extract_emails(html):
                        if add_lead(e,"Bing Search",url,query,specialty=sp):
                            found_total += 1
                            slog(f"Found: {e}")
                    time.sleep(random.uniform(2.0,4.0))
            elif src_key.startswith("direct_"):
                idx = int(src_key.split("_")[1])
                if idx < len(DIRECT_SOURCES):
                    label,sname,url = DIRECT_SOURCES[idx]
                    slog(f"Scanning {label}...")
                    html = fetch_url(url)
                    sp = detect_specialty_from_text(label+" "+html[:4000])
                    for e in extract_emails(html):
                        if add_lead(e,label,url,"",specialty=sp):
                            found_total += 1
                            slog(f"Found: {e}")
                    time.sleep(random.uniform(2.0,4.0))
        except Exception as ex:
            slog(f"Error: {str(ex)[:60]}")
        with scrape_lock:
            scrape_progress["done_sources"] += 1
            scrape_progress["found"] = found_total
    slog(f"Done — {found_total} new emails found.")
    with scrape_lock:
        scrape_progress["running"] = False

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

@app.route("/api/stats")
@require_auth
def api_stats():
    leads = load_leads(); sent = load_sent()
    today = date.today().isoformat()
    sent_today = sum(1 for s in sent if s.get("sent_at","").startswith(today))
    opens = sum(1 for s in sent if s.get("opened"))
    open_rate = round(opens/len(sent)*100,1) if sent else 0
    sp_leads = {}
    for l in leads:
        sp = l.get("specialty","unknown"); sp_leads[sp] = sp_leads.get(sp,0)+1
    return jsonify({"total_leads":len(leads),"total_sent":len(sent),"sent_today":sent_today,"open_rate":open_rate,"opens":opens,"sp_leads":sp_leads})

@app.route("/api/templates")
@require_auth
def api_templates():
    leads = load_leads()
    sent_emails = {s["email"].lower() for s in load_sent()}
    sp_counts = {}
    for l in leads:
        if l["email"].lower() not in sent_emails:
            sp = l.get("specialty","unknown"); sp_counts[sp] = sp_counts.get(sp,0)+1
    result = []
    for sp, pool in TEMPLATES.items():
        count = sp_counts.get(sp,0)
        result.append({
            "specialty": sp, "label": SP_LABELS.get(sp,sp), "count": count,
            "initial": [{"subject":s,"body":b} for s,b in pool["initial"]],
            "followup": [{"subject":s,"body":b} for s,b in pool["followup"]],
        })
    result.sort(key=lambda x: -x["count"])
    return jsonify(result)

@app.route("/api/sources")
@require_auth
def api_sources():
    return jsonify({
        "reddit":[{"key":f"reddit_{i}","label":r[0],"source":r[1]} for i,r in enumerate(REDDIT_SOURCES)],
        "bing":  [{"key":f"bing_{i}",  "label":q[:55],"source":"bing"} for i,q in enumerate(BING_QUERIES)],
        "direct":[{"key":f"direct_{i}","label":d[0],"source":d[1]} for i,d in enumerate(DIRECT_SOURCES)],
    })

@app.route("/api/scrape", methods=["POST"])
@require_auth
def api_scrape():
    if scrape_progress["running"]: return jsonify({"error":"Already running"}),409
    selected = (request.json or {}).get("sources",[])
    if not selected: return jsonify({"error":"No sources selected"}),400
    threading.Thread(target=run_scrape,args=(selected,),daemon=True).start()
    return jsonify({"ok":True})

@app.route("/api/scrape/progress")
@require_auth
def api_scrape_progress():
    with scrape_lock: return jsonify(dict(scrape_progress))

@app.route("/api/scrape/stop", methods=["POST"])
@require_auth
def api_scrape_stop():
    with scrape_lock: scrape_progress["running"] = False
    return jsonify({"ok":True})

@app.route("/api/leads")
@require_auth
def api_leads():
    leads = load_leads()
    sent_emails = {s["email"].lower() for s in load_sent()}
    for l in leads: l["sent"] = l["email"].lower() in sent_emails
    return jsonify(leads)

@app.route("/api/leads/reclassify", methods=["POST"])
@require_auth
def api_reclassify():
    leads = load_leads(); changed = 0
    for lead in leads:
        old = lead.get("specialty","unknown")
        url = lead.get("url",""); text = lead.get("text",""); source = lead.get("source","")
        combined = source+" "+url+" "+text
        if url and any(x in url for x in ["artstation","behance","gumroad","itch.io","carrd","dribbble","deviantart","sketchfab"]):
            page = fetch_url(url, timeout=8)
            if page: combined += " "+page[:5000]
        new_sp = detect_specialty_from_text(combined)
        if old != new_sp: lead["specialty"] = new_sp; changed += 1
    save_leads(leads)
    return jsonify({"changed":changed,"total":len(leads)})

@app.route("/api/leads/clear", methods=["POST"])
@require_auth
def api_leads_clear():
    save_leads([]); return jsonify({"ok":True})

@app.route("/api/leads/delete", methods=["POST"])
@require_auth
def api_leads_delete():
    to_del = set(e.lower() for e in (request.json or {}).get("emails",[]))
    leads = [l for l in load_leads() if l["email"].lower() not in to_del]
    save_leads(leads)
    return jsonify({"ok":True,"remaining":len(leads)})

@app.route("/api/leads/add", methods=["POST"])
@require_auth
def api_leads_add():
    emails = (request.json or {}).get("emails",[])
    added = sum(1 for e in emails if add_lead(e.strip(),"Manual Import","",""))
    return jsonify({"added":added})

@app.route("/api/config", methods=["GET"])
@require_auth
def api_get_config():
    c = load_config()
    return jsonify({k:v for k,v in c.items() if k!="smtp_pass"})

@app.route("/api/config", methods=["POST"])
@require_auth
def api_save_config():
    c = load_config(); c.update(request.json or {}); save_config(c)
    return jsonify({"ok":True})

@app.route("/api/sent")
@require_auth
def api_sent():
    return jsonify(load_sent())

def send_stream(recipients, subj_override, body_override, is_followup, tmpl_index=None):
    cfg = load_config()
    smtp_host = cfg.get("smtp_host","smtp.gmail.com")
    smtp_port = int(cfg.get("smtp_port",587))
    smtp_user = cfg.get("smtp_user","")
    smtp_pass = cfg.get("smtp_pass","")
    from_name = cfg.get("from_name","Stylarx")
    tracking_url = cfg.get("tracking_url","")
    sent_list = load_sent()
    sent_emails = {s["email"].lower() for s in sent_list}
    for item in recipients:
        email = item["email"].lower()
        specialty = item.get("specialty","unknown")
        if email in sent_emails:
            yield f"data: {json.dumps({'skip':email})}\n\n"; continue
        try:
            if subj_override and body_override:
                subj,body = subj_override,body_override
            else:
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
            with smtplib.SMTP(smtp_host,smtp_port) as s:
                s.starttls(); s.login(smtp_user,smtp_pass); s.send_message(msg)
            entry = {"email":email,"subject":subj,"sent_at":datetime.now().isoformat(),"token":token,"opened":False,"specialty":specialty,"followup":is_followup}
            sent_list.append(entry); sent_emails.add(email); save_sent(sent_list)
            leads = [l for l in load_leads() if l["email"].lower() != email]; save_leads(leads)
            yield f"data: {json.dumps({'sent':email,'specialty':specialty})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error':email,'msg':str(e)[:80]})}\n\n"
        delay = random.uniform(90,120)
        for i in range(int(delay)):
            yield f"data: {json.dumps({'wait':int(delay-i),'email':email})}\n\n"
            time.sleep(1)
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

@app.route("/api/change-password", methods=["POST"])
@require_auth
def api_change_pw():
    global APP_PASSWORD
    d = request.json or {}
    if d.get("current","") != APP_PASSWORD: return jsonify({"error":"Incorrect current password"}),400
    APP_PASSWORD = d.get("new","")
    return jsonify({"ok":True})

# ── CUSTOM TEMPLATES (saved overrides) ───────────────────────────────────────
CUSTOM_TEMPLATES_FILE = os.path.join(DATA_DIR, "custom_templates.json")

def load_custom_templates():
    return load_json(CUSTOM_TEMPLATES_FILE, {})

def save_custom_templates(d):
    save_json(CUSTOM_TEMPLATES_FILE, d)

@app.route("/api/templates/all")
@require_auth
def api_templates_all():
    """Return all templates (defaults merged with any saved custom ones)."""
    custom = load_custom_templates()
    result = []
    for sp, pool in TEMPLATES.items():
        sp_custom = custom.get(sp, {})
        initial_list = []
        for i, (subj, body) in enumerate(pool["initial"]):
            ov = sp_custom.get(f"initial_{i}", {})
            initial_list.append({
                "index": i,
                "subject": ov.get("subject", subj),
                "body": ov.get("body", body),
            })
        followup_list = []
        for i, (subj, body) in enumerate(pool["followup"]):
            ov = sp_custom.get(f"followup_{i}", {})
            followup_list.append({
                "index": i,
                "subject": ov.get("subject", subj),
                "body": ov.get("body", body),
            })
        result.append({
            "specialty": sp,
            "label": SP_LABELS.get(sp, sp),
            "initial": initial_list,
            "followup": followup_list,
        })
    return jsonify(result)

@app.route("/api/templates/save", methods=["POST"])
@require_auth
def api_templates_save():
    """Save a single template override: {specialty, type, index, subject, body}"""
    d = request.json or {}
    sp    = d.get("specialty")
    ttype = d.get("type")      # "initial" or "followup"
    idx   = d.get("index")
    subj  = d.get("subject", "")
    body  = d.get("body", "")
    if not sp or ttype not in ("initial","followup") or idx is None:
        return jsonify({"error": "Missing fields"}), 400
    custom = load_custom_templates()
    if sp not in custom:
        custom[sp] = {}
    custom[sp][f"{ttype}_{idx}"] = {"subject": subj, "body": body}
    save_custom_templates(custom)
    return jsonify({"ok": True})

@app.route("/api/templates/reset", methods=["POST"])
@require_auth
def api_templates_reset():
    """Reset a specialty back to defaults."""
    sp = (request.json or {}).get("specialty")
    custom = load_custom_templates()
    if sp and sp in custom:
        del custom[sp]
    save_custom_templates(custom)
    return jsonify({"ok": True})

@app.route("/api/followup/ready")
@require_auth
def api_followup_ready():
    """Return sent emails grouped by specialty that haven't had a followup yet."""
    sent = load_sent()
    # Only initial emails that haven't been followed up
    initial_emails = {s["email"].lower() for s in sent if not s.get("followup", False)}
    followup_emails = {s["email"].lower() for s in sent if s.get("followup", False)}
    ready = [s for s in sent if not s.get("followup", False) and s["email"].lower() not in followup_emails]
    # Deduplicate by email
    seen = set()
    deduped = []
    for s in ready:
        if s["email"].lower() not in seen:
            seen.add(s["email"].lower())
            deduped.append(s)
    sp_counts = {}
    for s in deduped:
        sp = s.get("specialty","unknown")
        sp_counts[sp] = sp_counts.get(sp,0)+1
    return jsonify({"ready": deduped, "sp_counts": sp_counts, "total": len(deduped)})

if __name__ == "__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",8080)),debug=False)
