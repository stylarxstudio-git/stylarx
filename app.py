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

SEED_SENT = '[{"email": "nevan2721@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nevanghost1@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "southernshotty@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ngluongtho@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "marocsofiane20@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "blenderhub2@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "bettison.gamedesign@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "higgsasmotion@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "atomicairship108@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "chuckcg01@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "yansculpts@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jugaadanimation@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nrjnicks@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sirtaza1648@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "fablesalive@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "luc.chamerlat@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "kowalskiartwork@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "workshop.pierrebenjamin@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jhrvdesign@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "vuducblog@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "toniccbusiness@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "leartesstudios@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "interior.models.b3d@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-04T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ellimity@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sopi.iscoding@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "gazi@select.co", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nafaysaleem12@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "codeburcu.pr@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nganhphuong218@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "studio@surrealgenesis.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "starkosha3d@outlook.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ruslandelion123@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "info@vexiam.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "info@innsvx.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "contact@flexxlex.co.uk", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "josiahbout@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "manman2382@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "lilkjk2676@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "elithyajira@outlook.de", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "emmalouise@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "contact@3dvenoz.fr", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "trinspiron@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sub.sensus@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "tomsilf.creative@outlook.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sttangelina@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "wonderwell.studios@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "truebones@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "pancake.manicure@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dileepbhargav.l@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "lordczy@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "truongcgartist@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "allthingsanimationrigs@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "hectorabrahamt@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dennis.porter.3d@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jon.peel.shoesmith@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "josephsimba77@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "madlabvfx@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "guilodob@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nicolasella30@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "achung115@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "cvbtruong@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "pavel_barnev2000@mail.ru", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "yosef@blendervitals.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "info@blenderbros.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "blenderbase@gmx.de", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ryanlykos@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "shadererror.dll@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "achand833@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "maritdoodles@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "chris.cgmasters@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "plua3dart@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "3dillustrationmuseum@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "robotpencil.info@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "heymipru@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "infogdrs@yahoo.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "turnersteele7@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "worksodesign@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "arti@80.lv", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "hello@doublejumpacademy.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "tyler.bakabakagames@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "pradeep@highavenue.co", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sonderingemily@underscoretalent.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dadonik9416@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-05T12:00:00", "token": "", "opened": false, "specialty": "unknown", "followup": false}, {"email": "rscroll08@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "b41d4759b299455fba870a12dad2b8f3", "opened": false, "specialty": "unknown", "followup": false}, {"email": "syomapozdeev@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "7ad36508b8b64e679682e52072e44be9", "opened": false, "specialty": "unknown", "followup": false}, {"email": "lander@dewandel.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "82e244e34a804c15aa9e0c1cea6ce6b5", "opened": false, "specialty": "unknown", "followup": false}, {"email": "zedtix@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "04adcbd3648447739cbed50121c03751", "opened": false, "specialty": "unknown", "followup": false}, {"email": "oana.hinceanu@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "4c1b125caa4c4ed4b9b63e80e7a5d814", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sinziana.zamfir@yahoo.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ac661f7a843a43c4ad75a30aeaaf988c", "opened": false, "specialty": "unknown", "followup": false}, {"email": "riadev244@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "fc72a8613d2f4b0486d1ce266ef81f80", "opened": false, "specialty": "unknown", "followup": false}, {"email": "tomislavtomljenovic253@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "a6dd5d9649764f0b89401ec90277303f", "opened": false, "specialty": "unknown", "followup": false}, {"email": "pack1931@hotmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "eb49fdd17bc74d9f99b5a53ffc18fe30", "opened": false, "specialty": "unknown", "followup": false}, {"email": "iconstudiobiz@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "3252ed177fb8495ebf3e6fc3b0597b2e", "opened": false, "specialty": "unknown", "followup": false}, {"email": "lestdarikki@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "15c6ec555867410a9cffe42511834867", "opened": false, "specialty": "unknown", "followup": false}, {"email": "rmxttmgg@proton.me", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "98efc7144c074657a0eaf13a1fcc653a", "opened": false, "specialty": "unknown", "followup": false}, {"email": "carmarrodriguez.art12@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f0e63aafd5e743d094c28499df235832", "opened": false, "specialty": "unknown", "followup": false}, {"email": "eli@dreamhopper.games", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "853645cf6ce94c53b9839cc8fa34b641", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dave_draws@outlook.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "195dd19eaf6b43d0964e616f2212fab4", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ettawrites21@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ce483eb57b3248508a758a1838024fe6", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jayar.smellwell@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "3b53e132caa94262890129db60d757bd", "opened": false, "specialty": "unknown", "followup": false}, {"email": "apply@aandbtalent.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "3aee40bec99e43178f6d040131b933fd", "opened": false, "specialty": "unknown", "followup": false}, {"email": "tayumidraws@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "c7b213224cb84c3ea1aef418c27842fd", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ramon.bello@aandbtalent.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "d8bc4db4903b4070ae4f40a3833e915e", "opened": false, "specialty": "unknown", "followup": false}, {"email": "lucasferreira2101@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "6f61ca697706468bb6f6b8438a7f4693", "opened": false, "specialty": "unknown", "followup": false}, {"email": "alvin@studioaurora.io", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f2f4c9f7da1c45deb8670bb050603ac1", "opened": false, "specialty": "unknown", "followup": false}, {"email": "hollowstringstudios@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "4108338dfbd24f4fae1566652d2782e0", "opened": false, "specialty": "unknown", "followup": false}, {"email": "alexandre.joao.seixas@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "1cdaa3efee9e408e9c3c6d6f138a6ba4", "opened": false, "specialty": "unknown", "followup": false}, {"email": "admin@3sigma-studios.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "b1a892a03ecb4bf48bdce26fd7baef09", "opened": false, "specialty": "unknown", "followup": false}, {"email": "slimjimbojones@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "00129e6fb44b4f8ca7800d57ce06c1bc", "opened": false, "specialty": "unknown", "followup": false}, {"email": "amirezabe99@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5a3d34d9e7c4435494683fe1f828d8d6", "opened": false, "specialty": "unknown", "followup": false}, {"email": "deeprootstoken@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "67f0ab5b883749e5be90a8e0af229922", "opened": false, "specialty": "unknown", "followup": false}, {"email": "aaaaliwhite@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "6a86f6e8ab89400da9c1159378cd75db", "opened": false, "specialty": "unknown", "followup": false}, {"email": "thepaperboatfilm@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5949c2669b9e407ba389592632e97ca4", "opened": false, "specialty": "unknown", "followup": false}, {"email": "wasted.potential.chi@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f717cbdaa6824da3aaceb489b80f86f9", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jadoon.zeshan1@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "20e70c535a6c477582376fd149ebd942", "opened": false, "specialty": "unknown", "followup": false}, {"email": "fareehakashif1418@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5e328b257baf4cd18f16bd0d3c02033d", "opened": false, "specialty": "unknown", "followup": false}, {"email": "3dartist.gd@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "29e7f188a3e34bdd8ec2fe1dabe68b07", "opened": false, "specialty": "unknown", "followup": false}, {"email": "gturmanidze1993@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5b0da0f45c474cf8a779aaa13579d0e6", "opened": false, "specialty": "unknown", "followup": false}, {"email": "spacefoxcontact@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "bcb9a975842047b0ae1963110ec51556", "opened": false, "specialty": "unknown", "followup": false}, {"email": "mellodesign2323@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "bc04578564844fd2b44e232d79dd8f6f", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jisa255@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "2cc8eff18dd24833b9fb0943146e2326", "opened": false, "specialty": "unknown", "followup": false}, {"email": "bribecfox@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ae9734cca3d747e88ef645c3dc4ed2b5", "opened": false, "specialty": "unknown", "followup": false}, {"email": "mhdshora08@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f0a26311a7034d2f90969bab11422d31", "opened": false, "specialty": "unknown", "followup": false}, {"email": "bapham800@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ebd5ca9fe83e48fb8dee60e96b541929", "opened": false, "specialty": "unknown", "followup": false}, {"email": "acikelatahan@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f76d48eac58b4c91b4b64dcfe120a701", "opened": false, "specialty": "unknown", "followup": false}, {"email": "clarexbennett@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "7667f63509b7459ba45fdb1710a9f315", "opened": false, "specialty": "unknown", "followup": false}, {"email": "joao117sa@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "efd94bd9302841f98adabccd9fe490d6", "opened": false, "specialty": "unknown", "followup": false}, {"email": "iamjayy313@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ab4c9b033dcb4c3a95f2f4d690677fa3", "opened": false, "specialty": "unknown", "followup": false}, {"email": "divya@steloramedia.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5b405cdcd7b7434f97a82eb0e428fb9b", "opened": false, "specialty": "unknown", "followup": false}, {"email": "info@toolkaiser.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f22131ee70cb4c7bbca66e3b53f90fb7", "opened": false, "specialty": "unknown", "followup": false}, {"email": "marcodeveloper167@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "e183b3183d9f4d948aff2b563b65391f", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jgrohit.exe@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "371e22d86d294a3597fab8d6d20c2448", "opened": false, "specialty": "unknown", "followup": false}, {"email": "saadiya.dev@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "8f07a2ee8e944e14a15a22e2228d7b49", "opened": false, "specialty": "unknown", "followup": false}, {"email": "arhum6622@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "7d3338f1f09d4b419563b0aa34d7ab79", "opened": false, "specialty": "unknown", "followup": false}, {"email": "itsmohamedtriki@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "08f954aa66694f198b22080f42a1b75b", "opened": false, "specialty": "unknown", "followup": false}, {"email": "rjgoodman@techinterviewers.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ce7b19c547c0424683188c2771e2e600", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ayisha.ambianz@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ab1f4ceb374741d9a67c464623dc6bfd", "opened": false, "specialty": "unknown", "followup": false}, {"email": "hlairalex@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "299f74e348d54512a41c401a9c67f101", "opened": false, "specialty": "unknown", "followup": false}, {"email": "onealjack9797@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "c5b315aae16144b59760714be911f6c5", "opened": false, "specialty": "unknown", "followup": false}, {"email": "morganhmjames@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "78edcf0de3b144deb4433cc0692f075d", "opened": false, "specialty": "unknown", "followup": false}, {"email": "largeladsstudio@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "b0841fbb0e8a4ffd94546533d52a305e", "opened": false, "specialty": "unknown", "followup": false}, {"email": "micheletortora2022@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "04fccff43efe42b88f5e460ded0bfa38", "opened": false, "specialty": "unknown", "followup": false}, {"email": "martinsmatheus0497@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "c122e640ad234566853e94b5e10482a9", "opened": false, "specialty": "unknown", "followup": false}, {"email": "robin@vfxlabs.net", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "35ef2217dc7540569295123337a2e410", "opened": false, "specialty": "unknown", "followup": false}, {"email": "contact@maguriv.dev", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "2335ade501b940c1a561f7d5af032546", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dev@madeforme.studio", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "76d37adc36494976b621850b3f132e9e", "opened": false, "specialty": "unknown", "followup": false}, {"email": "karrtouche@proton.me", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "830dc1804fdb43549a054282c86a3753", "opened": false, "specialty": "unknown", "followup": false}, {"email": "hello@mlc.studio", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "13c912d66bf34932bf2b48c376e834e9", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nimer.aslam01@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "7bc76da4a57a43908e779b72bc5b3e03", "opened": false, "specialty": "unknown", "followup": false}, {"email": "adampsn335@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "929babf10154470f8e11c2b31df8f6d1", "opened": false, "specialty": "unknown", "followup": false}, {"email": "hello@channelcosu.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "96ecfe7ab5ec49dc800d65e4d08bf97c", "opened": false, "specialty": "unknown", "followup": false}, {"email": "cliffstersprog@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "56df945d87834299b3f4a3cfc8105bc5", "opened": false, "specialty": "unknown", "followup": false}, {"email": "idris.hadjoudj@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "d57d1ce91d4f4c83b5869793a16c356e", "opened": false, "specialty": "unknown", "followup": false}, {"email": "maxshatalovaudio@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ad060b65c2eb4f1983474c7cc8f201f8", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ilwsq4169@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "25ee285c020a4912b9cf20f6781de11c", "opened": false, "specialty": "unknown", "followup": false}, {"email": "brunogambacurta@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f1c19355cf21437d8139e5ebaaaec1f7", "opened": false, "specialty": "unknown", "followup": false}, {"email": "iltaen13@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "d69a52c134b64435b5d245dffbb87dc5", "opened": false, "specialty": "unknown", "followup": false}, {"email": "estudiosreply@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "de1203bafc654d2eb4d6111d7e52a115", "opened": false, "specialty": "unknown", "followup": false}, {"email": "2nddartt@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "73a95d4250374446b78e7b70ed0d34c6", "opened": false, "specialty": "unknown", "followup": false}, {"email": "tomiczdarko@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "dc2f9df15cfc4a2eba5e9591d52c2ea8", "opened": false, "specialty": "unknown", "followup": false}, {"email": "viniciustk3d@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "3935a65a3c714b8fb8aa776ea040a0c2", "opened": false, "specialty": "unknown", "followup": false}, {"email": "guiga.franzoni@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "8059bab00cf34f72951a954e98c07c2d", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dethiagolima@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "ede0076f5a4641caa0fb8f43c8e27129", "opened": false, "specialty": "unknown", "followup": false}, {"email": "camilabrugnoli@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "77830d83a8ed498b9981c9454a0835bb", "opened": false, "specialty": "unknown", "followup": false}, {"email": "danukim105@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "34e083aae73c447ba8361fd761277f4f", "opened": false, "specialty": "unknown", "followup": false}, {"email": "pnikota@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "d4aa70506edb461b8ca31550c6fc77ba", "opened": false, "specialty": "unknown", "followup": false}, {"email": "andrewslibradilla@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "48032787fa274f07a0512142965f4a32", "opened": false, "specialty": "unknown", "followup": false}, {"email": "bbibbi1025@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "f731da29348a4ac18d752027aa87a930", "opened": false, "specialty": "unknown", "followup": false}, {"email": "onderson.rocha@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "00df4d54b3a449b988a186e764dfa9c7", "opened": false, "specialty": "unknown", "followup": false}, {"email": "artbykandles@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5c60335c56f24de58015c0f21730fe65", "opened": false, "specialty": "unknown", "followup": false}, {"email": "maxim.norel.3d@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "6f33e698a8834be7a5fb5315b2f9af7f", "opened": false, "specialty": "unknown", "followup": false}, {"email": "mladen@misfitvillage.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "d1035456ad3f4aa2a4b911d912502646", "opened": false, "specialty": "unknown", "followup": false}, {"email": "ilamushie@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "cc42f6a4fc7948398dd8713b346c5abd", "opened": false, "specialty": "unknown", "followup": false}, {"email": "dreamsheepgs@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "3d7a12e079d942f1914c9a9486c1aec1", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jobs@indietech.studio", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "98ae660daf11454a9b01e4bd4fa51e5a", "opened": false, "specialty": "unknown", "followup": false}, {"email": "contacts@himasters.art", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "17e21bbf55ab4ebf9cc5837733715659", "opened": false, "specialty": "unknown", "followup": false}, {"email": "flameovkosmos@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "628c5ae382d248779b6ca80aa7c76dd6", "opened": false, "specialty": "unknown", "followup": false}, {"email": "anatoleduboisconcept@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "5a0b41be8d444cdbab88324e719d82d0", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sharkforgeentertainment@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "e69485c173af45459ceac6d109a7491d", "opened": false, "specialty": "unknown", "followup": false}, {"email": "lucassoaresca@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "a68f6dc350ba40ed8a818eb9b84faa57", "opened": false, "specialty": "unknown", "followup": false}, {"email": "emilyjor348@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "4188527b8b354b8eb4028d4e077c7296", "opened": false, "specialty": "unknown", "followup": false}, {"email": "taubeanimations@proton.me", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "a5efd5e782b54412b6a211e3df37c62b", "opened": false, "specialty": "unknown", "followup": false}, {"email": "k-tech-studio.email@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "10c747eba48f437792b2476b59ff5f21", "opened": false, "specialty": "unknown", "followup": false}, {"email": "wonkydom@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "22d1a7e86b6d443c8c0a572233e55b03", "opened": false, "specialty": "unknown", "followup": false}, {"email": "contact@northhackmedia.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "a3b51851c0384832b40e06637be22b8d", "opened": false, "specialty": "unknown", "followup": false}, {"email": "sebastien.brunet@northhackmedia.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "e9faef5af00f44e8afc6f7445e03634e", "opened": false, "specialty": "unknown", "followup": false}, {"email": "william.svensson@northhackmedia.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "bd4ee8e5f66d400b819ae95d9c22883a", "opened": false, "specialty": "unknown", "followup": false}, {"email": "rage3dart@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "c25f8bff71704887a2417f469669dfd4", "opened": false, "specialty": "unknown", "followup": false}, {"email": "arcadeinspace@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "996d429ac4d64e67a45de30cdcfadf88", "opened": false, "specialty": "unknown", "followup": false}, {"email": "nick@luminouslabs.ca", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "614b8a069a1d4b379f55e9acab2e745f", "opened": false, "specialty": "unknown", "followup": false}, {"email": "jeremy@seedlang.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "a56c55912b7943c6b41d7849cfe3fdf4", "opened": false, "specialty": "unknown", "followup": false}, {"email": "liu.zhang@noctilux3d.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "79b87f2343a140e7bed37c24abfe03d1", "opened": false, "specialty": "unknown", "followup": false}, {"email": "editor@80.lv", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "579c2470a57645c98c49224655073b76", "opened": false, "specialty": "unknown", "followup": false}, {"email": "k.tokarev@80.lv", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "6a458614d0194c83b3e094f8571c2b73", "opened": false, "specialty": "unknown", "followup": false}, {"email": "manakazeart@gmail.com", "subject": "Your work caught our attention \\u2014 Stylarx", "sent_at": "2026-03-06T12:00:00", "token": "1e60d470e5674507be67f929b8402e69", "opened": false, "specialty": "unknown", "followup": false}]'

def seed_sent_history():
    try:
        if os.path.exists(SENT_FILE):
            with open(SENT_FILE) as f:
                existing = json.load(f)
            if existing: return
    except: pass
    with open(SENT_FILE, "w") as f:
        f.write(SEED_SENT)

seed_sent_history()

scrape_progress = {"running": False, "log": [], "found": 0, "total_sources": 0, "done_sources": 0}
scrape_lock = threading.Lock()

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

def require_auth(f):
    from functools import wraps
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("authed"):
            if request.is_json or "text/event" in request.headers.get("Accept",""):
                return jsonify({"error":"unauthorized"}), 401
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

SPECIALTY_KEYWORDS = {
    "texture_artist":     ["texture","pbr","substance","material","albedo","roughness","normal map","texturing","surfacing","mari","quixel","megascans","tileable","udim","bake"],
    "character_artist":   ["character","character artist","zbrush","sculpt","anatomy","figure","portrait","humanoid","creature","skin","face","npc","bust","stylized character"],
    "environment_artist": ["environment","env artist","landscape","terrain","scene","level","foliage","prop","architecture","modular","kitbash","diorama","biome","exterior"],
    "vfx_artist":         ["vfx","visual effects","houdini","nuke","compositor","simulation","destruction","fluid","fire","smoke","explosion","particles","pyro","fx artist"],
    "animator":           ["animat","rigging","rig","skinning","motion capture","mocap","keyframe","walk cycle","facial","blend shape","bones","weight painting"],
    "motion_graphics":    ["motion graphic","mograph","after effects","cinema 4d","c4d","motion design","kinetic","title sequence","broadcast","loop","explainer"],
    "technical_artist":   ["technical artist","tech art","shader","hlsl","glsl","pipeline","vex","python script","procedural","automation","optimiz","lod"],
    "game_developer":     ["game dev","indie game","unity","unreal","godot","ue4","ue5","game design","level design","gameplay","game jam","steam","itch.io","mobile game"],
    "3d_generalist":      ["3d generalist","blender","maya","3ds max","cinema 4d","freelance 3d","3d artist","3d model","render","visualization","archviz","product viz"],
    "concept_artist":     ["concept art","concept artist","concept design","illustration","digital painting","2d","sketching","ideation","production design","storyboard"],
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

def add_lead(email, source, url="", text=""):
    email = email.lower().strip()
    if not re.match(r"[^@]+@[^@]+\.[^@]{2,}", email): return False
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

TEMPLATES = {
    "character_artist": {
        "initial": [
            ("Your characters caught our eye — Stylarx", "Hey {name},\n\nCame across your character work — the sculpt quality is genuinely impressive.\n\nI run Stylarx — premium 3D assets and AI tools built for artists like you. Founder tier: $59–$149 one-time lifetime access (no subscriptions).\n\nWorth a look: https://stylarx.app\n\n— Stylarx"),
            ("Quick note for character artists", "Hi {name},\n\nSaw your character art — the detail really stands out.\n\nBuilding Stylarx — premium 3D assets + AI tools. Founder tier is $59–$149 lifetime before prices go up.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("Fellow creator — heads up", "Hey {name},\n\nLove the character work. Stylarx — 140+ 3D assets, 10+ AI tools, one-time price. Founder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx Founder deal", "Hey {name},\n\nFollowing up on Stylarx. Founder window still open — $59–$149 lifetime. Closing soon.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx", "Hi {name},\n\nOne last note. Stylarx Founder pricing ($59–$149 lifetime) is almost done.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("Still thinking about it?", "Hey {name},\n\nStylarx Founder deal ($59–$149 lifetime) still live but closing soon.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "texture_artist": {
        "initial": [
            ("For texture artists — Stylarx", "Hey {name},\n\nNoticed your texture work — really clean PBR output.\n\nI run Stylarx — AI texture generator + full 3D asset library. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Your material work is impressive", "Hi {name},\n\nSaw your substance/texture work — top tier.\n\nStylarx has AI texture tools + 3D asset library. Founder pricing: $59–$149 lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("New tools for texture artists", "Hey {name},\n\nBuilding Stylarx — AI texture generator + 140+ 3D assets. Founder deal: $59–$149 lifetime.\n\nhttps://stylarx.app"),
        ],
        "followup": [
            ("Following up — Stylarx", "Hey {name},\n\nFollowing up on Stylarx. AI texture tools still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last chance — Stylarx Founder", "Hi {name},\n\nStylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app\n\nBest"),
            ("Still interested?", "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "environment_artist": {
        "initial": [
            ("Environment art toolkit — Stylarx", "Hey {name},\n\nYour environment work caught my eye — world-building and composition are excellent.\n\nBuilding Stylarx — modular 3D kits + AI tools for env artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("For environment artists", "Hi {name},\n\nSaw your env art — scene composition is really strong.\n\nStylarx — 3D assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ("Modular kits for env artists", "Hey {name},\n\nBuilding Stylarx — modular prop library + AI layout tools. Founder price: $59–$149.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ],
        "followup": [
            ("Following up — Stylarx", "Hey {name},\n\nFollowing up on Stylarx. Modular kits + AI tools at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx", "Hi {name},\n\nStylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app"),
            ("Still thinking?", "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "vfx_artist": {
        "initial": [
            ("VFX tools — Stylarx Founder", "Hey {name},\n\nCame across your VFX work — simulation quality is top tier.\n\nBuilding Stylarx — 3D assets + AI tools for VFX artists. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Quick note for VFX artists", "Hi {name},\n\nImpressive VFX work. Stylarx — assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ("Rapid iteration tools for VFX", "Hey {name},\n\nStylarx — AI tools for rapid VFX iteration. 140+ assets included. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
        ],
        "followup": [
            ("Following up — Stylarx", "Hey {name},\n\nFollowing up on Stylarx. Still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx", "Hi {name},\n\nStylarx Founder deal closing soon — $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ("Still open — Stylarx", "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app\n\n— Stylarx"),
        ]
    },
    "animator": {
        "initial": [
            ("For animators — quick note", "Hey {name},\n\nYour animation work is excellent — motion and character performance really come through.\n\nBuilding Stylarx — rig-ready 3D assets + AI motion tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Rig-ready assets for animators", "Hi {name},\n\nSaw your animation work — impressive. Stylarx — rig-ready assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ("Animation toolkit — Stylarx", "Hey {name},\n\nBuilding Stylarx — 140+ rig-ready 3D assets + AI motion tools. Founder price: $59–$149.\n\nhttps://stylarx.app"),
        ],
        "followup": [
            ("Following up — Stylarx", "Hey {name},\n\nFollowing up on Stylarx. Rig-ready library still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx", "Hi {name},\n\nStylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app"),
            ("Still interested?", "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still open.\n\nhttps://stylarx.app"),
        ]
    },
    "game_developer": {
        "initial": [
            ("Game dev asset toolkit — Stylarx", "Hey {name},\n\nYour game project looks great — love the indie dev hustle.\n\nI run Stylarx — 140+ game-ready 3D assets + AI tools. Unity, Unreal, Godot compatible. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("For indie game developers", "Hi {name},\n\nIndie dev is tough — especially the art side. Stylarx has 140+ game-ready assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ("Game-ready 3D assets", "Hey {name},\n\nStylarx — 140+ 3D assets, 10+ AI tools, $59–$149 founder lifetime deal.\n\nhttps://stylarx.app"),
        ],
        "followup": [
            ("Following up — Stylarx", "Hey {name},\n\nFollowing up on Stylarx. 140+ game-ready assets still at Founder pricing ($59–$149 lifetime).\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx", "Hi {name},\n\nStylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app"),
            ("Still building?", "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app"),
        ]
    },
    "unknown": {
        "initial": [
            ("A quick note from Stylarx", "Hey {name},\n\nCame across your work — really stood out.\n\nI run Stylarx — 140+ premium 3D assets and 10+ AI tools for working artists. Founder tier: $59–$149 one-time lifetime.\n\nhttps://stylarx.app\n\nBest,\nStylarx"),
            ("Found your work — quick note", "Hi {name},\n\nYour work is great. Building Stylarx — 3D assets + AI tools. Founder: $59–$149 lifetime.\n\nhttps://stylarx.app"),
            ("Stylarx — for 3D artists", "Hey {name},\n\nStylarx — premium 3D assets + AI tools. Founder launch at $59–$149 lifetime.\n\nhttps://stylarx.app"),
        ],
        "followup": [
            ("Following up — Stylarx", "Hey {name},\n\nFollowing up on Stylarx. Founder pricing ($59–$149 lifetime) still open.\n\nhttps://stylarx.app\n\n— Stylarx"),
            ("Last note — Stylarx", "Hi {name},\n\nStylarx Founder deal ($59–$149 lifetime) closing soon.\n\nhttps://stylarx.app"),
            ("Still interested?", "Hey {name},\n\nStylarx Founder pricing ($59–$149 lifetime) still live.\n\nhttps://stylarx.app"),
        ]
    },
}

for sp in ["motion_graphics","technical_artist","3d_generalist","concept_artist"]:
    TEMPLATES[sp] = TEMPLATES["unknown"]

def get_template(specialty, is_followup):
    pool = TEMPLATES.get(specialty, TEMPLATES["unknown"])
    variants = pool["followup"] if is_followup else pool["initial"]
    return random.choice(variants)

REDDIT_SOURCES = [
    ("r/gameDevClassifieds","r/gameDevClassifieds","https://www.reddit.com/r/gameDevClassifieds/search.json?q=3d+artist&sort=new&limit=50"),
    ("r/forhire — 3D","r/forhire","https://www.reddit.com/r/forhire/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/forhire — texture","r/forhire","https://www.reddit.com/r/forhire/search.json?q=texture+artist&sort=new&limit=25"),
    ("r/forhire — animator","r/forhire","https://www.reddit.com/r/forhire/search.json?q=animator&sort=new&limit=25"),
    ("r/forhire — vfx","r/forhire","https://www.reddit.com/r/forhire/search.json?q=vfx+artist&sort=new&limit=25"),
    ("r/blender freelance","r/blender","https://www.reddit.com/r/blender/search.json?q=freelance+commission&sort=new&limit=25"),
    ("r/3Dartists","r/3Dartists","https://www.reddit.com/r/3Dartists/search.json?q=freelance&sort=new&limit=25"),
    ("r/ZBrush","r/ZBrush","https://www.reddit.com/r/ZBrush/search.json?q=commission&sort=new&limit=25"),
    ("r/Maya","r/Maya","https://www.reddit.com/r/Maya/search.json?q=freelance&sort=new&limit=25"),
    ("r/SubstancePainter","r/SubstancePainter","https://www.reddit.com/r/SubstancePainter/search.json?q=artist&sort=new&limit=25"),
    ("r/Houdini","r/Houdini","https://www.reddit.com/r/Houdini/search.json?q=freelance&sort=new&limit=25"),
    ("r/Cinema4D","r/Cinema4D","https://www.reddit.com/r/Cinema4D/search.json?q=freelance&sort=new&limit=25"),
    ("r/lowpoly","r/lowpoly","https://www.reddit.com/r/lowpoly/search.json?q=artist&sort=new&limit=25"),
    ("r/characterdesign","r/characterdesign","https://www.reddit.com/r/characterdesign/search.json?q=commission&sort=new&limit=25"),
    ("r/vfx","r/vfx","https://www.reddit.com/r/vfx/search.json?q=freelance&sort=new&limit=25"),
    ("r/indiegamedev","r/indiegamedev","https://www.reddit.com/r/indiegamedev/search.json?q=artist&sort=new&limit=25"),
    ("r/gamedev","r/gamedev","https://www.reddit.com/r/gamedev/search.json?q=hiring+3d+artist&sort=new&limit=25"),
    ("r/Unity3D","r/Unity3D","https://www.reddit.com/r/Unity3D/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/unrealengine","r/unrealengine","https://www.reddit.com/r/unrealengine/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/artcommissions","r/artcommissions","https://www.reddit.com/r/artcommissions/search.json?q=3d&sort=new&limit=25"),
    ("r/HungryArtists","r/HungryArtists","https://www.reddit.com/r/HungryArtists/search.json?q=3d&sort=new&limit=25"),
    ("r/commissions","r/commissions","https://www.reddit.com/r/commissions/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/conceptart","r/conceptart","https://www.reddit.com/r/conceptart/search.json?q=freelance&sort=new&limit=25"),
    ("r/stylizedstation","r/stylizedstation","https://www.reddit.com/r/stylizedstation/search.json?q=artist&sort=new&limit=25"),
    ("r/learnblender","r/learnblender","https://www.reddit.com/r/learnblender/search.json?q=email&sort=new&limit=25"),
    ("r/shaders","r/shaders","https://www.reddit.com/r/shaders/search.json?q=freelance&sort=new&limit=25"),
    ("r/Freelance","r/Freelance","https://www.reddit.com/r/Freelance/search.json?q=3d+artist&sort=new&limit=25"),
    ("r/computergraphics","r/computergraphics","https://www.reddit.com/r/computergraphics/search.json?q=freelance&sort=new&limit=25"),
    ("r/daz3d","r/daz3d","https://www.reddit.com/r/daz3d/search.json?q=artist&sort=new&limit=25"),
    ("r/leveldesign","r/leveldesign","https://www.reddit.com/r/leveldesign/search.json?q=artist&sort=new&limit=25"),
]

BING_QUERIES = [
    "site:gumroad.com 3d models blender artist email","site:gumroad.com substance painter texture artist",
    "site:gumroad.com character 3d zbrush","site:gumroad.com environment 3d artist","site:gumroad.com vfx houdini",
    "site:gumroad.com indie game 3d assets","site:gumroad.com animator rigging",
    "site:itch.io freelance 3d artist contact email","site:itch.io 3d game assets developer","site:itch.io character artist contact",
    "site:carrd.co 3d artist portfolio email","site:carrd.co character artist hire",
    "site:behance.net 3d artist contact email","site:behance.net character artist contact","site:behance.net texture artist contact",
    "site:dribbble.com 3d artist contact email","site:deviantart.com 3d artist commissions email",
    "site:artstation.com 3d artist available hire email","site:artstation.com character artist freelance",
    "site:sketchfab.com 3d artist contact email","site:cgtrader.com 3d artist contact",
    "site:linkedin.com 3d artist freelance available",
    "freelance 3d character artist for hire email","freelance texture artist pbr substance hire email",
    "freelance environment artist 3d hire email","freelance vfx artist houdini hire email",
    "stylized 3d artist commission open email","hard surface 3d modeler freelance email",
    "3d animator rigger freelance email","blender freelance artist portfolio email",
    "maya 3d artist freelance email","zbrush sculptor character freelance email",
    "substance painter texture artist hire email","unreal engine 3d artist hire email",
    "unity 3d artist freelance email","houdini vfx artist freelance email",
    "cinema 4d motion graphics artist hire email","concept artist freelance hire email",
    "3d product visualization artist hire email","archviz 3d artist freelance email",
    "game ready assets artist freelance email","indie game dev artist hire email",
    "low poly 3d artist hire email","3d generalist freelance portfolio email",
    "technical artist pipeline freelance email","nft 3d artist commission email",
]

DIRECT_SOURCES = [
    ("BlenderArtists Jobs","blenderartists","https://blenderartists.org/c/jobs/job-listings/27.json?page=1"),
    ("BlenderArtists Jobs p2","blenderartists","https://blenderartists.org/c/jobs/job-listings/27.json?page=2"),
    ("itch.io 3D assets p1","itch.io","https://itch.io/game-assets/free/tag-3d?page=1"),
    ("itch.io 3D assets p2","itch.io","https://itch.io/game-assets/free/tag-3d?page=2"),
    ("itch.io 3D assets p3","itch.io","https://itch.io/game-assets/tag-3d?page=1"),
    ("ArtStation Jobs p1","artstation","https://www.artstation.com/jobs?page=1"),
    ("ArtStation Jobs p2","artstation","https://www.artstation.com/jobs?page=2"),
    ("ArtStation Jobs p3","artstation","https://www.artstation.com/jobs?page=3"),
    ("80.lv Jobs","80.lv","https://80.lv/jobs/"),
    ("Polycount Jobs","polycount","https://polycount.com/categories/job-board"),
    ("CGSociety Forums","cgsociety","https://forums.cgsociety.org/c/jobs/"),
    ("Renderosity Market","renderosity","https://www.renderosity.com/marketplace/"),
    ("Sketchfab Popular","sketchfab","https://sketchfab.com/3d-models/popular?features=downloadable"),
    ("CGTrader Designers","cgtrader","https://www.cgtrader.com/designers"),
    ("TurboSquid Artists","turbosquid","https://www.turbosquid.com/Search/Artists"),
    ("GameDev.net Jobs","gamedev.net","https://www.gamedev.net/classifieds/"),
    ("ZBrushCentral WIP","zbrushcentral","https://www.zbrushcentral.com/c/work-in-progress/"),
    ("DeviantArt 3D art","deviantart","https://www.deviantart.com/tag/3dart?page=1"),
    ("DeviantArt blender","deviantart","https://www.deviantart.com/tag/blender3d?page=1"),
    ("Behance 3D","behance","https://www.behance.net/search/projects?field=3d-modeling&page=1"),
    ("OpenGameArt","opengameart","https://opengameart.org/art-search-advanced?keys=&field_art_type_tid[]=9"),
    ("Fiverr 3D artists","fiverr","https://www.fiverr.com/search/gigs?query=3d+artist"),
    ("Upwork 3D artists","upwork","https://www.upwork.com/search/profiles/?q=3d+artist"),
    ("IndieDB Artists","indiedb","https://www.indiedb.com/groups/3d-artists/members"),
    ("GameJolt 3D","gamejolt","https://gamejolt.com/games?tag=3d"),
    ("SideFX Forum","sidefx","https://www.sidefx.com/forum/topic/houdini-lounge/"),
    ("Unity Forum Jobs","unity","https://forum.unity.com/forums/jobs-offerings.22/"),
    ("TIGSource","tigsource","https://forums.tigsource.com/index.php?board=10.0"),
    ("Dribbble 3D","dribbble","https://dribbble.com/tags/3d"),
    ("Fab.com creators","fab.com","https://www.fab.com/listings?category=3d-assets&sort_by=-created_at"),
]

scrape_progress = {"running": False, "log": [], "found": 0, "total_sources": 0, "done_sources": 0}
scrape_lock = threading.Lock()

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
                    slog(f"Scanning {label}...")
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
                                        slog(f"Found: {e}")
                        except: pass
                    time.sleep(random.uniform(1.5, 3))
            elif src_key.startswith("bing_"):
                idx = int(src_key.split("_")[1])
                if idx < len(BING_QUERIES):
                    query = BING_QUERIES[idx]
                    url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}&count=20"
                    slog(f"Searching: {query[:50]}...")
                    html = scrape_url(url)
                    for e in extract_emails(html):
                        if add_lead(e, "Bing Search", url, query):
                            found_total += 1
                            slog(f"Found: {e}")
                    time.sleep(random.uniform(2, 4))
            elif src_key.startswith("direct_"):
                idx = int(src_key.split("_")[1])
                if idx < len(DIRECT_SOURCES):
                    label, sname, url = DIRECT_SOURCES[idx]
                    slog(f"Scanning {label}...")
                    html = scrape_url(url)
                    for e in extract_emails(html):
                        if add_lead(e, label, url, ""):
                            found_total += 1
                            slog(f"Found: {e}")
                    time.sleep(random.uniform(2, 4))
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
            session["authed"] = True
            return redirect("/")
        return render_template("login.html", error="Incorrect password. Try again.")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/")
@require_auth
def index():
    return render_template("index.html")

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
    return jsonify({"total_leads": len(leads), "total_sent": len(sent),
        "sent_today": sent_today, "open_rate": open_rate, "opens": opens, "sp_leads": sp_leads})

@app.route("/api/sources")
@require_auth
def api_sources():
    return jsonify({
        "reddit": [{"key":f"reddit_{i}","label":r[0],"source":r[1]} for i,r in enumerate(REDDIT_SOURCES)],
        "bing":   [{"key":f"bing_{i}",  "label":q[:55],"source":"bing"} for i,q in enumerate(BING_QUERIES)],
        "direct": [{"key":f"direct_{i}","label":d[0],"source":d[1]} for i,d in enumerate(DIRECT_SOURCES)],
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
    leads = load_leads()
    changed = 0
    for lead in leads:
        new_sp = detect_specialty(lead.get("source",""), lead.get("url",""), lead.get("text",""))
        if lead.get("specialty") != new_sp:
            lead["specialty"] = new_sp
            changed += 1
    save_leads(leads)
    return jsonify({"changed":changed,"total":len(leads)})

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
    emails = (request.json or {}).get("emails",[])
    added = sum(1 for e in emails if add_lead(e.strip(), "Manual Import", "", ""))
    return jsonify({"added":added})

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
            token = str(uuid.uuid4()).replace("-","")
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
            leads = [l for l in load_leads() if l["email"].lower() != email]
            save_leads(leads)
            yield f"data: {json.dumps({'sent':email,'specialty':specialty})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error':email,'msg':str(e)})}\n\n"
        delay = random.uniform(90,120)
        for i in range(int(delay)):
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
    if d.get("current","") != APP_PASSWORD: return jsonify({"error":"Incorrect current password"}),400
    APP_PASSWORD = d.get("new","")
    return jsonify({"ok":True})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",8080)), debug=False)
