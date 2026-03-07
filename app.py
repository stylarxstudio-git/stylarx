import os, json, re, time, random, smtplib, threading, uuid, secrets
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, session, redirect, render_template, Response, stream_with_context
from functools import wraps
import urllib.request, urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

LEADS_FILE  = os.path.join(DATA_DIR, "found_leads.json")
SENT_FILE   = os.path.join(DATA_DIR, "sent.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "stylarx2024")

scrape_progress = {"running": False, "log": [], "found": 0, "total_sources": 0, "done_sources": 0}
scrape_lock = threading.Lock()

# ── data helpers ───────────────────────────────────────────────────────────────
def load_json(path, default):
    try:
        with open(path) as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, "w") as f: json.dump(data, f, indent=2)

def load_leads():  return load_json(LEADS_FILE, [])
def save_leads(d): save_json(LEADS_FILE, d)
def load_sent():   return load_json(SENT_FILE, [])
def save_sent(d):  save_json(SENT_FILE, d)
def load_config(): return load_json(CONFIG_FILE, {})
def save_config(d):save_json(CONFIG_FILE, d)

# ── auth ───────────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("authed"):
            if request.is_json or "text/event" in request.headers.get("Accept",""):
                return jsonify({"error":"unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# ── specialty detection ────────────────────────────────────────────────────────
SPECIALTY_KEYWORDS = {
    "texture_artist":     ["texture","pbr","substance","material","albedo","roughness","normal map","texturing","surfacing","mari","quixel","megascans","bitmap","tileable","udim","bake","baking","texel"],
    "character_artist":   ["character","character artist","character design","zbrush","sculpt","anatomy","figure","portrait","humanoid","creature","skin","face","body","npc","hero","villain","bust","stylized character","realistic character"],
    "environment_artist": ["environment","env artist","landscape","terrain","scene","level","worldbuilding","foliage","prop","architecture","modular","kitbash","diorama","nature","biome","exterior","interior design 3d","set design"],
    "vfx_artist":         ["vfx","visual effects","houdini","nuke","compositor","compositing","simulation","destruction","fluid","fire","smoke","explosion","particles","pyro","fx artist","niagara","cascade","after effects vfx"],
    "animator":           ["animat","rigging","rig","skinning","motion capture","mocap","keyframe","walk cycle","character animation","facial","blend shape","controller","bones","weight painting","inverse kinematics"],
    "motion_graphics":    ["motion graphic","mograph","after effects","cinema 4d","c4d","motion design","kinetic","title sequence","broadcast","loop","explainer","infographic","logo animation"],
    "technical_artist":   ["technical artist","tech art","shader","hlsl","glsl","tool","pipeline","vex","python script","procedural","automation","optimiz","lod","performance","pipeline td","technical director"],
    "game_developer":     ["game dev","indie game","unity","unreal","godot","ue4","ue5","game design","level design","gameplay","game jam","steam","itch.io","mobile game","rpg maker","construct","gamemaker"],
    "3d_generalist":      ["3d generalist","blender","maya","3ds max","cinema 4d","freelance 3d","3d artist","3d model","render","visualization","archviz","product viz","cgi","3d printing","product render"],
    "concept_artist":     ["concept art","concept artist","concept design","illustration","digital painting","2d","sketching","ideation","production design","storyboard","visual development","vis dev"],
}

SPECIALTY_LABELS = {
    "texture_artist":"Texture Artist","character_artist":"Character Artist",
    "environment_artist":"Environment Artist","vfx_artist":"VFX Artist",
    "animator":"Animator","motion_graphics":"Motion Graphics",
    "technical_artist":"Technical Artist","game_developer":"Game Developer",
    "3d_generalist":"3D Generalist","concept_artist":"Concept Artist","unknown":"Unknown",
}

def detect_specialty(source="", url="", text=""):
    blob = " ".join([source, url, text]).lower()
    for sp, kws in SPECIALTY_KEYWORDS.items():
        if any(k in blob for k in kws):
            return sp
    return "unknown"

def reclassify_all_leads():
    leads = load_leads()
    changed = 0
    for lead in leads:
        new_sp = detect_specialty(lead.get("source",""), lead.get("url",""), lead.get("text",""))
        if lead.get("specialty") != new_sp:
            lead["specialty"] = new_sp
            changed += 1
    save_leads(leads)
    return changed, len(leads)

def add_lead(email, source, url="", text=""):
    email = email.lower().strip()
    if not re.match(r"[^@]+@[^@]+\.[^@]{2,}", email): return False
    # skip obvious non-person emails
    skip = ["noreply","no-reply","support","info@","admin@","contact@","hello@","team@","help@","abuse@","postmaster@","webmaster@","newsletter@","notifications@","mailer@","donotreply@"]
    if any(s in email for s in skip): return False
    leads = load_leads()
    existing = {l["email"].lower() for l in leads}
    sent_emails = {s["email"].lower() for s in load_sent()}
    if email in existing or email in sent_emails: return False
    specialty = detect_specialty(source, url, text)
    leads.append({"email": email, "source": source, "url": url, "specialty": specialty,
                  "text": text[:200], "found_at": datetime.now().isoformat()})
    save_leads(leads)
    return True

# ── email templates ────────────────────────────────────────────────────────────
TEMPLATES = {
    "character_artist": {
        "initial": [
            ("Your characters deserve better assets",
             "Hey {name},\n\nCame across your character work — the sculpt quality and anatomy are genuinely impressive.\n\nI run Stylarx — premium 3D assets and AI tools built for artists like you. We just launched our Founder tier at $59–$149 one-time (lifetime access, no subscriptions ever).\n\nCharacter artists love our texture packs and modular prop libraries — fills the gaps so you can stay focused on characters.\n\nWorth a look: https://stylarx.app\n\n— Stylarx"),
            ("Quick note for character artists",
             "Hi {name},\n\nSaw your character art — the detail and expression really stand out.\n\nBuilding Stylarx — premium 3D assets + AI tools for working artists. Founder tier is $59–$149 lifetime before prices go up.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
            ("Fellow creator — heads up",
             "Hey {name},\n\nLove the character work. I'm building Stylarx — 140+ 3D assets, 10+ AI tools, one-time price.\n\nFounder pricing live now: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx Founder deal",
             "Hey {name},\n\nFollowing up on my last note about Stylarx.\n\nFounder window is still open — $59–$149 one-time lifetime access to 140+ 3D assets + AI tools. Closing soon.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nOne last note on Stylarx. Founder pricing ($59–$149 lifetime) is almost done.\n\nIf you missed it: https://stylarx.app\n\nEither way, keep up the great work.\n\nBest,\nStylarx"),
            ("Still thinking about it?",
             "Hey {name},\n\nJust checking in — Stylarx Founder deal ($59–$149 lifetime) is still live but closing soon.\n\nPerfect for character artists who want a full asset + AI toolkit without recurring fees.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "texture_artist": {
        "initial": [
            ("For texture & material artists",
             "Hey {name},\n\nNoticed your texture/material work — really clean PBR output.\n\nI run Stylarx — 3D assets + AI tools including an AI texture generator built for surfacing artists. Founder launch: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Your material work is impressive",
             "Hi {name},\n\nSaw your substance/texture work — the material quality is top tier.\n\nStylarx has AI texture tools + a full 3D asset library. Founder pricing: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("New tools for texture artists",
             "Hey {name},\n\nBuilding Stylarx — AI texture generator + 140+ 3D assets. Founder deal: $59–$149 lifetime.\n\nSurfacing artists have been loving the AI texture tools specifically.\n\nhttps://stylarx.app\n\nCheers"),
        ],
        "followup": [
            ("Following up — Stylarx texture tools",
             "Hey {name},\n\nFollowing up on Stylarx. The AI texture generator + full material library is still at Founder pricing ($59–$149 lifetime) for a limited time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last chance — Stylarx Founder",
             "Hi {name},\n\nLast note on Stylarx — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still interested?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open. Built specifically for texture and material artists.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "environment_artist": {
        "initial": [
            ("Environment art toolkit — Founder deal",
             "Hey {name},\n\nYour environment work caught my eye — the world-building and composition are excellent.\n\nBuilding Stylarx — 3D assets + AI tools for environment artists. Founder pricing: $59–$149 one-time lifetime.\n\nModular kits + AI layout tools built with env artists in mind.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("For environment & level artists",
             "Hi {name},\n\nSaw your env art — scene composition and lighting are really strong.\n\nStylarx — 3D asset + AI tool platform. Founder launch: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
            ("Modular kits for env artists",
             "Hey {name},\n\nBuilding Stylarx — modular prop library + AI terrain tools for environment artists. One-time Founder price: $59–$149.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx env tools",
             "Hey {name},\n\nFollowing up on Stylarx. Modular prop library + AI layout tools at Founder pricing ($59–$149 lifetime) — still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nOne last note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Stylarx — still thinking?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still available. Built for environment artists.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "vfx_artist": {
        "initial": [
            ("VFX tools — Founder pricing",
             "Hey {name},\n\nCame across your VFX work — simulation quality and comp are top tier.\n\nBuilding Stylarx — 3D assets + AI tools for VFX artists. Founder deal: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Quick note for VFX artists",
             "Hi {name},\n\nImpressive VFX work. Stylarx — assets + AI tools for artists. Founder launch: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("Rapid iteration tools for VFX",
             "Hey {name},\n\nBuilding Stylarx — AI tools built for rapid iteration on effects and comp work. 140+ assets included. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx VFX tools",
             "Hey {name},\n\nFollowing up on Stylarx. Still at Founder pricing ($59–$149 lifetime) for now.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note on Stylarx — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Stylarx — still open",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. Built for VFX artists.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "animator": {
        "initial": [
            ("For animators — quick note",
             "Hey {name},\n\nYour animation work is excellent — motion and character performance really come through.\n\nBuilding Stylarx — rig-ready 3D assets + AI motion tools. Founder: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Rig-ready assets for animators",
             "Hi {name},\n\nSaw your animation work — impressive range of motion.\n\nStylarx — rig-ready assets + AI tools. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers"),
            ("Animation toolkit — Stylarx",
             "Hey {name},\n\nBuilding Stylarx — 140+ rig-ready 3D assets + AI motion tools for working animators. One-time Founder price: $59–$149.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx animation tools",
             "Hey {name},\n\nFollowing up on Stylarx. Rig-ready library + AI tools still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still interested in Stylarx?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open. Built for animators and riggers.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "motion_graphics": {
        "initial": [
            ("Motion design tools — Stylarx",
             "Hey {name},\n\nYour motion design work is fantastic — the visual rhythm and polish are excellent.\n\nBuilding Stylarx — 3D assets + AI tools for motion designers. Works great with C4D, Blender + AE pipelines. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("For motion designers",
             "Hi {name},\n\nGreat mograph work. Stylarx — premium 3D assets + AI tools. Founder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nBest"),
            ("Mograph asset toolkit",
             "Hey {name},\n\nBuilding Stylarx — 3D asset library that plugs straight into C4D/Blender/AE workflows. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx motion tools",
             "Hey {name},\n\nFollowing up on Stylarx. 3D library + AI tools for motion designers still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Stylarx — still open",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. Built for motion designers.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "technical_artist": {
        "initial": [
            ("Tech art pipeline tools — Stylarx",
             "Hey {name},\n\nYour technical art work is impressive — building solid pipelines is genuinely hard.\n\nBuilding Stylarx — Python-compatible AI tools + modular 3D asset library. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("For technical artists",
             "Hi {name},\n\nSaw your tech art work. Stylarx — 3D assets + AI tools. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers"),
            ("Pipeline-ready tools — Stylarx",
             "Hey {name},\n\nBuilding Stylarx — modular assets + AI tools that plug into existing pipelines. One-time Founder price: $59–$149.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx",
             "Hey {name},\n\nFollowing up on Stylarx. Pipeline-ready tools still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still thinking about Stylarx?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open. Built for technical artists.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "game_developer": {
        "initial": [
            ("Game dev asset toolkit — Stylarx",
             "Hey {name},\n\nYour game project looks great — love the indie dev hustle.\n\nI run Stylarx — 140+ game-ready 3D assets + AI tools for indie devs. Unity, Unreal, Godot compatible. Founder: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("For indie game developers",
             "Hi {name},\n\nIndie game dev is tough — especially the art side. Stylarx has 140+ game-ready assets + AI tools. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
            ("Game-ready 3D assets — Stylarx",
             "Hey {name},\n\nBuilding a game is hard enough. Stylarx handles the asset side — 140+ 3D assets, 10+ AI tools, $59–$149 founder lifetime deal.\n\nhttps://stylarx.app"),
        ],
        "followup": [
            ("Following up — Stylarx game assets",
             "Hey {name},\n\nFollowing up on Stylarx. 140+ game-ready assets still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still building?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live. Game-ready assets for Unity/Unreal/Godot.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "3d_generalist": {
        "initial": [
            ("3D artist toolkit — Stylarx",
             "Hey {name},\n\nYour 3D work is impressive — great range across modeling, texturing, and rendering.\n\nBuilding Stylarx — 140+ premium 3D assets + 10+ AI tools for generalist artists. Founder: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Premium 3D assets for working artists",
             "Hi {name},\n\nSaw your 3D work. Stylarx — premium assets + AI tools. Founder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("Stylarx — for 3D generalists",
             "Hey {name},\n\nBuilding Stylarx — 140+ 3D assets + AI tools for generalist 3D artists. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx",
             "Hey {name},\n\nFollowing up on Stylarx. Still at Founder pricing ($59–$149 lifetime) for now.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still interested?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open. 140+ assets + AI tools.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "concept_artist": {
        "initial": [
            ("For concept artists — Stylarx",
             "Hey {name},\n\nYour concept work is stunning — the ideation and visual development are top level.\n\nBuilding Stylarx — 3D assets + AI tools that speed up the 2D-to-3D pipeline for concept artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Concept art toolkit",
             "Hi {name},\n\nSaw your concept art — production quality is excellent.\n\nStylarx — AI tools + 3D library for concept artists. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers"),
            ("Quick note for concept artists",
             "Hey {name},\n\nBuilding Stylarx — AI-powered tools that accelerate concept-to-3D workflows. 140+ assets included. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx concept tools",
             "Hey {name},\n\nFollowing up on Stylarx. AI tools for concept artists still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note — Stylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still thinking about Stylarx?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open. Built for concept and visual dev artists.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "unknown": {
        "initial": [
            ("A quick note from Stylarx",
             "Hey {name},\n\nCame across your work — really stood out to me.\n\nI run Stylarx — 140+ premium 3D assets and 10+ AI tools built for working 3D artists. Founder tier: $59–$149 one-time lifetime access.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("Found your work — quick note",
             "Hi {name},\n\nYour work is great. I'm building Stylarx — 3D assets + AI tools. Founder launch: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
            ("Stylarx — for 3D artists",
             "Hey {name},\n\nStylarx — premium 3D assets + AI tools. Founder launch at $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx",
             "Hey {name},\n\nFollowing up on Stylarx. Founder pricing ($59–$149 lifetime) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hi {name},\n\nLast note on Stylarx — Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still interested?",
             "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
}

def get_template(specialty, is_followup):
    pool = TEMPLATES.get(specialty, TEMPLATES["unknown"])
    variants = pool["followup"] if is_followup else pool["initial"]
    return random.choice(variants)

# ── sources ────────────────────────────────────────────────────────────────────
REDDIT_SOURCES = [
    ("r/gamedev hiring",      "r/gamedev",           "https://www.reddit.com/r/gamedev/search.json?q=hiring+3d+artist&sort=new&limit=25"),
    ("r/forhire 3d",          "r/forhire",           "https://www.reddit.com/r/forhire/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/blender freelance",   "r/blender",           "https://www.reddit.com/r/blender/search.json?q=freelance+commission&sort=new&limit=25"),
    ("r/3Dartists",           "r/3Dartists",         "https://www.reddit.com/r/3Dartists/search.json?q=freelance&sort=new&limit=25"),
    ("r/ZBrush",              "r/ZBrush",            "https://www.reddit.com/r/ZBrush/search.json?q=commission&sort=new&limit=25"),
    ("r/Maya",                "r/Maya",              "https://www.reddit.com/r/Maya/search.json?q=freelance&sort=new&limit=25"),
    ("r/SubstancePainter",    "r/SubstancePainter",  "https://www.reddit.com/r/SubstancePainter/search.json?q=artist&sort=new&limit=25"),
    ("r/Houdini",             "r/Houdini",           "https://www.reddit.com/r/Houdini/search.json?q=freelance&sort=new&limit=25"),
    ("r/Cinema4D",            "r/Cinema4D",          "https://www.reddit.com/r/Cinema4D/search.json?q=freelance&sort=new&limit=25"),
    ("r/lowpoly",             "r/lowpoly",           "https://www.reddit.com/r/lowpoly/search.json?q=artist&sort=new&limit=25"),
    ("r/stylizedstation",     "r/stylizedstation",   "https://www.reddit.com/r/stylizedstation/search.json?q=artist&sort=new&limit=25"),
    ("r/characterdesign",     "r/characterdesign",   "https://www.reddit.com/r/characterdesign/search.json?q=commission&sort=new&limit=25"),
    ("r/godot",               "r/godot",             "https://www.reddit.com/r/godot/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/vfx",                 "r/vfx",               "https://www.reddit.com/r/vfx/search.json?q=freelance&sort=new&limit=25"),
    ("r/indiegamedev",        "r/indiegamedev",      "https://www.reddit.com/r/indiegamedev/search.json?q=artist&sort=new&limit=25"),
    ("r/gameDevClassifieds",  "r/gameDevClassifieds","https://www.reddit.com/r/gameDevClassifieds/search.json?q=3d&sort=new&limit=50"),
    ("r/Unity3D",             "r/Unity3D",           "https://www.reddit.com/r/Unity3D/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/unrealengine",        "r/unrealengine",      "https://www.reddit.com/r/unrealengine/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/computergraphics",    "r/computergraphics",  "https://www.reddit.com/r/computergraphics/search.json?q=freelance&sort=new&limit=25"),
    ("r/NFT 3d",              "r/NFT",               "https://www.reddit.com/r/NFT/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/artcommissions",      "r/artcommissions",    "https://www.reddit.com/r/artcommissions/search.json?q=3d&sort=new&limit=25"),
    ("r/HungryArtists",       "r/HungryArtists",     "https://www.reddit.com/r/HungryArtists/search.json?q=3d&sort=new&limit=25"),
    ("r/commissions",         "r/commissions",       "https://www.reddit.com/r/commissions/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/Freelance",           "r/Freelance",         "https://www.reddit.com/r/Freelance/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/conceptart",          "r/conceptart",        "https://www.reddit.com/r/conceptart/search.json?q=freelance&sort=new&limit=25"),
    ("r/learnblender",        "r/learnblender",      "https://www.reddit.com/r/learnblender/search.json?q=email&sort=new&limit=25"),
    ("r/proceduralgeneration","r/proceduralgeneration","https://www.reddit.com/r/proceduralgeneration/search.json?q=artist&sort=new&limit=25"),
    ("r/shaders",             "r/shaders",           "https://www.reddit.com/r/shaders/search.json?q=freelance&sort=new&limit=25"),
    ("r/gamedesign",          "r/gamedesign",        "https://www.reddit.com/r/gamedesign/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/VoxelGameDev",        "r/VoxelGameDev",      "https://www.reddit.com/r/VoxelGameDev/search.json?q=artist&sort=new&limit=25"),
    ("r/daz3d",               "r/daz3d",             "https://www.reddit.com/r/daz3d/search.json?q=artist&sort=new&limit=25"),
    ("r/PixelArt 3d",         "r/PixelArt",          "https://www.reddit.com/r/PixelArt/search.json?q=3d&sort=new&limit=25"),
    ("r/blenderhelp",         "r/blenderhelp",       "https://www.reddit.com/r/blenderhelp/search.json?q=freelance&sort=new&limit=25"),
    ("r/gameAssets",          "r/gameAssets",        "https://www.reddit.com/r/gameAssets/search.json?q=artist&sort=new&limit=25"),
    ("r/ImmersionArt",        "r/ImmersionArt",      "https://www.reddit.com/r/ImmersionArt/search.json?q=3d&sort=new&limit=25"),
    ("r/leveldesign",         "r/leveldesign",       "https://www.reddit.com/r/leveldesign/search.json?q=artist&sort=new&limit=25"),
    ("r/freelanceuk",         "r/freelanceuk",       "https://www.reddit.com/r/freelanceuk/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/forhire texture",     "r/forhire",           "https://www.reddit.com/r/forhire/search.json?q=texture+artist&sort=new&limit=25"),
    ("r/forhire animator",    "r/forhire",           "https://www.reddit.com/r/forhire/search.json?q=animator&sort=new&limit=25"),
    ("r/forhire vfx",         "r/forhire",           "https://www.reddit.com/r/forhire/search.json?q=vfx+artist&sort=new&limit=25"),
]

BING_QUERIES = [
    "site:gumroad.com 3d models blender artist email",
    "site:gumroad.com substance painter texture artist",
    "site:gumroad.com character 3d zbrush",
    "site:gumroad.com environment 3d artist",
    "site:gumroad.com vfx houdini artist",
    "site:gumroad.com indie game 3d assets",
    "site:gumroad.com animator rigging",
    "site:itch.io freelance 3d artist contact email",
    "site:itch.io 3d game assets indie developer",
    "site:itch.io character artist contact",
    "site:carrd.co 3d artist portfolio email",
    "site:carrd.co character artist hire",
    "site:format.com 3d artist freelance hire",
    "site:behance.net 3d artist contact email",
    "site:behance.net character artist contact",
    "site:behance.net texture artist contact",
    "site:behance.net environment artist contact",
    "site:dribbble.com 3d artist contact email",
    "site:deviantart.com 3d artist commissions open email",
    "site:deviantart.com character artist commission",
    "site:cgsociety.org 3d artist portfolio hire",
    "site:artstation.com 3d artist available hire email",
    "site:artstation.com character artist freelance",
    "site:artstation.com texture artist freelance",
    "site:sketchfab.com 3d artist contact email",
    "site:cgtrader.com 3d artist contact",
    "site:turbosquid.com artist portfolio email",
    "site:linkedin.com 3d artist freelance available",
    "freelance 3d character artist for hire email contact",
    "freelance texture artist pbr substance hire email",
    "freelance environment artist 3d hire email",
    "freelance vfx artist houdini for hire email",
    "stylized 3d artist commission open email",
    "hard surface 3d modeler freelance email",
    "3d animator rigger freelance email contact",
    "blender freelance artist portfolio email contact",
    "maya 3d artist freelance email contact",
    "zbrush sculptor character freelance email",
    "substance painter texture artist hire email",
    "unreal engine 3d artist for hire email",
    "unity 3d artist freelance portfolio email",
    "godot indie game 3d artist hire email",
    "houdini vfx artist freelance email",
    "cinema 4d motion graphics artist hire email",
    "after effects motion designer freelance email",
    "concept artist freelance hire email",
    "3d product visualization artist hire email",
    "archviz 3d artist freelance email",
    "game ready assets artist freelance email",
    "3d printing artist freelance email contact",
    "nft 3d artist commission email",
    "indie game dev artist hire email contact",
    "low poly 3d artist hire email",
    "stylized character artist commission email",
    "3d generalist freelance portfolio email contact",
    "technical artist pipeline freelance email",
    "vfx compositor freelance email contact",
    "rigging artist freelance hire email",
    "blender environment artist freelance email",
]

DIRECT_SOURCES = [
    ("BlenderArtists Jobs p1",  "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=1"),
    ("BlenderArtists Jobs p2",  "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=2"),
    ("BlenderArtists Jobs p3",  "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=3"),
    ("BlenderArtists Jobs p4",  "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=4"),
    ("itch.io assets p1",       "itch.io",        "https://itch.io/game-assets/free/tag-3d?page=1"),
    ("itch.io assets p2",       "itch.io",        "https://itch.io/game-assets/free/tag-3d?page=2"),
    ("itch.io assets p3",       "itch.io",        "https://itch.io/game-assets/free/tag-3d?page=3"),
    ("itch.io assets p4",       "itch.io",        "https://itch.io/game-assets/tag-3d?page=1"),
    ("Polycount Jobs",          "polycount",      "https://polycount.com/categories/job-board"),
    ("ArtStation Jobs p1",      "artstation",     "https://www.artstation.com/jobs?page=1"),
    ("ArtStation Jobs p2",      "artstation",     "https://www.artstation.com/jobs?page=2"),
    ("ArtStation Jobs p3",      "artstation",     "https://www.artstation.com/jobs?page=3"),
    ("ArtStation Jobs p4",      "artstation",     "https://www.artstation.com/jobs?page=4"),
    ("80.lv Jobs",              "80.lv",          "https://80.lv/jobs/"),
    ("CGSociety Forums",        "cgsociety",      "https://forums.cgsociety.org/c/jobs/"),
    ("IndieDB Artists",         "indiedb",        "https://www.indiedb.com/groups/3d-artists/members"),
    ("Renderosity Market",      "renderosity",    "https://www.renderosity.com/marketplace/"),
    ("Sketchfab Popular",       "sketchfab",      "https://sketchfab.com/3d-models/popular?features=downloadable"),
    ("CGTrader Designers",      "cgtrader",       "https://www.cgtrader.com/designers"),
    ("TurboSquid Artists",      "turbosquid",     "https://www.turbosquid.com/Search/Artists"),
    ("GameDev.net Jobs",        "gamedev.net",    "https://www.gamedev.net/classifieds/"),
    ("GameJolt Artists",        "gamejolt",       "https://gamejolt.com/games?tag=3d"),
    ("ZBrushCentral",           "zbrushcentral",  "https://www.zbrushcentral.com/c/work-in-progress/"),
    ("3DTotal Community",       "3dtotal",        "https://3dtotal.com/gallery"),
    ("DeviantArt 3D p1",        "deviantart",     "https://www.deviantart.com/tag/3dart?page=1"),
    ("DeviantArt 3D p2",        "deviantart",     "https://www.deviantart.com/tag/blender3d?page=1"),
    ("DeviantArt character",    "deviantart",     "https://www.deviantart.com/tag/characterdesign?page=1"),
    ("Behance 3D p1",           "behance",        "https://www.behance.net/search/projects?field=3d-modeling&page=1"),
    ("Behance character",       "behance",        "https://www.behance.net/search/projects?field=character-design"),
    ("Fab.com creators",        "fab.com",        "https://www.fab.com/listings?category=3d-assets&sort_by=-created_at"),
    ("OpenGameArt",             "opengameart",    "https://opengameart.org/art-search-advanced?keys=&field_art_type_tid[]=9"),
    ("Fiverr 3D artists",       "fiverr",         "https://www.fiverr.com/search/gigs?query=3d+artist"),
    ("Upwork 3D artists",       "upwork",         "https://www.upwork.com/search/profiles/?q=3d+artist"),
    ("99designs 3D",            "99designs",      "https://99designs.com/profiles/3d-designers"),
    ("PeoplePerHour 3D",        "peopleperhour",  "https://www.peopleperhour.com/freelance-jobs/design/3d-rendering"),
    ("Freelancer 3D",           "freelancer",     "https://www.freelancer.com/jobs/3d-modelling/"),
    ("Guru 3D artists",         "guru",           "https://www.guru.com/d/freelancers/l/united-states/sk/3d-modeling/"),
    ("SideFX Forum",            "sidefx",         "https://www.sidefx.com/forum/topic/houdini-lounge/"),
    ("Autodesk Community",      "autodesk",       "https://forums.autodesk.com/t5/maya-forum/bd-p/area-b201"),
    ("Unity Forum Jobs",        "unity",          "https://forum.unity.com/forums/jobs-offerings.22/"),
    ("Unreal Forum",            "unreal",         "https://forums.unrealengine.com/c/marketplace/13"),
    ("TIGSource",               "tigsource",      "https://forums.tigsource.com/index.php?board=10.0"),
    ("IndieDB members",         "indiedb",        "https://www.indiedb.com/members?sort=modificationdatetime&dir=asc"),
    ("Graphicriver authors",    "envato",         "https://graphicriver.net/3d"),
    ("Dribbble 3D",             "dribbble",       "https://dribbble.com/tags/3d"),
    ("Dribbble character",      "dribbble",       "https://dribbble.com/tags/character_design"),
    ("ArtStation Learn",        "artstation",     "https://www.artstation.com/learning"),
    ("Reallusion community",    "reallusion",     "https://forum.reallusion.com/"),
    ("DAZ3D community",         "daz3d",          "https://www.daz3d.com/forums/categories"),
]

# ── scraping ───────────────────────────────────────────────────────────────────
def scrape_url(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=14) as r:
            return r.read().decode("utf-8", errors="ignore")
    except: return ""

def extract_emails(text):
    return list(set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)))

def slog(msg):
    with scrape_lock:
        scrape_progress["log"].append({"time": datetime.now().strftime("%H:%M:%S"), "msg": msg})

def run_scrape(selected_sources):
    with scrape_lock:
        scrape_progress.update({"running": True, "log": [], "found": 0, "done_sources": 0, "total_sources": len(selected_sources)})
    found_total = 0
    for src_key in selected_sources:
        if not scrape_progress["running"]: break
        try:
            if src_key.startswith("reddit_"):
                idx = int(src_key.split("_")[1])
                if idx < len(REDDIT_SOURCES):
                    label, sname, url = REDDIT_SOURCES[idx]
                    slog(f"RECON: {label}")
                    html = scrape_url(url)
                    if html:
                        try:
                            data = json.loads(html)
                            for p in data.get("data",{}).get("children",[]):
                                pd = p.get("data",{})
                                text = pd.get("selftext","") + " " + pd.get("title","")
                                for e in extract_emails(text):
                                    if add_lead(e, label, pd.get("url",""), text):
                                        found_total += 1
                                        slog(f"TARGET ACQUIRED: {e}")
                        except: pass
                    time.sleep(random.uniform(1.5, 3))
            elif src_key.startswith("bing_"):
                idx = int(src_key.split("_")[1])
                if idx < len(BING_QUERIES):
                    query = BING_QUERIES[idx]
                    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=20"
                    slog(f"SEARCH: {query[:45]}...")
                    html = scrape_url(url)
                    for e in extract_emails(html):
                        if add_lead(e, "Bing", url, query):
                            found_total += 1
                            slog(f"TARGET ACQUIRED: {e}")
                    time.sleep(random.uniform(2, 4))
            elif src_key.startswith("direct_"):
                idx = int(src_key.split("_")[1])
                if idx < len(DIRECT_SOURCES):
                    label, sname, url = DIRECT_SOURCES[idx]
                    slog(f"DIRECT: {label}")
                    html = scrape_url(url)
                    for e in extract_emails(html):
                        if add_lead(e, label, url, ""):
                            found_total += 1
                            slog(f"TARGET ACQUIRED: {e}")
                    time.sleep(random.uniform(2, 4))
        except Exception as ex:
            slog(f"ERROR: {str(ex)[:60]}")
        with scrape_lock:
            scrape_progress["done_sources"] += 1
            scrape_progress["found"] = found_total
    slog(f"MISSION COMPLETE. {found_total} TARGETS ACQUIRED.")
    with scrape_lock:
        scrape_progress["running"] = False

# ── auth routes ────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form.get("password","") == APP_PASSWORD:
            session["authed"] = True
            return redirect("/")
        return render_template("login.html", error="ACCESS DENIED — INCORRECT PASSWORD")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@require_auth
def index():
    return render_template("index.html")

# ── api: stats ─────────────────────────────────────────────────────────────────
@app.route("/api/stats")
@require_auth
def api_stats():
    leads = load_leads()
    sent  = load_sent()
    today = date.today().isoformat()
    sent_today = sum(1 for s in sent if s.get("sent_at","").startswith(today))
    opens = sum(1 for s in sent if s.get("opened"))
    open_rate = round(opens/len(sent)*100,1) if sent else 0
    sp_leads = {}
    for l in leads:
        sp = l.get("specialty","unknown")
        sp_leads[sp] = sp_leads.get(sp,0)+1
    sp_sent = {}
    for s in sent:
        sp = s.get("specialty","unknown")
        sp_sent[sp] = sp_sent.get(sp,0)+1
    return jsonify({
        "total_leads": len(leads), "total_sent": len(sent),
        "sent_today": sent_today, "open_rate": open_rate, "opens": opens,
        "sp_leads": sp_leads, "sp_sent": sp_sent,
    })

# ── api: scraper ───────────────────────────────────────────────────────────────
@app.route("/api/sources")
@require_auth
def api_sources():
    return jsonify({
        "reddit": [{"key":f"reddit_{i}","label":r[0],"source":r[1]} for i,r in enumerate(REDDIT_SOURCES)],
        "bing":   [{"key":f"bing_{i}",  "label":q[:50],"source":"bing"} for i,q in enumerate(BING_QUERIES)],
        "direct": [{"key":f"direct_{i}","label":d[0],"source":d[1]} for i,d in enumerate(DIRECT_SOURCES)],
    })

@app.route("/api/scrape", methods=["POST"])
@require_auth
def api_scrape():
    if scrape_progress["running"]: return jsonify({"error":"Already running"}),409
    selected = (request.json or {}).get("sources",[])
    if not selected: return jsonify({"error":"No sources"}),400
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

# ── api: leads ─────────────────────────────────────────────────────────────────
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
    changed, total = reclassify_all_leads()
    return jsonify({"changed":changed,"total":total})

@app.route("/api/leads/clear", methods=["POST"])
@require_auth
def api_leads_clear():
    save_leads([])
    return jsonify({"ok":True})

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
    data = request.json or {}
    emails = data.get("emails",[])
    added = 0
    for e in emails:
        if add_lead(e.strip(), "Manual Import", "", ""):
            added += 1
    return jsonify({"added":added})

# ── api: mailer ────────────────────────────────────────────────────────────────
@app.route("/api/config", methods=["GET"])
@require_auth
def api_get_config():
    c = load_config()
    return jsonify({k:v for k,v in c.items() if k!="smtp_pass"})

@app.route("/api/config", methods=["POST"])
@require_auth
def api_save_config():
    c = load_config()
    c.update(request.json or {})
    save_config(c)
    return jsonify({"ok":True})

@app.route("/api/sent")
@require_auth
def api_sent():
    return jsonify(load_sent())

def send_stream(recipients, subj_override, body_override, is_followup):
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
                subj, body = subj_override, body_override
            else:
                subj, body = get_template(specialty, is_followup)
            name = email.split("@")[0].replace("."," ").replace("_"," ").title()
            body = body.replace("{name}", name)
            token = str(uuid.uuid4())
            if tracking_url:
                pixel = f'<img src="{tracking_url.rstrip("/")}/track/{token}" width="1" height="1" style="display:none">'
                msg = MIMEMultipart("alternative")
                msg.attach(MIMEText(body,"plain"))
                msg.attach(MIMEText(body.replace("\n","<br>")+pixel,"html"))
            else:
                msg = MIMEMultipart()
                msg.attach(MIMEText(body,"plain"))
            msg["Subject"] = subj
            msg["From"] = f"{from_name} <{smtp_user}>"
            msg["To"] = email
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.starttls(); s.login(smtp_user, smtp_pass); s.send_message(msg)
            entry = {"email":email,"subject":subj,"sent_at":datetime.now().isoformat(),
                     "token":token,"opened":False,"specialty":specialty,"followup":is_followup}
            sent_list.append(entry)
            sent_emails.add(email)
            save_sent(sent_list)
            # Remove from leads
            leads = [l for l in load_leads() if l["email"].lower() != email]
            save_leads(leads)
            yield f"data: {json.dumps({'sent':email,'specialty':specialty})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error':email,'msg':str(e)})}\n\n"
        delay = random.uniform(90,120)
        for i in range(int(delay)):
            if not scrape_progress.get("running",False):
                yield f"data: {json.dumps({'wait':int(delay-i),'email':email})}\n\n"
            time.sleep(1)
    yield f"data: {json.dumps({'done':True})}\n\n"

@app.route("/api/send", methods=["POST"])
@require_auth
def api_send():
    d = request.json or {}
    return Response(stream_with_context(send_stream(d.get("emails",[]),d.get("subject",""),d.get("body",""),d.get("followup",False))),
                    mimetype="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.route("/track/<token>")
def track(token):
    sl = load_sent()
    for s in sl:
        if s.get("token") == token:
            s["opened"] = True; s["opened_at"] = datetime.now().isoformat()
    save_sent(sl)
    return Response(b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", mimetype="image/gif")

@app.route("/api/change-password", methods=["POST"])
@require_auth
def api_change_pw():
    global APP_PASSWORD
    d = request.json or {}
    if d.get("current","") != APP_PASSWORD: return jsonify({"error":"Wrong password"}),400
    APP_PASSWORD = d.get("new","")
    return jsonify({"ok":True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)), debug=False)
