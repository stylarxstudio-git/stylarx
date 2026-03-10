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
    "game_developer": {
        "initial": [
            ("Generate your game character in seconds — Stylarx",
             "Hey {name},\n\nFound your game project and had to reach out.\n\nI run Stylarx — we have an AI Character Design Generator where you describe your character and it builds it for you. RPG hero, sci-fi soldier, fantasy creature — type it in, get a design out. No drawing skills needed, no hours in ZBrush.\n\nWe also have a Sound Effect Generator. Describe any sound — footsteps on gravel, laser gun charging up, dungeon door creaking — and it generates it instantly. No more searching free SFX libraries for something that almost fits.\n\nFounder pricing: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Your game is missing this AI toolkit — Stylarx",
             "Hi {name},\n\nBuilding a game solo or with a small team means you wear every hat. Programmer, designer, artist, sound designer.\n\nStylarx has AI tools built exactly for that situation:\n\n-> Human Rig Generator: describe a character, get a rigged model ready to animate\n-> Sound Effect Generator: describe any sound, get a production-ready SFX file\n-> PBR Generator: describe a material, get game-ready textures\n\nAll in one Founder license: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Stop spending dev time on assets — Stylarx",
             "Hey {name},\n\nEvery week you spend on asset production is a week you are not designing levels, balancing mechanics, or shipping.\n\nStylarx gives indie game devs AI tools that generate what you need on demand:\n- Character designs from a text prompt\n- Sound effects from a description\n- PBR textures from a reference image or prompt\n- Rigged human models from a prompt\n\nFounder launch: $59-$149 one-time, lifetime access, no subscriptions.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx game dev tools",
             "Hey {name},\n\nLooping back about Stylarx — the AI toolkit for indie game devs I mentioned.\n\nCharacter Generator, Sound Effect Generator, Rig Generator, PBR Generator. Founder deal ($59-$149 one-time) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("One more thing — Stylarx",
             "Hi {name},\n\nForgot to mention: Stylarx also has a Sticker Generator — great for UI elements, icons, and in-game collectibles. Describe what you want, get a clean transparent PNG.\n\nStill on Founder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx Founder deal",
             "Hey {name},\n\nLast email from me. Stylarx Founder pricing ($59-$149 one-time) closes soon — after that it moves to subscription.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "environment_artist": {
        "initial": [
            ("Turn any photo into a PBR material — Stylarx",
             "Hey {name},\n\nFound your environment work and immediately thought of something we built at Stylarx.\n\nWe have an Image to PBR tool — you upload any photo (a wall, a floor, a rock face, anything) and it generates the full PBR material set: albedo, roughness, metalness, normal map, AO. Ready to drop into Unreal or Unity.\n\nWe also have a PBR Generator where you just describe a material — cracked desert ground, sun-bleached — and it builds it from scratch.\n\nFounder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The environment art toolkit built for your workflow — Stylarx",
             "Hi {name},\n\nYour environment portfolio is strong — the material work especially. I wanted to tell you about some tools we built at Stylarx that fit directly into an environment pipeline:\n\n-> Image to HDRI: drop in any photo and get a full 360 HDRI for lighting your scene\n-> Image to PBR: any photo becomes a complete PBR material set\n-> Element Generator: describe any plant, object, or texture element and get a transparent PNG — flowers, leaves, vines, moss patches\n\nFounder deal: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Generate your scene lighting and materials with AI — Stylarx",
             "Hey {name},\n\nBuilding environments means constant hunting for the right HDRI, the right materials, the right scattered elements.\n\nStylarx automates all of it:\n- Image to HDRI — any photo becomes a lighting environment\n- PBR Generator — describe a surface, get all maps\n- Element Generator — describe any plant or organic element, get a clean transparent PNG to scatter across your scene\n- Scene Stager — AI-assisted scene composition and lighting setup\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx environment tools",
             "Hey {name},\n\nLooping back about Stylarx — Image to PBR, Image to HDRI, Element Generator, PBR Generator, Scene Stager. All in one Founder license.\n\n$59-$149 one-time, still available.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The Element Generator — more detail",
             "Hi {name},\n\nWanted to be specific about the Element Generator: you type autumn oak leaf, tropical fern frond, mossy rock — and you get back a transparent PNG ready to scatter or use in your textures. No background removal, no cleanup.\n\nFounder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email. Founder pricing closes soon — $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "concept_artist": {
        "initial": [
            ("Generate character designs from your brief — Stylarx",
             "Hey {name},\n\nFound your concept work — the design thinking behind it is really clear.\n\nAt Stylarx we built a Character Design Generator where you describe a character — species, role, aesthetic, personality — and it generates design variations you can paint over, reference, or present to a client. Faster exploration, more options, same final quality.\n\nWe also have a Depth Map Generator — upload any image and get a clean depth map for compositing or 3D projection.\n\nFounder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("More design variations, faster — Stylarx",
             "Hi {name},\n\nConcept work lives and dies in the exploration phase. The more ground you cover, the better the final design tends to be.\n\nStylarx has tools that speed that up:\n\n-> Character Design Generator: describe your character and get visual options instantly\n-> Element Generator: describe any prop, creature feature, or organic element and get a transparent PNG reference\n-> Scene Stager: AI-assisted scene composition for environment and keyframe concepts\n\nAll in one Founder license: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("AI reference tools for concept pipelines — Stylarx",
             "Hey {name},\n\nYour concept portfolio is impressive — the range of subjects and design clarity are both strong.\n\nStylarx has tools that fit directly into a concept workflow:\n- Character Design Generator — describe and generate design variations\n- Scene Stager — AI scene composition for environment concepts\n- Depth Map Generator — extract depth from any reference image\n- Element Generator — transparent PNG cutouts of any described element\n\nFounder deal: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx concept tools",
             "Hey {name},\n\nLooping back about Stylarx — Character Design Generator, Element Generator, Depth Map Generator, Scene Stager. $59-$149 one-time, still on Founder pricing.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("How the Element Generator works for concept",
             "Hi {name},\n\nQuick example: you are designing a forest guardian — type twisted branch crown, bioluminescent moss patch, gnarled root claw into the Element Generator and get transparent PNGs to paint over or composite. Founder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast one. Founder pricing ($59-$149 one-time) closes soon.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "vfx_artist": {
        "initial": [
            ("Generate HDRIs and custom gobos from any image — Stylarx",
             "Hey {name},\n\nSaw your VFX work and had to reach out about a couple tools we built at Stylarx.\n\nImage to HDRI: drop in any photo — a sky, an interior, a street scene — and get a full 360 HDRI ready to light your CG elements. No more hunting HDRI libraries for something that nearly matches.\n\nGobo Generator: describe any light pattern — venetian blind shadows, forest canopy light, industrial grate — and generate a custom gobo texture for your lighting rigs.\n\nFounder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Custom gobos and HDRIs on demand — Stylarx",
             "Hi {name},\n\nYour VFX reel is strong. I wanted to tell you about Stylarx specifically because we built tools that solve real lighting problems for VFX work:\n\n-> Gobo Generator: describe any shadow pattern and generate a custom gobo — no more settling for stock textures\n-> Image to HDRI: convert any reference photo into a usable lighting environment\n-> Depth Map Generator: extract clean depth maps from any image for compositing\n-> Element Generator: generate transparent cutout elements from a description — smoke wisps, debris, organic shapes\n\nFounder deal: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The lighting toolkit VFX artists actually need — Stylarx",
             "Hey {name},\n\nMatching practical lighting in CG means constantly solving lighting puzzles — finding the right HDRI, getting the right gobo shadow, having the right matte elements.\n\nStylarx has AI tools for all of it:\n- Image to HDRI — any photo becomes a lighting environment\n- Gobo Generator — describe a shadow pattern, get a custom gobo\n- Depth Map Generator — clean depth from any reference\n- Element Generator — transparent PNG elements from a prompt\n\nFounder launch: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx VFX tools",
             "Hey {name},\n\nLooping back about Stylarx — Image to HDRI, Gobo Generator, Depth Map Generator, Element Generator. Built for VFX lighting and compositing workflows.\n\n$59-$149 one-time, Founder deal still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The Gobo Generator — more detail",
             "Hi {name},\n\nTo be specific about the Gobo Generator: you describe a light pattern in plain English — corrugated metal shadows, broken glass caustics, palm frond silhouette — and get a clean texture map back. Works in any renderer that accepts light textures.\n\nFounder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email from me. Founder pricing ($59-$149 one-time) closes soon.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "animator": {
        "initial": [
            ("Generate a rigged human model from a prompt — Stylarx",
             "Hey {name},\n\nFound your animation work — the weight and timing are genuinely great.\n\nI built a Human Rig Generator at Stylarx: describe a character — body type, proportions, style — and get back a fully rigged model ready to animate. Skip the modeling and rigging entirely and get straight to the keyframes.\n\nFounder pricing: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Skip the rigging, get to the animation — Stylarx",
             "Hi {name},\n\nYour animation reel is strong. I wanted to reach out because we built tools at Stylarx that are a direct fit for how animators work:\n\n-> Human Rig Generator: describe a character and get a production-ready rig\n-> Character Design Generator: generate character designs from a prompt to use as reference or for client approval\n-> Scene Stager: AI-assisted scene setup so you spend less time on blocking and more on performance\n\nFounder deal: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("AI tools built for animation pipelines — Stylarx",
             "Hey {name},\n\nSaw your animation work and had to reach out. Stylarx has tools that cut the setup time out of animation projects:\n- Human Rig Generator — describe a character, get a rig\n- Character Design Generator — generate design references from a prompt\n- Scene Stager — AI scene composition and layout\n\nFewer hours on setup. More hours actually animating.\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx animation tools",
             "Hey {name},\n\nLooping back about Stylarx — Human Rig Generator, Character Design Generator, Scene Stager. Founder deal ($59-$149 one-time) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The Rig Generator — how it works",
             "Hi {name},\n\nTo be specific: the Human Rig Generator takes a text description of your character, generates the model and applies a production rig — IK/FK, facial controls, hand rig. Maya and Blender compatible. Founder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast one. Founder pricing closes soon — $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "motion_graphics": {
        "initial": [
            ("Generate any element as a transparent PNG — Stylarx",
             "Hey {name},\n\nFound your motion work — the design language is really consistent and the rhythm is clean.\n\nI built an Element Generator at Stylarx: you describe any visual element — ink splash, cherry blossom petals, geometric shards, smoke wisps — and get back a transparent PNG ready to animate in After Effects. No sourcing stock, no background removal, no cleanup.\n\nFounder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("AI tools built for motion designers — Stylarx",
             "Hi {name},\n\nSaw your mograph reel — impressive output. I wanted to tell you about Stylarx specifically because we have tools that fit directly into motion workflows:\n\n-> Element Generator: describe any design element, get a clean transparent PNG\n-> Gobo Generator: describe a light texture or overlay pattern, get a custom asset\n-> Sticker Generator: generate clean vector-style stickers from a prompt — great for UI and social motion work\n-> Image to HDRI: convert any reference into a 3D lighting environment\n\nFounder deal: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Stop sourcing stock elements — generate them — Stylarx",
             "Hey {name},\n\nHow much time per project goes into hunting for the right stock element that is almost right but not quite?\n\nStylarx has an Element Generator that lets you describe exactly what you need and generates it as a transparent PNG. Holographic foil tear, retro TV static overlay, neon light leak — whatever the brief calls for, generate it in seconds.\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx motion tools",
             "Hey {name},\n\nLooping back about Stylarx — Element Generator, Gobo Generator, Sticker Generator, Image to HDRI. Built for motion design pipelines. Founder deal ($59-$149 one-time) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The Sticker Generator — quick detail",
             "Hi {name},\n\nThe Sticker Generator generates clean, cutout-style graphic elements from a text prompt. Works great for social media motion, UI animations, and icon packs. Founder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email. Founder pricing closes soon — $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "texture_artist": {
        "initial": [
            ("Turn any photo into a full PBR material — Stylarx",
             "Hey {name},\n\nFound your texture work — the material quality and PBR accuracy are really solid.\n\nWe built two tools at Stylarx I think you would use constantly: Image to PBR, which takes any photo and generates a complete PBR material set (albedo, roughness, metalness, normal, AO), and PBR Generator, which builds a full material set from a text description alone. Scratched copper with green patina — done in seconds.\n\nFounder pricing: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("PBR textures from a photo or a prompt — Stylarx",
             "Hi {name},\n\nYour texture art is clean — the roughness variation and micro-detail work especially.\n\nStylarx has two tools built specifically for texture artists:\n-> Image to PBR: upload any reference photo, get a complete PBR set ready for Substance or Unreal\n-> PBR Generator: describe any material in plain English and generate the full texture set\n\nFounder deal: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Generate complete PBR sets on demand — Stylarx",
             "Hey {name},\n\nSaw your texture portfolio. I built Stylarx partly because texture artists spend too much time building base material setups from scratch.\n\nOur Image to PBR tool turns any photo into a full production PBR set. Our PBR Generator creates one from a text prompt. Both tools together mean you can explore 10 material directions in the time it used to take to set up 1.\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx texture tools",
             "Hey {name},\n\nLooping back about Stylarx — Image to PBR and PBR Generator. Both in one Founder license at $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Image to PBR — what it actually outputs",
             "Hi {name},\n\nTo be specific: Image to PBR outputs albedo, roughness, metalness, normal map, and ambient occlusion maps — all from one source photo. Compatible with Substance, Unreal, Unity, and Blender. Founder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast one. Founder pricing closes soon — $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "technical_artist": {
        "initial": [
            ("Generate PBR materials and depth maps on demand — Stylarx",
             "Hey {name},\n\nFound your technical art work and wanted to reach out about Stylarx specifically.\n\nWe have an Image to PBR tool that converts any source photo into a complete PBR material set — all maps, production-ready, no manual baking. Useful for rapid material validation and pipeline testing without waiting on the art team.\n\nWe also have a Depth Map Generator that extracts clean depth maps from any image — handy for shader testing and material layering.\n\nFounder pricing: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("AI tools for tech art pipelines — Stylarx",
             "Hi {name},\n\nYour technical art portfolio is solid — building those systems requires understanding both sides of the pipeline at once.\n\nStylarx has tools that fit a tech art workflow:\n-> Image to PBR: convert any photo to a full PBR set for material testing\n-> PBR Generator: generate material sets from a text description\n-> Human Rig Generator: generate rigged characters from a prompt for pipeline validation\n-> Depth Map Generator: clean depth extraction from any image\n\nFounder deal: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Stop waiting on assets to test your pipeline — Stylarx",
             "Hey {name},\n\nHow much of your time goes into waiting for or fixing assets before you can validate your systems?\n\nStylarx gives you AI tools to generate test-quality assets on demand — PBR materials, rigged characters, depth maps — so you can validate pipeline changes without blocking on anyone.\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx tech art tools",
             "Hey {name},\n\nLooping back about Stylarx — Image to PBR, PBR Generator, Human Rig Generator, Depth Map Generator. Founder deal ($59-$149 one-time) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Depth Map Generator — quick detail",
             "Hi {name},\n\nThe Depth Map Generator extracts a clean, high-quality depth map from any input image — useful for material layering, parallax effects, and shader validation. Founder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email. Founder pricing closes soon — $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "3d_generalist": {
        "initial": [
            ("10 AI tools for the full 3D pipeline — Stylarx",
             "Hey {name},\n\nFound your work — the range across different disciplines is genuinely impressive.\n\nI built Stylarx for artists like you who work across the full pipeline. We have 10+ AI tools covering the whole thing: Character Design Generator, Human Rig Generator, Image to PBR, PBR Generator, Image to HDRI, Depth Map Generator, Sound Effect Generator, Element Generator, Gobo Generator, Scene Stager.\n\nOne Founder license covers everything: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("One license, every tool you need — Stylarx",
             "Hi {name},\n\nAs a 3D generalist you need different tools depending on the project. One week you need materials, the next you need a rig, the next you need scene lighting.\n\nStylarx covers all of it in one Founder license:\n- Image to PBR and PBR Generator for materials\n- Human Rig Generator for characters\n- Image to HDRI for scene lighting\n- Element Generator for transparent asset creation\n- Scene Stager for composition\n\n$59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Built for how generalists actually work — Stylarx",
             "Hey {name},\n\nYour 3D portfolio shows real breadth — modeling, texturing, lighting, all at a consistent quality level.\n\nStylarx was built for exactly that workflow. Instead of 10 different subscriptions for 10 different tools, one Founder license gives you everything: AI character generation, PBR creation, rig generation, HDRI creation, depth maps, sound effects, and more.\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx",
             "Hey {name},\n\nLooping back about Stylarx — 10+ AI tools for the full 3D pipeline, one Founder license. $59-$149 one-time, still available.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("What is inside Stylarx",
             "Hi {name},\n\nQuick breakdown of what is in the Founder license: Character Design Generator, Human Rig Generator, Image to PBR, PBR Generator, Image to HDRI, Depth Map Generator, Sound Effect Generator, Element Generator, Gobo Generator, Scene Stager. 140+ 3D assets included too.\n\n$59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email. Founder pricing ($59-$149 one-time) closes soon.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "character_artist": {
        "initial": [
            ("Generate character designs from a prompt — Stylarx",
             "Hey {name},\n\nFound your character work and had to reach out.\n\nAt Stylarx we built a Character Design Generator: describe a character in plain English — species, silhouette, personality, aesthetic — and get back design variations you can use as a starting point, client reference, or base to paint over.\n\nWe also have a Human Rig Generator that builds a fully rigged model from a text description, ready to pose and present.\n\nFounder pricing: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Speed up your character pipeline — Stylarx",
             "Hi {name},\n\nYour character work is seriously impressive — the anatomy and surface detail especially.\n\nStylarx has AI tools that fit directly into a character art workflow:\n-> Character Design Generator: describe and generate design variations instantly\n-> Human Rig Generator: go from concept to rigged model with a prompt\n-> Image to PBR: turn any skin, fabric, or armor reference photo into a full PBR set\n\nFounder deal: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("AI character tools for production artists — Stylarx",
             "Hey {name},\n\nSaw your character portfolio and thought you should know about Stylarx — we built tools specifically for character artists:\n- Character Design Generator: text prompt to character design variations\n- Human Rig Generator: text prompt to rigged character\n- Image to PBR: reference photo to complete skin and material PBR set\n\nFounder launch: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx character tools",
             "Hey {name},\n\nLooping back about Stylarx — Character Design Generator, Human Rig Generator, Image to PBR. Founder deal ($59-$149 one-time) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("The Character Design Generator — more detail",
             "Hi {name},\n\nThe Character Design Generator takes a detailed text brief and outputs design concept variations — useful for client exploration, personal projects, or as a starting reference you paint over. Founder price: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email from me. Founder pricing closes soon — $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
    "unknown": {
        "initial": [
            ("AI tools for 3D artists — Stylarx",
             "Hey {name},\n\nFound your work online and wanted to reach out about Stylarx — a platform built for 3D artists and game developers.\n\nWe have 10+ AI tools: Character Design Generator, Human Rig Generator, Image to PBR, PBR Generator, Image to HDRI, Sound Effect Generator, Element Generator, Gobo Generator, Depth Map Generator, Scene Stager. Plus 140+ 3D assets.\n\nFounder pricing: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Built for 3D artists — Stylarx",
             "Hi {name},\n\nSaw your work and wanted to reach out. I run Stylarx — AI tools and 3D assets for artists and game developers.\n\nGenerate characters, rigs, PBR materials, HDRIs, sound effects, and more — all from text prompts or image uploads. One Founder license: $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("10+ AI tools for your creative workflow — Stylarx",
             "Hey {name},\n\nQuick note about Stylarx — we built 10+ AI tools specifically for 3D artists and game developers. Everything from PBR material generation to AI character design to sound effect generation.\n\nFounder deal: $59-$149 one-time, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx",
             "Hey {name},\n\nLooping back about Stylarx — AI tools for 3D artists and game devs. Founder deal ($59-$149 one-time) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Still open — Stylarx Founder pricing",
             "Hi {name},\n\nStylarx Founder pricing ($59-$149 one-time) is still live. 10+ AI tools, 140+ 3D assets, lifetime access.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx",
             "Hey {name},\n\nLast email from me. Founder pricing closes soon — $59-$149 one-time.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
    },
}

def get_template(specialty, is_followup, index=None):
    pool = TEMPLATES.get(specialty, TEMPLATES['unknown'])
    variants = pool['followup'] if is_followup else pool['initial']
    if index is not None and 0 <= index < len(variants): return variants[index]
    return random.choice(variants)

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

@app.route("/api/leads")
@require_auth
def api_leads():
    leads = load_leads()
    sent_emails = {s["email"].lower() for s in load_sent()}
    for l in leads: l["sent"] = l["email"].lower() in sent_emails
    return jsonify(leads)

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

@app.route("/api/leads/add-specialty", methods=["POST"])
@require_auth
def api_leads_add_specialty():
    d = request.json or {}
    emails   = d.get("emails", [])
    specialty = d.get("specialty", "unknown")
    # Validate specialty
    if specialty not in SP_LABELS:
        specialty = "unknown"
    added = 0
    for raw in emails:
        email = raw.strip().lower()
        if add_lead(email, "Manual Import", "", "", specialty=specialty):
            added += 1
    return jsonify({"added": added, "specialty": specialty})

@app.route("/api/config", methods=["GET"])
@require_auth
def api_get_config():
    c = load_config()
    return jsonify({k:v for k,v in c.items() if k!="smtp_pass"})

@app.route("/api/config", methods=["POST"])
@require_auth
def api_save_config():
    c = load_config(); c.update(request.json or {}); save_json(CONFIG_FILE, c)
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
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
                s.login(smtp_user, smtp_pass); s.send_message(msg)
            entry = {"email":email,"subject":subj,"sent_at":datetime.now().isoformat(),"token":token,"opened":False,"specialty":specialty,"followup":is_followup}
            sent_list.append(entry); sent_emails.add(email); save_sent(sent_list)
            leads = [l for l in load_leads() if l["email"].lower() != email]; save_leads(leads)
            yield f"data: {json.dumps({'sent':email,'specialty':specialty})}\n\n"
            
            # FIX: Wait 1.5 minutes ONLY on success
            delay = random.uniform(90, 120)
            for i in range(int(delay)):
                yield f"data: {json.dumps({'wait':int(delay-i)})}\n\n"
                time.sleep(1)
        except Exception as e:
            # FIX: Fail immediately on error (no waiting)
            yield f"data: {json.dumps({'error':email,'msg':str(e)[:80]})}\n\n"
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
