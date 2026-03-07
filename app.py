import os, json, re, time, random, smtplib, threading, uuid, hashlib, secrets
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, request, jsonify, session, redirect, render_template, Response, stream_with_context
from functools import wraps
import urllib.request, urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(DATA_DIR, exist_ok=True)

LEADS_FILE  = os.path.join(DATA_DIR, "found_leads.json")
SENT_FILE   = os.path.join(DATA_DIR, "sent.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")

APP_PASSWORD = os.environ.get("APP_PASSWORD", "stylarx2024")

# ─── scrape state ────────────────────────────────────────────────────────────
scrape_progress = {"running": False, "log": [], "found": 0, "total_sources": 0, "done_sources": 0}
scrape_lock = threading.Lock()

# ─── data helpers ────────────────────────────────────────────────────────────
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

# ─── auth ─────────────────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("authed"):
            if request.is_json or request.headers.get("Accept","").startswith("text/event"):
                return jsonify({"error":"unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# ─── specialty detection ─────────────────────────────────────────────────────
SPECIALTY_KEYWORDS = {
    "texture_artist":     ["texture","pbr","substance","material","albedo","roughness","normal map","texturing","surfacing","mari","quixel","megascans","bitmap"],
    "character_artist":   ["character","character artist","character design","zbrush","sculpt","anatomy","figure","portrait","humanoid","creature","rigging","skin","face","body","npc","hero"],
    "environment_artist": ["environment","env artist","landscape","terrain","scene","level","worldbuilding","foliage","prop","architecture","modular","kit bash","kitbash","diorama","nature"],
    "vfx_artist":         ["vfx","visual effects","houdini","nuke","compositor","compositing","simulation","destruction","fluid","fire","smoke","explosion","particles","pyro","fx artist"],
    "animator":           ["animat","rigging","rig","skinning","motion capture","mocap","keyframe","walk cycle","character animation","facial","blend shape","controller"],
    "motion_graphics":    ["motion graphic","mograph","after effects","cinema 4d","c4d","motion design","kinetic","title sequence","broadcast","loop","explainer"],
    "technical_artist":   ["technical artist","tech art","shader","hlsl","glsl","tool","pipeline","vex","python script","procedural","automation","optimiz","lod","performance"],
    "game_developer":     ["game dev","indie game","unity","unreal","godot","ue4","ue5","game design","level design","gameplay","game jam","steam","itch.io","mobile game"],
    "3d_generalist":      ["3d generalist","blender","maya","3ds max","cinema 4d","freelance 3d","3d artist","3d model","render","visualization","archviz","product viz"],
}
SPECIALTY_LABELS = {
    "texture_artist":"Texture Artist","character_artist":"Character Artist",
    "environment_artist":"Environment Artist","vfx_artist":"VFX Artist",
    "animator":"Animator","motion_graphics":"Motion Graphics",
    "technical_artist":"Technical Artist","game_developer":"Game Developer",
    "3d_generalist":"3D Generalist","unknown":"Unknown",
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
    leads = load_leads()
    existing = {l["email"] for l in leads}
    sent_emails = {s["email"] for s in load_sent()}
    if email in existing or email in sent_emails:
        return False
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False
    specialty = detect_specialty(source, url, text)
    leads.append({"email": email, "source": source, "url": url, "specialty": specialty,
                  "found_at": datetime.now().isoformat()})
    save_leads(leads)
    return True

# ─── email templates ──────────────────────────────────────────────────────────
SPECIALTY_VARIATIONS = {
    "character_artist": [
        ("Your characters deserve better assets", "Hey {name},\n\nI came across your character work and it's seriously impressive — the anatomy and detail really stand out.\n\nI run Stylarx — we make premium 3D assets and AI tools built specifically for artists like you. Right now we're doing a Founder launch at $59–$149 one-time (lifetime access, no subscriptions).\n\nIf you work in Blender, Maya, or ZBrush this might save you a ton of time on the supporting elements around your characters — environments, props, textures.\n\nWorth a look: https://stylarx.app\n\nBest,\nStylarx"),
        ("Quick note for character artists", "Hi {name},\n\nSaw your character art — the sculpt quality is excellent.\n\nBuilding Stylarx — premium 3D assets + AI tools for working artists. We just launched a Founder tier ($59–$149 lifetime) before we raise prices.\n\nCharacter artists especially love our texture packs and modular prop libraries — fills the gaps so you can focus on what you do best.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
        ("Fellow creators, quick heads up", "Hey {name},\n\nLove the character work. I'm building Stylarx — a toolkit for 3D artists (140+ assets, 10+ AI tools).\n\nFounder pricing is live: $59–$149 one-time for lifetime access.\n\nTake a look if you're curious: https://stylarx.app\n\n— Stylarx team"),
    ],
    "texture_artist": [
        ("For texture & material artists", "Hey {name},\n\nNoticed your texture/material work — really clean PBR stuff.\n\nI run Stylarx, a platform with premium 3D assets and AI-powered tools for surfacing artists. Our Founder launch is open at $59–$149 lifetime — includes our AI texture generator and full material library.\n\nhttps://stylarx.app\n\nThought it might be relevant.\n\n— Stylarx"),
        ("Your materials work is great", "Hi {name},\n\nI saw your substance/texture work — the material quality is genuinely impressive.\n\nWe're launching Stylarx (3D assets + AI tools) with a one-time Founder price ($59–$149 lifetime access). The AI texture tools in particular might be interesting for your workflow.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
        ("Quick note — new tools for material artists", "Hey {name},\n\nBuilding Stylarx — premium assets + AI tools for 3D artists. Currently running a Founder deal ($59–$149 lifetime before we raise prices).\n\nSurfacing artists have been loving the AI texture generator.\n\nhttps://stylarx.app\n\nCheers"),
    ],
    "environment_artist": [
        ("Environment art toolkit — founder deal", "Hey {name},\n\nYour environment work caught my eye — the world-building and level design is excellent.\n\nI'm building Stylarx, a platform of premium 3D assets + AI tools purpose-built for environment and level artists. Founder pricing is open right now: $59–$149 one-time lifetime access.\n\nOur modular kits and AI layout tools could seriously speed up your pipeline.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("For environment & level artists", "Hi {name},\n\nSaw your env art — the scene composition and lighting are really strong.\n\nStylarx is a 3D asset + AI tool platform for artists like you. We're in a Founder launch ($59–$149 lifetime). The modular prop library and AI terrain tools are built with environment artists in mind.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
    ],
    "vfx_artist": [
        ("VFX tools — founder pricing", "Hey {name},\n\nCame across your VFX work — the simulation quality and compositing are top-tier.\n\nI run Stylarx — 3D assets and AI tools for working VFX artists. We're running a Founder deal right now: $59–$149 one-time lifetime access.\n\nOur AI tools are particularly useful for rapid iteration on effects and comp work.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("Quick note for VFX artists", "Hi {name},\n\nImpressive VFX work. Building Stylarx — assets + AI tools for artists.\n\nFounder launch is live at $59–$149 lifetime: https://stylarx.app\n\nBest,\nStylarx"),
    ],
    "animator": [
        ("For animators — quick note", "Hey {name},\n\nYour animation work is great — the motion and character performance really come through.\n\nBuilding Stylarx — 3D assets and AI tools for animators and riggers. Founder launch is live at $59–$149 one-time lifetime access.\n\nOur AI motion tools and rig-ready asset library might be useful for your workflow.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("Animator-friendly tools — Stylarx", "Hi {name},\n\nSaw your animation work — genuinely impressive range of motion.\n\nStylarx is a 3D toolkit for working artists ($59–$149 founder lifetime deal). Rig-ready assets + AI tools.\n\nhttps://stylarx.app\n\nCheers"),
    ],
    "motion_graphics": [
        ("Motion design tools — Stylarx", "Hey {name},\n\nYour motion design work is fantastic — the visual rhythm and polish are excellent.\n\nBuilding Stylarx — 3D assets and AI tools for motion designers. Founder launch at $59–$149 lifetime is live.\n\nOur 3D asset library works great with C4D, Blender + AE pipelines.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("Quick note for motion designers", "Hi {name},\n\nGreat mograph work. Stylarx is a platform of premium 3D assets + AI tools — founder pricing at $59–$149 lifetime.\n\nhttps://stylarx.app\n\nBest"),
    ],
    "technical_artist": [
        ("Tech art pipeline tools — Stylarx", "Hey {name},\n\nYour technical art work is impressive — building tools and pipelines is genuinely hard to do well.\n\nI run Stylarx — 3D assets and AI tools for working artists. Founder pricing: $59–$149 lifetime.\n\nOur Python-compatible AI tools and modular asset library might fit well in your pipeline work.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("Quick note — Stylarx founder deal", "Hi {name},\n\nSaw your tech art work. Building Stylarx ($59–$149 founder lifetime) — 3D assets + AI tools.\n\nhttps://stylarx.app\n\nCheers"),
    ],
    "game_developer": [
        ("Game dev asset toolkit — Stylarx", "Hey {name},\n\nYour game project looks great — love the indie game dev hustle.\n\nI run Stylarx — 140+ premium 3D game-ready assets and AI tools for indie devs. We're running a Founder launch at $59–$149 one-time lifetime access (no subscriptions ever).\n\nBuilt with Unity, Unreal, and Godot workflows in mind.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("For indie game developers", "Hi {name},\n\nIndie game dev is tough — especially the art side. Stylarx has 140+ game-ready 3D assets + AI tools to speed things up.\n\nFounder deal: $59–$149 lifetime one-time: https://stylarx.app\n\nCheers,\nStylarx"),
        ("Quick note — game-ready 3D assets", "Hey {name},\n\nBuilding a game is hard enough — let Stylarx handle the asset side.\n\n140+ 3D assets, 10+ AI tools, $59–$149 lifetime founder deal.\n\nhttps://stylarx.app"),
    ],
    "3d_generalist": [
        ("3D artist toolkit — Stylarx", "Hey {name},\n\nYour 3D work is impressive — great range across modeling, texturing, and rendering.\n\nBuilding Stylarx — 140+ premium 3D assets and 10+ AI tools for generalist 3D artists. Currently running a Founder launch at $59–$149 one-time lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ("Premium 3D assets for working artists", "Hi {name},\n\nSaw your 3D work. Stylarx is a platform of premium 3D assets + AI tools — founder pricing live at $59–$149 lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
    ],
}

DEFAULT_VARIATIONS = [
    ("A quick note from Stylarx", "Hey {name},\n\nI came across your work and wanted to reach out — your 3D art really stood out to me.\n\nI run Stylarx — a platform of 140+ premium 3D assets and 10+ AI tools built for working 3D artists. We just opened our Founder tier at $59–$149 one-time (lifetime access, no subscriptions).\n\nWorth a look if you're building or creating: https://stylarx.app\n\nBest,\nStylarx"),
    ("Found your work — quick note", "Hi {name},\n\nYour work is great — I'm building Stylarx, a toolkit for 3D artists (140+ assets, 10+ AI tools). We're in a Founder launch at $59–$149 lifetime access.\n\nhttps://stylarx.app\n\nCheers,\nStylarx"),
    ("Stylarx — for 3D artists", "Hey {name},\n\nStylarx is a premium 3D asset platform + AI tools — currently doing a Founder launch at $59–$149 lifetime. Thought it might be useful for your work.\n\nhttps://stylarx.app\n\n— Stylarx"),
]

FOLLOWUP_VARIATIONS = [
    ("Following up — Stylarx", "Hey {name},\n\nJust following up on my previous note about Stylarx.\n\nWe're still in our Founder window — $59–$149 one-time lifetime access to 140+ 3D assets and 10+ AI tools. After this launch the price goes up.\n\nhttps://stylarx.app\n\nFeel free to ignore if it's not a fit — just didn't want you to miss the window.\n\n— Stylarx"),
    ("Last note — Stylarx Founder deal", "Hi {name},\n\nOne last follow-up on Stylarx. Our Founder pricing ($59–$149 lifetime) closes soon.\n\nhttps://stylarx.app\n\nEither way, keep up the great work.\n\nBest,\nStylarx"),
]

def get_variations(specialty):
    return SPECIALTY_VARIATIONS.get(specialty, DEFAULT_VARIATIONS)

# ─── scraper sources ──────────────────────────────────────────────────────────
REDDIT_SOURCES = [
    ("r/gamedev", "r/gamedev", "https://www.reddit.com/r/gamedev/search.json?q=hiring+3d+artist&sort=new&limit=25"),
    ("r/forhire", "r/forhire", "https://www.reddit.com/r/forhire/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/blender", "r/blender", "https://www.reddit.com/r/blender/search.json?q=freelance+commission&sort=new&limit=25"),
    ("r/3Dartists", "r/3Dartists", "https://www.reddit.com/r/3Dartists/search.json?q=freelance&sort=new&limit=25"),
    ("r/ZBrush", "r/ZBrush", "https://www.reddit.com/r/ZBrush/search.json?q=commission&sort=new&limit=25"),
    ("r/Maya", "r/Maya", "https://www.reddit.com/r/Maya/search.json?q=freelance&sort=new&limit=25"),
    ("r/SubstancePainter", "r/SubstancePainter", "https://www.reddit.com/r/SubstancePainter/search.json?q=artist&sort=new&limit=25"),
    ("r/Houdini", "r/Houdini", "https://www.reddit.com/r/Houdini/search.json?q=freelance&sort=new&limit=25"),
    ("r/Cinema4D", "r/Cinema4D", "https://www.reddit.com/r/Cinema4D/search.json?q=freelance&sort=new&limit=25"),
    ("r/lowpoly", "r/lowpoly", "https://www.reddit.com/r/lowpoly/search.json?q=artist&sort=new&limit=25"),
    ("r/stylizedstation", "r/stylizedstation", "https://www.reddit.com/r/stylizedstation/search.json?q=artist&sort=new&limit=25"),
    ("r/characterdesign", "r/characterdesign", "https://www.reddit.com/r/characterdesign/search.json?q=commission&sort=new&limit=25"),
    ("r/godot", "r/godot", "https://www.reddit.com/r/godot/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/vfx", "r/vfx", "https://www.reddit.com/r/vfx/search.json?q=freelance&sort=new&limit=25"),
    ("r/indiegamedev", "r/indiegamedev", "https://www.reddit.com/r/indiegamedev/search.json?q=artist&sort=new&limit=25"),
    ("r/gameDevClassifieds", "r/gameDevClassifieds", "https://www.reddit.com/r/gameDevClassifieds/search.json?q=3d&sort=new&limit=50"),
    ("r/Unity3D", "r/Unity3D", "https://www.reddit.com/r/Unity3D/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/unrealengine", "r/unrealengine", "https://www.reddit.com/r/unrealengine/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/computergraphics", "r/computergraphics", "https://www.reddit.com/r/computergraphics/search.json?q=freelance&sort=new&limit=25"),
    ("r/NFT", "r/NFT", "https://www.reddit.com/r/NFT/search.json?q=3d+artist&sort=new&limit=25"),
]

BING_QUERIES = [
    "site:gumroad.com 3d models blender artist",
    "site:gumroad.com 3d assets substance painter",
    "site:gumroad.com character 3d zbrush",
    "site:gumroad.com environment 3d artist",
    "site:gumroad.com vfx houdini artist",
    "site:itch.io freelance 3d artist contact email",
    "site:itch.io 3d game assets indie developer",
    "site:carrd.co 3d artist portfolio email",
    "site:format.com 3d artist freelance hire",
    "site:deviantart.com 3d artist commissions open email",
    "site:cgsociety.org 3d artist portfolio hire",
    "freelance 3d character artist for hire email contact",
    "freelance texture artist pbr substance hire",
    "freelance environment artist 3d hire email",
    "freelance vfx artist houdini for hire",
    "stylized 3d artist commission open email",
    "hard surface 3d modeler freelance email",
    "3d animator rigger freelance email contact",
    "blender freelance artist portfolio email contact",
    "maya 3d artist freelance email contact",
    "zbrush sculptor character freelance email",
    "substance painter texture artist hire",
    "unreal engine 3d artist for hire email",
    "unity 3d artist freelance portfolio email",
    "godot indie game 3d artist hire",
]

DIRECT_SOURCES = [
    ("Blender Artists Forum p1", "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=1"),
    ("Blender Artists Forum p2", "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=2"),
    ("Blender Artists Forum p3", "blenderartists", "https://blenderartists.org/c/jobs/job-listings/27.json?page=3"),
    ("itch.io forum p1", "itch.io", "https://itch.io/search?classification=game_assets&q=3d&page=1"),
    ("itch.io forum p2", "itch.io", "https://itch.io/search?classification=game_assets&q=3d&page=2"),
    ("Polycount p1", "polycount", "https://polycount.com/categories/job-board"),
    ("ArtStation Jobs p1", "artstation", "https://www.artstation.com/jobs?page=1&specialization=3d-generalist"),
    ("ArtStation Jobs p2", "artstation", "https://www.artstation.com/jobs?page=2&specialization=character-artist"),
    ("ArtStation Jobs p3", "artstation", "https://www.artstation.com/jobs?page=3&specialization=environment-artist"),
    ("ArtStation Jobs p4", "artstation", "https://www.artstation.com/jobs?page=4&specialization=vfx-artist"),
    ("80.lv Jobs", "80.lv", "https://80.lv/jobs/"),
    ("CGSociety Jobs", "cgsociety", "https://forums.cgsociety.org/c/jobs/"),
    ("IndieDB", "indiedb", "https://www.indiedb.com/groups/3d-artists/members"),
    ("Renderosity", "renderosity", "https://www.renderosity.com/marketplace/"),
    ("Sketchfab", "sketchfab", "https://sketchfab.com/3d-models/popular?features=downloadable&sort_by=-likeCount"),
]

# ─── scraping logic ───────────────────────────────────────────────────────────
def scrape_url(url, source_name):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return ""

def extract_emails_from_text(text):
    return list(set(re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)))

def log(msg):
    with scrape_lock:
        scrape_progress["log"].append({"time": datetime.now().strftime("%H:%M:%S"), "msg": msg})

def run_scrape(selected_sources):
    global scrape_progress
    with scrape_lock:
        scrape_progress.update({"running": True, "log": [], "found": 0, "done_sources": 0, "total_sources": len(selected_sources)})

    found_total = 0

    for src_key in selected_sources:
        if src_key.startswith("reddit_"):
            idx = int(src_key.split("_")[1])
            if idx < len(REDDIT_SOURCES):
                label, source_name, url = REDDIT_SOURCES[idx]
                log(f"Scraping {label}...")
                html = scrape_url(url, label)
                if html:
                    try:
                        data = json.loads(html)
                        posts = data.get("data",{}).get("children",[])
                        for p in posts:
                            pd = p.get("data",{})
                            text = pd.get("selftext","") + " " + pd.get("title","")
                            emails = extract_emails_from_text(text)
                            for e in emails:
                                if add_lead(e, label, pd.get("url",""), text):
                                    found_total += 1
                                    log(f"✓ Found: {e}")
                    except: pass
                time.sleep(random.uniform(1.5, 3))

        elif src_key.startswith("bing_"):
            idx = int(src_key.split("_")[1])
            if idx < len(BING_QUERIES):
                query = BING_QUERIES[idx]
                enc = urllib.parse.quote(query)
                url = f"https://www.bing.com/search?q={enc}&count=20"
                log(f"Searching: {query[:50]}...")
                html = scrape_url(url, "bing")
                if html:
                    emails = extract_emails_from_text(html)
                    for e in emails:
                        if add_lead(e, "Bing Search", url, query):
                            found_total += 1
                            log(f"✓ Found: {e}")
                time.sleep(random.uniform(2, 4))

        elif src_key.startswith("direct_"):
            idx = int(src_key.split("_")[1])
            if idx < len(DIRECT_SOURCES):
                label, source_name, url = DIRECT_SOURCES[idx]
                log(f"Scraping {label}...")
                html = scrape_url(url, label)
                if html:
                    emails = extract_emails_from_text(html)
                    for e in emails:
                        if add_lead(e, label, url, ""):
                            found_total += 1
                            log(f"✓ Found: {e}")
                time.sleep(random.uniform(2, 4))

        with scrape_lock:
            scrape_progress["done_sources"] += 1
            scrape_progress["found"] = found_total

    log(f"✅ Done. Found {found_total} new leads.")
    with scrape_lock:
        scrape_progress["running"] = False

# ─── routes: auth ─────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        pw = request.form.get("password","")
        if pw == APP_PASSWORD:
            session["authed"] = True
            return redirect("/")
        return render_template("login.html", error="Incorrect password")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ─── routes: main ─────────────────────────────────────────────────────────────
@app.route("/")
@require_auth
def index():
    return render_template("index.html")

# ─── routes: dashboard data ───────────────────────────────────────────────────
@app.route("/api/stats")
@require_auth
def api_stats():
    leads = load_leads()
    sent  = load_sent()
    today = date.today().isoformat()
    sent_today = sum(1 for s in sent if s.get("sent_at","").startswith(today))
    opens = sum(1 for s in sent if s.get("opened"))
    open_rate = round(opens / len(sent) * 100, 1) if sent else 0
    sp_counts = {}
    for l in leads:
        sp = l.get("specialty","unknown")
        sp_counts[sp] = sp_counts.get(sp,0) + 1
    return jsonify({
        "total_leads": len(leads),
        "total_sent": len(sent),
        "sent_today": sent_today,
        "open_rate": open_rate,
        "opens": opens,
        "specialty_counts": sp_counts,
    })

# ─── routes: scraper ──────────────────────────────────────────────────────────
@app.route("/api/sources")
@require_auth
def api_sources():
    reddit = [{"key": f"reddit_{i}", "label": r[0], "source": r[1]} for i, r in enumerate(REDDIT_SOURCES)]
    bing   = [{"key": f"bing_{i}",   "label": q[:55], "source": "bing"} for i, q in enumerate(BING_QUERIES)]
    direct = [{"key": f"direct_{i}", "label": d[0], "source": d[1]} for i, d in enumerate(DIRECT_SOURCES)]
    return jsonify({"reddit": reddit, "bing": bing, "direct": direct})

@app.route("/api/scrape", methods=["POST"])
@require_auth
def api_scrape():
    if scrape_progress["running"]:
        return jsonify({"error": "Already running"}), 409
    data = request.json or {}
    selected = data.get("sources", [])
    if not selected:
        return jsonify({"error": "No sources selected"}), 400
    t = threading.Thread(target=run_scrape, args=(selected,), daemon=True)
    t.start()
    return jsonify({"ok": True})

@app.route("/api/scrape/progress")
@require_auth
def api_scrape_progress():
    with scrape_lock:
        return jsonify(dict(scrape_progress))

@app.route("/api/scrape/stop", methods=["POST"])
@require_auth
def api_scrape_stop():
    with scrape_lock:
        scrape_progress["running"] = False
    return jsonify({"ok": True})

# ─── routes: leads ────────────────────────────────────────────────────────────
@app.route("/api/leads")
@require_auth
def api_leads():
    leads = load_leads()
    sent_emails = {s["email"] for s in load_sent()}
    for l in leads:
        l["sent"] = l["email"] in sent_emails
    return jsonify(leads)

@app.route("/api/leads/reclassify", methods=["POST"])
@require_auth
def api_reclassify():
    changed, total = reclassify_all_leads()
    return jsonify({"changed": changed, "total": total})

@app.route("/api/leads/clear", methods=["POST"])
@require_auth
def api_leads_clear():
    save_leads([])
    return jsonify({"ok": True})

@app.route("/api/leads/delete", methods=["POST"])
@require_auth
def api_leads_delete():
    emails_to_del = set(request.json.get("emails", []))
    leads = [l for l in load_leads() if l["email"] not in emails_to_del]
    save_leads(leads)
    return jsonify({"ok": True, "remaining": len(leads)})

# ─── routes: mailer ───────────────────────────────────────────────────────────
@app.route("/api/config", methods=["GET"])
@require_auth
def api_get_config():
    c = load_config()
    return jsonify({k: v for k, v in c.items() if k != "password"})

@app.route("/api/config", methods=["POST"])
@require_auth
def api_save_config():
    c = load_config()
    data = request.json or {}
    c.update(data)
    save_config(c)
    return jsonify({"ok": True})

@app.route("/api/sent")
@require_auth
def api_sent():
    return jsonify(load_sent())

def send_emails_stream(emails_with_specialty, subject_override, body_override, is_followup):
    config = load_config()
    smtp_host = config.get("smtp_host", "smtp.gmail.com")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_pass = config.get("smtp_pass", "")
    from_name = config.get("from_name", "Stylarx")
    tracking_url = config.get("tracking_url", "")

    sent_list = load_sent()
    sent_emails = {s["email"] for s in sent_list}

    for item in emails_with_specialty:
        email = item["email"]
        specialty = item.get("specialty", "unknown")
        if email in sent_emails:
            yield f"data: {json.dumps({'skip': email})}\n\n"
            continue
        try:
            if subject_override and body_override:
                subj, body = subject_override, body_override
            elif is_followup:
                subj, body = random.choice(FOLLOWUP_VARIATIONS)
            else:
                variations = get_variations(specialty)
                subj, body = random.choice(variations)

            name = email.split("@")[0].replace(".", " ").replace("_", " ").title()
            body = body.replace("{name}", name)

            token = str(uuid.uuid4())
            if tracking_url:
                pixel = f'\n\n<img src="{tracking_url.rstrip("/")}/track/{token}" width="1" height="1" style="display:none">'
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subj
                msg["From"] = f"{from_name} <{smtp_user}>"
                msg["To"] = email
                msg.attach(MIMEText(body, "plain"))
                msg.attach(MIMEText(body.replace("\n","<br>") + pixel, "html"))
            else:
                msg = MIMEMultipart()
                msg["Subject"] = subj
                msg["From"] = f"{from_name} <{smtp_user}>"
                msg["To"] = email
                msg.attach(MIMEText(body, "plain"))

            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.starttls()
                s.login(smtp_user, smtp_pass)
                s.send_message(msg)

            entry = {"email": email, "subject": subj, "sent_at": datetime.now().isoformat(),
                     "token": token, "opened": False, "specialty": specialty, "followup": is_followup}
            sent_list.append(entry)
            sent_emails.add(email)
            save_sent(sent_list)

            yield f"data: {json.dumps({'sent': email, 'specialty': specialty})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': email, 'msg': str(e)})}\n\n"

        delay = random.uniform(90, 120)
        for i in range(int(delay)):
            yield f"data: {json.dumps({'wait': int(delay-i), 'email': email})}\n\n"
            time.sleep(1)

    yield f"data: {json.dumps({'done': True})}\n\n"

@app.route("/api/send", methods=["POST"])
@require_auth
def api_send():
    data = request.json or {}
    emails_with_specialty = data.get("emails", [])
    subject = data.get("subject","")
    body    = data.get("body","")
    is_fu   = data.get("followup", False)
    return Response(stream_with_context(send_emails_stream(emails_with_specialty, subject, body, is_fu)),
                    mimetype="text/event-stream",
                    headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.route("/track/<token>")
def track(token):
    sent_list = load_sent()
    for s in sent_list:
        if s.get("token") == token:
            s["opened"] = True
            s["opened_at"] = datetime.now().isoformat()
    save_sent(sent_list)
    pixel = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(pixel, mimetype="image/gif")

# ─── change password ──────────────────────────────────────────────────────────
@app.route("/api/change-password", methods=["POST"])
@require_auth
def api_change_pw():
    global APP_PASSWORD
    data = request.json or {}
    cur = data.get("current","")
    nw  = data.get("new","")
    if cur != APP_PASSWORD:
        return jsonify({"error":"Current password incorrect"}), 400
    APP_PASSWORD = nw
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
