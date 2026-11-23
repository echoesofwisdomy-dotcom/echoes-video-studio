import os, io, json, re, random, asyncio, subprocess, requests, base64, time
from datetime import datetime, timedelta, timezone, time as dt_time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
import edge_tts

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# ---------------------------------------------------------
# 1. PAGE SETUP & STUDIO UI
# ---------------------------------------------------------
st.set_page_config(page_title="Echoes Video Studio", page_icon="🎬", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');
    header[data-testid="stHeader"] { background: transparent !important; }
    .stApp { 
        background-color: #080B11 !important; 
        background-image: radial-gradient(circle at 50% -20%, #151e33 0%, #080B11 75%) !important; 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important; 
        color: #E2E8F0 !important; 
    }
    .block-container { padding-top: 3.5rem !important; padding-bottom: 3rem !important; max-width: 720px !important; }
    div[data-testid="stExpander"] { 
        background: #0E1626 !important; 
        border: 1px solid rgba(56, 189, 248, 0.25) !important; 
        border-radius: 12px !important; 
        margin-bottom: 1rem !important; 
    }
    div[data-testid="stExpander"] summary { 
        background: #111B30 !important; 
        color: #38BDF8 !important; 
        font-size: 13px !important; 
        font-weight: 700 !important; 
    }
    label[data-testid="stWidgetLabel"] p { 
        color: #94A3B8 !important; 
        font-size: 12px !important; 
        font-weight: 700 !important; 
        text-transform: uppercase !important; 
    }
    .stTextInput>div>div>input, .stTextArea textarea { 
        background-color: #0A0F1D !important; 
        border: 1px solid rgba(56, 189, 248, 0.25) !important; 
        color: #F8FAFC !important; 
        border-radius: 8px !important; 
        font-size: 14px !important; 
        line-height: 1.6 !important; 
    }
    .stButton>button[kind="primary"] { 
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important; 
        color: #FFF !important; 
        border-radius: 10px !important; 
        height: 3.4rem !important; 
        font-weight: 700 !important; 
        text-transform: uppercase !important; 
        width: 100% !important; 
    }
    .stButton>button:not([kind="primary"]) { 
        background: #111B30 !important; 
        color: #E2E8F0 !important; 
        border: 1px solid rgba(56, 189, 248, 0.25) !important; 
        border-radius: 8px !important; 
        font-weight: 600 !important; 
    }
    .stDownloadButton>button { 
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important; 
        color: white !important; 
        border-radius: 10px !important; 
        height: 3.2rem !important; 
        font-weight: 700 !important; 
        width: 100% !important; 
    }
    .badge { 
        font-family: 'JetBrains Mono', monospace; 
        font-size: 11px; 
        font-weight: 600; 
        padding: 5px 12px; 
        border-radius: 6px; 
        display: inline-flex; 
        align-items: center; 
        margin: 2px; 
    }
    .badge-green { background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(52, 211, 153, 0.25); }
    .badge-blue  { background: rgba(56, 189, 248, 0.12); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.25); }
    .badge-amber { background: rgba(245, 158, 11, 0.12); color: #FBBF24; border: 1px solid rgba(251, 191, 36, 0.25); }
    .badge-purple{ background: rgba(168, 85, 247, 0.12); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.25); }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. FILE PATHWAYS & PERSISTENT STORAGE
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
MUSIC_DIR = os.path.join(BASE_DIR, "music")

for d in [DATA_DIR, TMP_DIR, FONTS_DIR, MUSIC_DIR]: 
    os.makedirs(d, exist_ok=True)

DRAFT_JSON_PATH = os.path.join(DATA_DIR, "active_draft.json")
DRAFT_AUDIO_PATH = os.path.join(DATA_DIR, "active_audio.mp3")
DRAFT_VAULT_PATH = os.path.join(DATA_DIR, "draft_vault.json")
API_KEY_FILE = os.path.join(DATA_DIR, "gemini_key.txt")
GSHEET_URL_FILE = os.path.join(DATA_DIR, "gsheet_webhook.txt")
CHANNEL_HANDLE_FILE = os.path.join(DATA_DIR, "channel_handle.txt")
META_HANDLE_FILE = os.path.join(DATA_DIR, "meta_handle.txt")
GUIDE_URL_FILE = os.path.join(DATA_DIR, "guide_url.txt")
EXCEL_TRACKER_PATH = os.path.join(DATA_DIR, "Echoes_Of_Wisdom_Content_Tracker.xlsx")

@st.cache_resource(show_spinner=False)
def ensure_dejavu_font():
    f_path = os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")
    if not os.path.exists(f_path) or os.path.getsize(f_path) < 10000:
        for u in [
            "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf",
            "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        ]:
            try:
                r = requests.get(u, timeout=8)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(f_path, "wb") as f: f.write(r.content)
                    break
            except Exception: pass
    return f_path

ensure_dejavu_font()

def get_persistent_api_key():
    if st.session_state.get("user_key_input"):
        return st.session_state["user_key_input"].strip().strip('"').strip("'")
    if st.session_state.get("api_key"):
        return st.session_state["api_key"].strip().strip('"').strip("'")
    if "GEMINI_API_KEY" in st.secrets:
        return str(st.secrets["GEMINI_API_KEY"]).strip().strip('"').strip("'")
    if os.getenv("GEMINI_API_KEY"):
        return os.getenv("GEMINI_API_KEY").strip()
    if os.path.exists(API_KEY_FILE):
        try:
            with open(API_KEY_FILE, "r", encoding="utf-8") as f:
                saved = f.read().strip()
                if saved: return saved
        except Exception: pass
    return ""

def save_persistent_api_key(key_val):
    clean = key_val.strip().strip('"').strip("'")
    st.session_state["api_key"] = clean
    try:
        with open(API_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception: pass

def get_persistent_gsheet_url():
    if st.session_state.get("user_sheet_url"):
        return st.session_state["user_sheet_url"].strip()
    if "GSHEET_WEBHOOK_URL" in st.secrets:
        return str(st.secrets["GSHEET_WEBHOOK_URL"]).strip()
    if os.path.exists(GSHEET_URL_FILE):
        try:
            with open(GSHEET_URL_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception: pass
    return ""

def save_persistent_gsheet_url(url_val):
    clean = url_val.strip()
    st.session_state["user_sheet_url"] = clean
    try:
        with open(GSHEET_URL_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception: pass

def get_persistent_yt_handle():
    if "YT_CHANNEL_HANDLE" in st.secrets:
        return str(st.secrets["YT_CHANNEL_HANDLE"]).strip()
    if os.path.exists(CHANNEL_HANDLE_FILE):
        try:
            with open(CHANNEL_HANDLE_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val: return val
        except Exception: pass
    return st.session_state.get("user_yt_handle", "@AJ-Echoes-of-Wisdom").strip()

def save_persistent_yt_handle(handle_val):
    clean = handle_val.strip()
    if clean and not clean.startswith("@"): clean = "@" + clean
    st.session_state["user_yt_handle"] = clean
    try:
        with open(CHANNEL_HANDLE_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception: pass

def get_persistent_meta_handle():
    if "META_CHANNEL_HANDLE" in st.secrets:
        return str(st.secrets["META_CHANNEL_HANDLE"]).strip()
    if os.path.exists(META_HANDLE_FILE):
        try:
            with open(META_HANDLE_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val: return val
        except Exception: pass
    return st.session_state.get("user_meta_handle", "@EchoesOfWisdomOfficial").strip()

def save_persistent_meta_handle(handle_val):
    clean = handle_val.strip()
    if clean and not clean.startswith("@"): clean = "@" + clean
    st.session_state["user_meta_handle"] = clean
    try:
        with open(META_HANDLE_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception: pass

def get_persistent_guide_url():
    if os.path.exists(GUIDE_URL_FILE):
        try:
            with open(GUIDE_URL_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val: return val
        except Exception: pass
    return "https://theechoesofwisdom.gumroad.com/l/stoic-guide"

# ---------------------------------------------------------
# DRAFT VAULT ENGINE
# ---------------------------------------------------------
def load_draft_vault():
    if os.path.exists(DRAFT_VAULT_PATH):
        try:
            with open(DRAFT_VAULT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return []

def save_to_draft_vault(draft_item):
    vault = load_draft_vault()
    hook_banner = draft_item.get("pkg", {}).get("hook_banner", "")
    vault = [v for v in vault if v.get("pkg", {}).get("hook_banner") != hook_banner]
    vault.insert(0, draft_item)
    vault = vault[:30]
    try:
        with open(DRAFT_VAULT_PATH, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=2)
    except Exception: pass

# ---------------------------------------------------------
# 3. 30 NON-REPEATING FORMATS, VISUALS & LIFE LESSONS
# ---------------------------------------------------------
SUBTITLE_ARCHETYPES = {
    "IMPERIAL_GOLD": {"label": "👑 Imperial Gold",   "ass_primary": "&H0000E5FF", "ass_outline": "&H00000000", "ass_font": "DejaVu Sans", "ass_size": 74, "banner_hex": "0xFFE500", "prefix": "gold_"},
    "GLACIAL_ICE":   {"label": "❄️ Glacial Ice",     "ass_primary": "&H00FFF500", "ass_outline": "&H00120A04", "ass_font": "DejaVu Sans", "ass_size": 72, "banner_hex": "0x00F5FF", "prefix": "ice_"},
    "FORGE_AMBER":   {"label": "🔥 Forge Amber",     "ass_primary": "&H000099FF", "ass_outline": "&H00050510", "ass_font": "DejaVu Sans", "ass_size": 76, "banner_hex": "0xFF9900", "prefix": "amber_"},
    "CRIMSON_IVORY": {"label": "🩸 Crimson & Ivory", "ass_primary": "&H003838FF", "ass_outline": "&H00F8FAFC", "ass_font": "DejaVu Serif","ass_size": 72, "banner_hex": "0xFF5555", "prefix": "crimson_"},
    "EMERALD_BONE":  {"label": "🌿 Emerald & Bone",  "ass_primary": "&H0086EFAC", "ass_outline": "&H0006120B", "ass_font": "DejaVu Sans", "ass_size": 74, "banner_hex": "0x4ADE80", "prefix": "emerald_"},
    "ROYAL_VIOLET":  {"label": "🔮 Violet & Gold",   "ass_primary": "&H00F5D0FE", "ass_outline": "&H002E0845", "ass_font": "DejaVu Serif","ass_size": 72, "banner_hex": "0xE879F9", "prefix": "violet_"}
}

CINEMATOGRAPHY_MATRIX = {
    "PUNCH_FLASH":      {"label": "⚡ Dynamic Kinetic Arc & Probe",         "ffmpeg_eq": "eq=contrast=1.12:brightness=0.01:saturation=1.08", "grade": "High-contrast chiaroscuro, volumetric dust motes, 35mm film grain"},
    "PULL_VIGN":        {"label": "🌊 Atmospheric Parallax & Macro Whip",   "ffmpeg_eq": "eq=contrast=1.16:brightness=-0.02:saturation=0.78","grade": "Moody slate-grey palette, deep shadows, muted earth tones"},
    "WARM_DRIFT":       {"label": "🔥 Forge Ember & Optical Rack Focus",    "ffmpeg_eq": "eq=contrast=1.10:brightness=0.02:saturation=1.24", "grade": "Warm tungsten highlights, soft ambient haze, 35mm analog warmth"},
    "NORDIC_CUT":       {"label": "❄️ Nordic Citadel & Fast Shutter Tilt",  "ffmpeg_eq": "eq=contrast=1.20:brightness=0.0:saturation=0.65",  "grade": "Cold overcast daylight, desaturated steel-blue grading, crisp edges"},
    "OVERHEAD_NOIR":    {"label": "🌑 High-Angle Bird's Eye Noir",          "ffmpeg_eq": "eq=contrast=1.24:brightness=-0.03:saturation=0.85","grade": "High-angle top-down noir shadows and dramatic rim lighting"},
    "GOLDEN_HOUR_ARC":  {"label": "🌅 Low-Horizon Golden Ray Sweep",        "ffmpeg_eq": "eq=contrast=1.08:brightness=0.02:saturation=1.20", "grade": "Warm low-angle golden hour sunbeams and soft depth"},
    "MONOCHROME_GRIT":  {"label": "🖤 Stark Monochrome Documentary",        "ffmpeg_eq": "eq=contrast=1.22:brightness=0.0:saturation=0.0",   "grade": "Stark black-and-white documentary realism and crisp grain"},
    "MODERN_LIFE_REAL": {"label": "🏙️ Modern Everyday Window Realism",      "ffmpeg_eq": "eq=contrast=1.08:brightness=0.01:saturation=1.05", "grade": "Naturalistic modern interior and street daylight, authentic emotion"}
}

DIRECTOR_STYLES = {k: v["label"] for k, v in CINEMATOGRAPHY_MATRIX.items()}

PLAYLIST_OPTIONS = [
    "The art of moving in silence (stoic mindset)",
    "Mastering human nature and fake friends ancient parables",
    "Financial Sovereignty and Relentless Discipline",
    "Father to Son: Ancient Legacy Lessons",
    "Aging Well: Habits for Mind and Body"
]

THIRTY_DAY_CURRICULUM = [
    {"day": 1,  "fmt": "CONFESSIONAL_WINDOW",   "pl": "Financial Sovereignty and Relentless Discipline",     "style": "MODERN_LIFE_REAL","arch": "EMERALD_BONE",  "badge": "QUIET RESERVE",    "hook_title": "THE SILENT BILL PAYER",          "script": "At thirty, I spent to look successful. By forty-five, I realized nobody pays your bills out of sympathy. Quiet savings buy the one luxury people rarely talk about: the freedom to say no without panic. Every calm decision compounds over time, so remember that you...",          "q": "What money habit gave you the most peace of mind as you got older?",         "s1": "35mm natural shot, man in knit sweater looking out modern apartment window at dawn",          "s2": "Close-up of simple coffee cup and clean notebook on wooden table in soft light",        "s3": "Medium shot walking calmly through quiet hallway into morning light",                      "s4": "Calm reflective close-up with steady eyes and natural window light"},
    {"day": 2,  "fmt": "TWO_ARROWS_PARABLE",    "pl": "The art of moving in silence (stoic mindset)",         "style": "PUNCH_FLASH",     "arch": "IMPERIAL_GOLD", "badge": "FIRST VS SECOND",  "hook_title": "STOP REPLAYING THE HIT",         "script": "Someone speaks carelessly and hurts your pride, that is the first arrow. Replaying that moment for three sleepless nights is the second arrow, and you fired it yourself. Let the first hit pass without feeding it. Guard your peace tonight, because real strength means you...",       "q": "How do you stop replaying an unfair remark or setback in your head?",          "s1": "24mm low-angle push-in on weathered warrior in shadowed stone courtyard",                "s2": "100mm macro shot of bronze arrow deflecting cleanly off dark iron shield",               "s3": "35mm tracking arc as subject strides across quiet stone bridge in mist",                "s4": "85mm portrait close-up with steady calm gaze and subtle rim light"},
    {"day": 3,  "fmt": "FAMILY_DOORWAY_SCENE",  "pl": "Father to Son: Ancient Legacy Lessons",               "style": "GOLDEN_HOUR_ARC", "arch": "CRIMSON_IVORY", "badge": "QUIET SACRIFICE",  "hook_title": "WHO STOOD IN THE DOORWAY",       "script": "We rarely notice who held the line when everything felt uncertain, until years later. Real loyalty shows up in quiet sacrifices, not loud promises. Honor the people who stayed when nothing was in it for them. Respect is earned in silence, and you...",                     "q": "Who is someone who showed quiet loyalty when things were hard?",              "s1": "28mm golden hour shot of family figures in warm doorway light with soft depth",        "s2": "85mm macro of weathered hands resting on warm oak table beside lamp",                 "s3": "35mm wide-to-medium tracking shot along sunlit stone path",                          "s4": "85mm close-up with warm afternoon sunbeam and composed expression"},
    {"day": 4,  "fmt": "MONOCHROME_WALK_AWAY",  "pl": "Mastering human nature and fake friends ancient parables","style": "MONOCHROME_GRIT","arch": "GLACIAL_ICE",   "badge": "NO ARGUMENT",      "hook_title": "WALKING AWAY CLEANLY",           "script": "Walking away is not weakness when you stop begging people to see your side. Some rooms will never understand your standards, and arguing only lowers your own ground. Step out quietly and let time do the sorting. You never lose power when you...",                     "q": "When did walking away without an argument protect your self-respect?",         "s1": "35mm monochrome candid shot, man in dark coat standing still on misty street",        "s2": "85mm black-and-white macro of leather boot stepping onto wet stone",                 "s3": "28mm wide documentary shot walking away down quiet alley in soft fog",              "s4": "85mm monochrome close-up showing calm, unhurried resolve"},
    {"day": 5,  "fmt": "OVERHEAD_NOIR_FOCUS",   "pl": "Financial Sovereignty and Relentless Discipline",     "style": "OVERHEAD_NOIR",   "arch": "FORGE_AMBER",   "badge": "SIGNAL VS NOISE",  "hook_title": "CUT THE DISTRACTIONS",           "script": "Most men do not fail from lack of talent, they drift because every small distraction pulls them off course. Pick one real standard and protect it daily. Momentum builds when your attention stops leaking in ten directions. Stay locked on the work, and you...",                   "q": "What is the biggest distraction you had to cut to get real work done?",        "s1": "21mm high-angle bird's-eye shot descending into shadowed courtyard",                "s2": "75mm top-down macro of brass compass needle settling steady on dark wood",            "s3": "40mm high-angle tracking along stone wall with deep noir shadows",                   "s4": "90mm dramatic rim-lit close-up with intense focused gaze"},
    {"day": 6,  "fmt": "NORDIC_COLD_DISCIPLINE","pl": "Aging Well: Habits for Mind and Body",                "style": "NORDIC_CUT",      "arch": "GLACIAL_ICE",   "badge": "BODY AFTER 40",    "hook_title": "YOUR FUTURE BODY IS WATCHING",   "script": "Every short walk, every clean meal, and every night of real rest is a vote for your independence twenty years from now. Do not trade future strength for today's comfort. Take care of the body that carries you through life, because later years reward how you...",               "q": "Which physical habit has helped your energy most after age thirty-five?",      "s1": "24mm wide shot in cold mountain mist, rugged man in dark wool coat",                 "s2": "100mm macro of frost and clear water droplets on dark granite",                    "s3": "50mm tracking shot along rocky ridge under overcast sky",                           "s4": "105mm close-up with cold visible breath and steady eyes"},
    {"day": 7,  "fmt": "FORGE_EMEMBER_TRUTH",   "pl": "Mastering human nature and fake friends ancient parables","style": "WARM_DRIFT",    "arch": "FORGE_AMBER",   "badge": "ACTION OVER TALK", "hook_title": "WATCH WHAT THEY DO",             "script": "Words are cheap when the stakes are low. Pay attention to who stays steady when pressure hits and nothing is gained by pretending. Character is revealed by action under strain, not speeches in calm weather. Keep your eyes open, and remember that you...",                   "q": "What action reveals someone's true character faster than their words?",         "s1": "50mm warm lateral drift past stone pillar revealing resolute man",                 "s2": "100mm macro of glowing orange embers rising in dark workshop",                     "s3": "35mm medium tracking shot through warm lantern-lit courtyard",                   "s4": "85mm close-up with warm amber firelight and firm nod"},
    {"day": 8,  "fmt": "EPIC_COLONNADE_SCALE",  "pl": "The art of moving in silence (stoic mindset)",         "style": "PULL_VIGN",       "arch": "IMPERIAL_GOLD", "badge": "INNER CALM",       "hook_title": "CALM INSIDE THE STORM",          "script": "You cannot control every gust of wind around you, yet you decide what enters your mind. When others panic or react loudly, steady breathing keeps your judgment sharp. Stay grounded in what you can influence today, and never forget that you...",                        "q": "What helps you stay calm when people around you start panicking?",             "s1": "35mm smooth pull-back dolly revealing vast ancient stone colonnade",                 "s2": "90mm rack-focus macro of heavy stone pillar and drifting dust",                   "s3": "28mm low pedestal crane shot across wet stone floor",                             "s4": "85mm profile-to-front close-up in cool atmospheric mist"},
    {"day": 9,  "fmt": "MODERN_DESK_REALISM",   "pl": "Financial Sovereignty and Relentless Discipline",     "style": "MODERN_LIFE_REAL","arch": "EMERALD_BONE",  "badge": "REAL PROGRESS",    "hook_title": "THE UNSEEN GRIND",               "script": "Nobody posts the quiet mornings when progress feels slow and invisible. That is the exact season where real discipline is formed. Keep showing up even when the scoreboard has not moved yet. Results catch up to consistency, and you...",                               "q": "What is one quiet goal you are working toward right now?",                    "s1": "35mm modern interior shot near window with warm morning light",                    "s2": "50mm close-up of pen, notebook, and desk lamp in quiet room",                    "s3": "28mm smooth dolly shot of man sitting focused at clean desk",                     "s4": "85mm close-up with calm, determined expression"},
    {"day": 10, "fmt": "MENTOR_SON_DIALOGUE",   "pl": "Father to Son: Ancient Legacy Lessons",               "style": "WARM_DRIFT",      "arch": "ROYAL_VIOLET",  "badge": "HONEST WORD",      "hook_title": "KEEP YOUR WORD SMALL",           "script": "Do not promise what you are not ready to finish. A man whose word carries weight never has to shout to be heard. Under-promise, work steadily, and let your follow-through speak for itself. Trust takes years to build, so make sure you...",                         "q": "What lesson about keeping promises do you pass on to younger people?",         "s1": "50mm warm shot of older mentor and young man at simple wooden table",              "s2": "100mm macro of hands clasping or resting firmly on wood",                       "s3": "35mm tracking shot walking side by side along courtyard path",                   "s4": "85mm close-up of mentor with warm side lighting and calm eyes"},
    {"day": 11, "fmt": "RESENTMENT_WEIGHT",     "pl": "Aging Well: Habits for Mind and Body",                "style": "PULL_VIGN",       "arch": "CRIMSON_IVORY", "badge": "LIGHTEN THE LOAD", "hook_title": "PUT DOWN OLD GRUDGES",           "script": "Holding onto old anger costs you far more than it costs the person who caused it. Years pass quickly, and carrying heavy baggage only drains your clarity today. Let go of what no longer serves your peace, because a lighter mind helps you...",                          "q": "What is one old grudge or worry you are glad you left behind?",               "s1": "35mm pull-back shot of lone figure standing on quiet cliff overlook",              "s2": "90mm macro of heavy iron chain or stone resting on ground",                      "s3": "28mm crane shot as figure turns toward open horizon",                           "s4": "85mm close-up with soft evening light and peaceful expression"},
    {"day": 12, "fmt": "GOSSIP_ROOM_RULE",      "pl": "Mastering human nature and fake friends ancient parables","style": "OVERHEAD_NOIR",  "arch": "GLACIAL_ICE",   "badge": "GUARD PRIVACY",    "hook_title": "WHO TALKS BEHIND DOORS",         "script": "Someone who gossips to you about others will eventually talk about you to someone else. Do not feed drama with your reactions or your private plans. Keep your circle small and your own counsel steady. Real discretion protects you when you...",                        "q": "How do you handle people who bring drama or gossip into your space?",         "s1": "21mm high-angle shot looking down into quiet shadowed room",                     "s2": "75mm macro of heavy wooden door closing softly",                                 "s3": "40mm overhead tracking shot along quiet corridor",                             "s4": "90mm close-up with composed, observant gaze"},
    {"day": 13, "fmt": "SUNK_COST_RELEASE",     "pl": "Financial Sovereignty and Relentless Discipline",     "style": "PUNCH_FLASH",     "arch": "FORGE_AMBER",   "badge": "CUT DEAD WEIGHT",  "hook_title": "DO NOT STAY OUT OF GUILT",       "script": "Staying in a draining situation just because you already spent time there is a costly trap. Past effort cannot buy back tomorrow's peace. Know when to pivot cleanly and put your energy where it actually grows. Wisdom shows up when you...",                            "q": "What situation did you stay in too long before finally stepping away?",         "s1": "24mm push-in on determined man standing at crossroads in dim light",             "s2": "100mm macro of scissors or blade cutting frayed cord cleanly",                   "s3": "35mm tracking arc as man steps onto new path",                                "s4": "85mm close-up with clear, decisive eyes"},
    {"day": 14, "fmt": "STILLNESS_IN_CHAOS",    "pl": "The art of moving in silence (stoic mindset)",         "style": "GOLDEN_HOUR_ARC", "arch": "IMPERIAL_GOLD", "badge": "QUIET CENTER",     "hook_title": "DO NOT MATCH THEIR VOLUME",      "script": "When someone raises their voice, matching their anger puts you on their level. Staying quiet and measured changes the entire dynamic in the room. Composure is a form of strength that loud reactions cannot fake. Hold your ground, and remember that you...",         "q": "How do you keep your voice calm when someone gets loud or defensive?",        "s1": "28mm worm's-eye golden hour shot looking up past steady figure",                 "s2": "85mm macro of calm water surface catching golden sunlight",                     "s3": "35mm tracking shot along quiet stone walkway",                                 "s4": "85mm close-up with warm sunset light and steady posture"},
    {"day": 15, "fmt": "MEMENTO_MORI_CLARITY",  "pl": "Aging Well: Habits for Mind and Body",                "style": "MONOCHROME_GRIT", "arch": "ROYAL_VIOLET",  "badge": "USE YOUR TIME",    "hook_title": "TIME DOES NOT RENEW",            "script": "Money can be earned back, but spent weeks and years return only in memory. Spend your best hours on people who matter and work that feels worthwhile. Stop postponing what you already know you should do. Live with intention today, because you...",                "q": "What is one thing you should stop putting off until next month or next year?",  "s1": "35mm monochrome shot of classic clock or sundial shadow in soft light",           "s2": "85mm macro of sand or steady tick movement in quiet light",                    "s3": "28mm wide shot of man walking purposefully along open path",                  "s4": "85mm monochrome close-up with reflective, grounded eyes"},
    {"day": 16, "fmt": "REBUILD_QUIETLY",       "pl": "Financial Sovereignty and Relentless Discipline",     "style": "MODERN_LIFE_REAL","arch": "EMERALD_BONE",  "badge": "SILENT COMEBACK",  "hook_title": "BUILD BEFORE YOU ANNOUNCE",      "script": "You do not need to announce every step before the work is finished. Quiet preparation lets you make mistakes privately and improve without pressure. Let the finished result speak when the time is right. True momentum starts when you...",                         "q": "Why do you think keeping plans private works better than announcing them?",    "s1": "35mm natural shot of man in modern room with soft daylight",                     "s2": "50mm close-up of hands writing notes in a clean journal",                       "s3": "28mm dolly shot across calm room toward window",                               "s4": "85mm close-up with quiet, confident expression"},
    {"day": 17, "fmt": "FIVE_MOMENTS_SILENCE",  "pl": "The art of moving in silence (stoic mindset)",         "style": "NORDIC_CUT",      "arch": "GLACIAL_ICE",   "badge": "FIVE PAUSES",      "hook_title": "FIVE TIMES TO PAUSE FIRST",      "script": "Pause before replying when angry, pause before judging without full facts, and pause when someone tries to pull you into pointless debate. A few seconds of restraint can save you hours of regret. Control is built in the pause, and you...",                       "q": "Which moment in your day makes a three-second pause most helpful?",           "s1": "24mm wide shot in crisp morning air on high stone ledge",                      "s2": "100mm macro of cold mist moving over dark stone",                              "s3": "50mm tracking shot along mountain ridge",                                      "s4": "105mm close-up with steady, composed gaze"},
    {"day": 18, "fmt": "FATHER_CRAFT_LEGACY",   "pl": "Father to Son: Ancient Legacy Lessons",               "style": "GOLDEN_HOUR_ARC", "arch": "IMPERIAL_GOLD", "badge": "LASTING SKILL",    "hook_title": "WHAT STAYS WHEN TITLES FADE",    "script": "Titles and trends change over time, but real skill, patience, and self-respect stay with a man for life. Master something practical and treat people fairly along the way. That kind of foundation never goes out of style, because you...",                       "q": "What skill or value has stayed useful to you across every stage of life?",     "s1": "28mm golden light shot of elder craftsman and younger learner in workshop",     "s2": "85mm macro of traditional hand tools resting on workbench",                     "s3": "35mm tracking shot through warm workshop light",                               "s4": "85mm close-up with warm golden backlight and steady look"},
    {"day": 19, "fmt": "COMPOSURE_UNDER_JABS",  "pl": "Mastering human nature and fake friends ancient parables","style": "MONOCHROME_GRIT","arch": "CRIMSON_IVORY", "badge": "STEADY NERVE",     "hook_title": "DO NOT WRESTLE IN THE MUD",      "script": "When someone runs out of solid points, they often reach for sarcasm or personal jabs to get a reaction. You do not have to accept every bait thrown your way. Stay calm, keep your dignity intact, and walk on. You stay in charge when you...",                  "q": "How do you stay composed when someone uses sarcasm to provoke you?",           "s1": "35mm monochrome medium shot in quiet courtyard",                              "s2": "85mm macro of dark water ripples settling into stillness",                      "s3": "28mm wide shot walking steadily along stone path",                            "s4": "85mm monochrome close-up with calm, unbothered eyes"},
    {"day": 20, "fmt": "COMPOUNDING_HABITS",    "pl": "Financial Sovereignty and Relentless Discipline",     "style": "OVERHEAD_NOIR",   "arch": "FORGE_AMBER",   "badge": "DAILY COMPOUND",   "hook_title": "SMALL STEPS BEAT BIG PLANS",     "script": "Big plans mean very little without small daily habits you can repeat on tired days. Focus on what you can do consistently this week rather than chasing overnight leaps. Steady effort adds up faster than people expect, and you...",                     "q": "What small daily habit has been easiest for you to keep consistent?",         "s1": "21mm overhead shot descending into quiet workspace",                          "s2": "75mm macro of clean desk items in warm side light",                            "s3": "40mm high-angle tracking shot along room edge",                               "s4": "90mm close-up with focused, grounded look"},
    {"day": 21, "fmt": "VITALITY_PACE",         "pl": "Aging Well: Habits for Mind and Body",                "style": "MODERN_LIFE_REAL","arch": "EMERALD_BONE",  "badge": "STEADY PACE",      "hook_title": "SUSTAINABLE ENERGY WINS",        "script": "Running yourself into exhaustion every week is not a badge of honor if your health and family life pay the price. Pace yourself so you can stay strong for the long haul. Real endurance is measured over years, not one sprint, so remember that you...",       "q": "How do you avoid burning out during busy weeks?",                             "s1": "35mm natural shot of man walking calmly by sunlit trees",                      "s2": "50mm close-up of sunlight filtering through green leaves",                      "s3": "28mm dolly shot along quiet park walkway",                                    "s4": "85mm close-up with relaxed, steady expression"},
    {"day": 22, "fmt": "SELF_RESPECT_BOUNDARY", "pl": "The art of moving in silence (stoic mindset)",         "style": "WARM_DRIFT",      "arch": "IMPERIAL_GOLD", "badge": "CLEAR LIMITS",     "hook_title": "RESPECT STARTS WITH BOUNDARIES", "script": "People learn how to treat you by watching what you tolerate without protest. Setting calm boundaries is not being harsh, it is respecting your own time and self-worth. Keep your boundaries clear and your temper steady, because you...",                    "q": "What boundary helped you feel more respected in your relationships?",         "s1": "50mm warm lateral drift in quiet stone courtyard",                            "s2": "100mm macro of stone archway and warm light beam",                              "s3": "35mm tracking shot walking steadily forward",                                "s4": "85mm close-up with calm, firm composure"},
    {"day": 23, "fmt": "TRUE_FRIENDSHIP_TEST",  "pl": "Mastering human nature and fake friends ancient parables","style": "PULL_VIGN",     "arch": "GLACIAL_ICE",   "badge": "REAL CIRCLE",      "hook_title": "KEEP YOUR CIRCLE GENUINE",       "script": "A crowded circle means very little if nobody is there when life gets real. Value the few people who show up honestly, speak straight, and want your good even when nothing is in it for them. Quality always beats quantity, and you...",                   "q": "What quality do you value most in a lifelong friend?",                       "s1": "35mm pull-back shot in misty coastal landscape",                             "s2": "90mm macro of calm waves rolling over dark stones",                            "s3": "28mm low crane shot across rocky ground",                                    "s4": "85mm close-up in cool slate daylight with steady eyes"},
    {"day": 24, "fmt": "MONEY_TRUTH_NO_HYPE",   "pl": "Financial Sovereignty and Relentless Discipline",     "style": "NORDIC_CUT",      "arch": "FORGE_AMBER",   "badge": "REAL WEALTH",      "hook_title": "SKIP THE FAKE FLEX",            "script": "Trying to look wealthy before you are actually free keeps many good people trapped in stress. Real confidence comes from living within your means and building breathing room. Financial calm beats outward flash every time, and you...",                         "q": "What is one status symbol or expense you realized wasn't worth it?",         "s1": "24mm wide shot in cold mountain light",                                      "s2": "100mm macro of solid stone texture in crisp light",                            "s3": "50mm tracking shot along high ridge",                                        "s4": "105mm close-up with calm, unpretentious expression"},
    {"day": 25, "fmt": "DAUGHTER_SON_WISDOM",   "pl": "Father to Son: Ancient Legacy Lessons",               "style": "MODERN_LIFE_REAL","arch": "ROYAL_VIOLET",  "badge": "LASTING EXAMPLE",  "hook_title": "THEY WATCH WHAT YOU DO",         "script": "Younger eyes watch how you handle stress, money, and hard days far more than they listen to long lectures. If you want them to grow up grounded, model calm discipline in everyday life. Example is the strongest teacher, and you...",                        "q": "What is one habit you hope the next generation picks up from you?",           "s1": "35mm natural shot near sunlit window in modern home",                        "s2": "50mm close-up of warm tea or coffee cup on table",                            "s3": "28mm dolly shot in calm, well-lit room",                                      "s4": "85mm close-up with warm, thoughtful expression"},
    {"day": 26, "fmt": "AGE_WITH_CLARITY",      "pl": "Aging Well: Habits for Mind and Body",                "style": "GOLDEN_HOUR_ARC", "arch": "EMERALD_BONE",  "badge": "CALM MATURITY",    "hook_title": "MATURITY BRINGS CLARITY",       "script": "One of the best parts of getting older is realizing how little of the daily noise actually matters. You save energy, choose your battles wisely, and value peace over proving a point. Calm experience is a real advantage, and you...",                      "q": "What feels much clearer to you now than it did ten years ago?",              "s1": "28mm golden hour shot on sunlit ridge",                                       "s2": "85mm macro of golden sunlight across trees",                                  "s3": "35mm tracking shot along peaceful path",                                      "s4": "85mm close-up in warm golden light with calm gaze"},
    {"day": 27, "fmt": "OVERTHINKING_TRAP",     "pl": "The art of moving in silence (stoic mindset)",         "style": "OVERHEAD_NOIR",   "arch": "CRIMSON_IVORY", "badge": "CLEAR THE MIND",   "hook_title": "OVERTHINKING STEALS TODAY",      "script": "Rehearsing worst-case scenarios all day rarely prepares you better—it just tires you out before anything happens. Handle what is right in front of you and leave tomorrow's worries for tomorrow. Action clears a crowded mind, and you...",                  "q": "How do you break out of overthinking when your mind starts racing?",          "s1": "21mm overhead shot in quiet shadowed courtyard",                             "s2": "75mm macro of calm dark surface with subtle light",                           "s3": "40mm high-angle tracking shot",                                             "s4": "90mm close-up with calm, focused eyes"},
    {"day": 28, "fmt": "PATIENCE_IN_SEASON",    "pl": "Mastering human nature and fake friends ancient parables","style": "WARM_DRIFT",    "arch": "IMPERIAL_GOLD", "badge": "SEASON OF GROWTH", "hook_title": "EVERY SEASON HAS ITS PACE",      "script": "Rushing a process that needs time only creates frustration and sloppy mistakes. Stay patient with your growth while staying faithful to your daily effort. Good things take root quietly before they show above ground, and you...",                         "q": "When did patience help you get a better result than rushing?",                "s1": "50mm warm lateral drift in stone workshop",                                   "s2": "100mm macro of warm light and wood grain",                                    "s3": "35mm medium tracking shot",                                                 "s4": "85mm close-up with steady, patient expression"},
    {"day": 29, "fmt": "INTEGRITY_IN_SMALLS",   "pl": "Father to Son: Ancient Legacy Lessons",               "style": "NORDIC_CUT",      "arch": "GLACIAL_ICE",   "badge": "QUIET INTEGRITY",  "hook_title": "INTEGRITY IN SMALL DETAILS",     "script": "How you handle small details when nobody is watching shows the real shape of your character. Honesty and fairness in small things build a reputation you never have to defend. Stand on solid ground every day, because you...",                           "q": "Why do small everyday choices matter so much for trust?",                     "s1": "24mm wide shot in crisp mountain air",                                        "s2": "100mm macro of clean stone and mist",                                         "s3": "50mm tracking shot along ridge",                                             "s4": "105mm close-up with calm, resolute gaze"},
    {"day": 30, "fmt": "STEADY_FORWARD_MOVEMENT","pl": "Aging Well: Habits for Mind and Body",                "style": "PUNCH_FLASH",     "arch": "FORGE_AMBER",   "badge": "KEEP MOVING",      "hook_title": "KEEP MOVING FORWARD STEADILY",   "script": "You do not need every answer today to take the next right step. Keep your standards steady, protect your peace, and move forward one honest day at a time. A composed life is built steadily, and you...",                                             "q": "What is one step you want to take this week to keep moving forward?",        "s1": "24mm push-in on resolute figure in dramatic light",                           "s2": "100mm macro of textured stone and light glints",                               "s3": "35mm tracking arc along path",                                              "s4": "85mm close-up with calm, confident eyes"}
]

DIVERSE_ARCHETYPES = [
    "A thoughtful man in his late thirties wearing a dark olive knit sweater standing by a tall modern window looking out over a sunlit city, natural candid expression. Strictly two arms only, flawless human anatomy.",
    "An elder master mentor with silver-streaked beard and calm authoritative eyes seated across a low stone table from a young apprentice in a sunlit courtyard. Strictly two arms per person, flawless human anatomy.",
    "A disciplined medieval merchant in dark wool and leather cloak inspecting a heavy iron-bound ledger chest by warm lantern light. Strictly two arms only, flawless human anatomy.",
    "A weathered seasoned craftsman in his fifties with strong forearms and calm eyes walking along a misty alpine granite ridge at sunrise. Strictly two arms only, flawless human anatomy.",
    "A composed mature man in a tailored dark coat and hat walking calmly down a quiet city street at dusk, sharp contrast and steady posture. Strictly two arms only, flawless human anatomy.",
    "An authentic mature Roman centurion with a stern weathered face, short military crop, subtle facial scar, wearing polished dark iron shoulder plates over a crimson tunic. Strictly two arms only, flawless human anatomy."
]

SETTINGS_MATRIX = [
    {"n": "Modern Sunlit Apartment & City View", "d": "Inside a calm modern living space or apartment window with natural daylight and soft depth."},
    {"n": "Quiet Neighborhood Street & Park",    "d": "Along a peaceful tree-lined street or park path in natural morning or golden-hour light."},
    {"n": "The Ancient Citadel Colonnades",      "d": "Within towering monolithic ancient stone colonnades and courtyards with dramatic light."},
    {"n": "The Windswept Coastal Cliffs",        "d": "Atop high windswept coastal cliffs overlooking ocean waves and mist."},
    {"n": "The Secluded Stone Workshop",         "d": "Inside a stone workshop with warm light, tools, and deep shadows."},
    {"n": "The Sunlit Alpine Ridge",           "d": "Along a high rocky granite ridge in crisp daylight and mist."}
]

# ---------------------------------------------------------
# 4. CADENCE & PERSISTENT DATA (05:00 & 18:00 IST OPTIMAL)
# ---------------------------------------------------------
DB_PATH = os.path.join(DATA_DIR, "video_schedule.json")
def load_db():
    d = {
        "scheduled_videos": [], 
        "used_hooks": [], 
        "used_theme_ids": [], 
        "last_scheduled_date": None, 
        "last_scheduled_slot": None, 
        "slot1_time": "05:00", 
        "slot2_time": "18:00"
    }
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                d.update(data)
        except Exception: pass
    return d

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

db = load_db()

def get_next_slot(base_d=None, base_s=None):
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    ld_str = base_d if base_d else db.get("last_scheduled_date")
    ls = base_s if base_s else db.get("last_scheduled_slot")
    s1_t, s2_t = db.get("slot1_time", "05:00"), db.get("slot2_time", "18:00")
    if ld_str and ls:
        try: ld = datetime.strptime(str(ld_str), "%Y-%m-%d").date()
        except Exception: ld = now_ist.date()
        if "SLOT 1" in str(ls).upper():
            return ld.strftime("%Y-%m-%d"), "SLOT 2 (EVENING)", s2_t
        else:
            return (ld + timedelta(days=1)).strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t
    else:
        td = now_ist.date()
        t1 = dt_time(int(s1_t.split(":")[0]), int(s1_t.split(":")[1]))
        t2 = dt_time(int(s2_t.split(":")[0]), int(s2_t.split(":")[1]))
        if now_ist.time() < t1: return td.strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t
        elif now_ist.time() < t2: return td.strftime("%Y-%m-%d"), "SLOT 2 (EVENING)", s2_t
        else: return (td + timedelta(days=1)).strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t

target_d, target_s, target_t = get_next_slot()

# ---------------------------------------------------------
# 5. BUILT-IN EXCEL TRACKER ENGINE
# ---------------------------------------------------------
def append_to_excel_tracker(row_data):
    if not OPENPYXL_AVAILABLE:
        return False
    headers = [
        "Video ID", "Target Date", "Slot (IST)", "YouTube Status", "Meta Status",
        "Assigned Playlist", "Concept Title", "Hook Banner", "Drive Batch Folder",
        "Video Link / Path", "Thumbnail Link / Path", "YouTube Title", "YouTube Description",
        "YouTube Tags", "YouTube Pinned Comment", "Meta Reel Caption (One-Box)",
        "Meta First Comment", "Director Visual FX", "Notes / Link to Post"
    ]
    if os.path.exists(EXCEL_TRACKER_PATH):
        try:
            wb = openpyxl.load_workbook(EXCEL_TRACKER_PATH)
            ws = wb["Content & Schedule Tracker"] if "Content & Schedule Tracker" in wb.sheetnames else wb.active
        except Exception:
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Content & Schedule Tracker"
            ws.append(headers)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Content & Schedule Tracker"
        ws.append(headers)
    last_r = ws.max_row
    next_id = f"EV-{last_r:03d}"
    ws.append([
        row_data.get("videoId", next_id), row_data.get("targetDate", ""), row_data.get("slot", ""),
        row_data.get("ytStatus", "Ready in Drive"), row_data.get("metaStatus", "Ready in Drive"),
        row_data.get("playlist", ""), row_data.get("titleConcept", ""), row_data.get("hookBanner", ""),
        row_data.get("driveFolder", ""), row_data.get("videoLink", ""), row_data.get("thumbLink", ""),
        row_data.get("ytTitle", ""), row_data.get("ytDesc", ""), row_data.get("ytTags", ""),
        row_data.get("ytPinned", ""), row_data.get("metaCaption", ""), row_data.get("metaComment", ""),
        row_data.get("directorFx", ""), row_data.get("notes", "Staged in Drive")
    ])
    wb.save(EXCEL_TRACKER_PATH)
    return True

# ---------------------------------------------------------
# 6. NATURAL HUMAN AUDIO & SUBTITLE ENGINE
# ---------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_fast_gemini_client(clean_k):
    try:
        return genai.Client(api_key=clean_k, http_options=types.HttpOptions(timeout=15000))
    except Exception:
        return genai.Client(api_key=clean_k)

def normalize_spoken_text(text):
    t = text.replace("...", ".").replace("…", ".")
    t = t.replace("—", ", ").replace("–", ", ").replace(" / ", ", ")
    t = re.sub(r"\s+", " ", t).strip()
    return t

def synthesize_with_gemini_audio(api_key, text, audio_path, voice_name="Charon"):
    clean_k = api_key.strip().strip('"').strip("'")
    if not clean_k: return False, None
    client = get_fast_gemini_client(clean_k)
    target_voice = "Charon" if "Charon" in voice_name else "Fenrir"
    spoken = normalize_spoken_text(text)
    for m in ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]:
        try:
            res = client.models.generate_content(
                model=m,
                contents=f"Read this naturally at a calm, unhurried conversational pace with clear pauses at periods and commas: {spoken}",
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=target_voice)
                        )
                    )
                )
            )
            for cand in res.candidates:
                for part in cand.content.parts:
                    if part.inline_data and part.inline_data.data:
                        raw_data = part.inline_data.data
                        raw_file = audio_path + ".gemini.raw"
                        with open(raw_file, "wb") as f: f.write(raw_data)
                        if raw_data[:4] == b"RIFF":
                            subprocess.run(['ffmpeg', '-y', '-i', raw_file, '-c:a', 'libmp3lame', '-b:a', '192k', audio_path], capture_output=True, check=True)
                        else:
                            subprocess.run(['ffmpeg', '-y', '-f', 's16le', '-ar', '24000', '-ac', '1', '-i', raw_file, '-c:a', 'libmp3lame', '-b:a', '192k', audio_path], capture_output=True, check=True)
                        if os.path.exists(raw_file): os.remove(raw_file)
                        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 3000:
                            return True, f"Gemini Natural ({target_voice} US Male)"
        except Exception:
            continue
    return False, None

async def synthesize_speech_timed(text, audio_path, primary_voice="Gemini-Charon", api_key="", use_gemini_tts=True):
    spoken = normalize_spoken_text(text)
    if api_key and use_gemini_tts and "Gemini" in primary_voice:
        ok, v_desc = synthesize_with_gemini_audio(api_key, spoken, audio_path, voice_name=primary_voice)
        if ok: return [], v_desc
    try:
        comm = edge_tts.Communicate(spoken, voice="en-US-ChristopherNeural", rate="+0%", pitch="-2Hz")
        timings = []
        with open(audio_path, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio": f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    st_s = chunk["offset"] / 10_000_000.0
                    dur_s = chunk["duration"] / 10_000_000.0
                    timings.append({"word": chunk.get("text", ""), "start": round(st_s, 3), "end": round(st_s + dur_s, 3)})
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 6000:
            return timings, "Christopher Natural (US Male)"
    except Exception: pass
    cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '18.5', '-c:a', 'libmp3lame', audio_path]
    subprocess.run(cmd, capture_output=True)
    return [], "Ambient Timing Bed"

def build_ass_subtitles(timed_words, script_text, ass_path, total_dur, arch_key="IMPERIAL_GOLD"):
    arch_cfg = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])
    color = arch_cfg["ass_primary"]
    ass_font = arch_cfg.get("ass_font", "DejaVu Sans")
    ass_size = arch_cfg.get("ass_size", 74)
    ass_outline = arch_cfg.get("ass_outline", "&H00000000")
    events = []

    if timed_words and len(timed_words) >= 5:
        clean_words = []
        for tw in timed_words:
            raw_w = tw['word'].replace("—", " ").replace("–", " ").replace("-", " ").replace("...", " ")
            w_txt = re.sub(r"[^\w\s',.!?]", "", raw_w).upper().strip()
            if w_txt:
                for sub_w in w_txt.split():
                    clean_words.append({'word': sub_w, 'start': tw['start'], 'end': tw['end']})
        chunk = []
        for i, tw in enumerate(clean_words):
            chunk.append(tw)
            is_punct = any(tw['word'].endswith(p) for p in ['.', '!', '?', ':', ';', ','])
            has_pause = (i + 1 < len(clean_words)) and (clean_words[i + 1]['start'] - tw['end'] >= 0.25)
            if is_punct or has_pause or len(chunk) >= 3:
                st_t = chunk[0]['start']
                en_t = clean_words[i + 1]['start'] if i + 1 < len(clean_words) else min(total_dur, chunk[-1]['end'] + 0.3)
                txt = " ".join([c['word'] for c in chunk]).strip()
                if txt: events.append((st_t, en_t, txt))
                chunk = []
        if chunk:
            st_t = chunk[0]['start']
            en_t = min(total_dur, chunk[-1]['end'] + 0.3)
            txt = " ".join([c['word'] for c in chunk]).strip()
            if txt: events.append((st_t, en_t, txt))
    else:
        clean_s = normalize_spoken_text(script_text)
        tokens = clean_s.split()
        token_groups = [tokens[i:i + 3] for i in range(0, len(tokens), 3)]
        vocal_start = 0.35
        step = max(0.45, (total_dur - vocal_start - 0.35) / max(1, len(token_groups)))
        for idx, grp in enumerate(token_groups):
            st_t = vocal_start + (idx * step)
            en_t = min(total_dur, vocal_start + ((idx + 1) * step))
            txt = re.sub(r"[^\w\s',.!?]", "", " ".join(grp)).upper().strip()
            if txt: events.append((st_t, en_t, txt))

    def fmt(s): return f"{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}"
    ass_doc = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{ass_font},{ass_size},{color},&H000000FF,{ass_outline},&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,50,50,420,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    for st_t, en_t, txt in events: ass_doc += f"Dialogue: 0,{fmt(st_t)},{fmt(en_t)},Default,,0,0,0,,{txt}\n"
    with open(ass_path, "w", encoding="utf-8") as f: f.write(ass_doc)
    return events

if "active_video_pkg" not in st.session_state and os.path.exists(DRAFT_JSON_PATH):
    try:
        with open(DRAFT_JSON_PATH, "r", encoding="utf-8") as f: d_data = json.load(f)
        d_data["audio"] = DRAFT_AUDIO_PATH
        st.session_state["active_video_pkg"] = d_data
    except Exception: pass

if "rendered_video_path" not in st.session_state:
    master_p = os.path.join(TMP_DIR, "master_output.mp4")
    if os.path.exists(master_p) and os.path.getsize(master_p) > 10000:
        st.session_state["rendered_video_path"] = master_p

# ---------------------------------------------------------
# 7. NON-REPETITIVE 30-DAY PACKAGE BUILDER & AI GENERATOR
# ---------------------------------------------------------
def build_package_from_day_entry(entry, custom_char=None, custom_setting=None):
    style_key = entry["style"]
    style_meta = CINEMATOGRAPHY_MATRIX.get(style_key, CINEMATOGRAPHY_MATRIX["MODERN_LIFE_REAL"])
    char_desc = custom_char or random.choice(DIVERSE_ARCHETYPES)
    sett_desc = custom_setting or random.choice(SETTINGS_MATRIX)["d"]
    hook_caps = entry["hook_title"].upper()

    return {
        "title_concept": f"Day {entry['day']}: {entry['hook_title'].title()} ({entry['fmt']})",
        "playlist": entry["pl"],
        "hook_banner": hook_caps,
        "video_overlay_text": entry["badge"],
        "subtitle_archetype": entry["arch"],
        "director_style": style_key,
        "script": entry["script"],
        "scene1_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s1']}. Context: {sett_desc}. {style_meta['grade']}. Flawless anatomy, strictly two arms.",
        "scene2_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s2']}. {style_meta['grade']}. Crisp focus and natural motion.",
        "scene3_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s3']}. Same protagonist ({char_desc[:75]}). {style_meta['grade']}. Strictly two arms.",
        "scene4_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s4']}. Same protagonist across scenes. {style_meta['grade']}.",
        "thumbnail_prompt": (
            f"9:16 vertical cinematic frame featuring {char_desc} in {sett_desc}. "
            f"Upper-third bold text reading: \"{hook_caps}\" in {SUBTITLE_ARCHETYPES.get(entry['arch'], SUBTITLE_ARCHETYPES['IMPERIAL_GOLD'])['label'].split(' ', 1)[1]} tone with clean shadow, clear of face, no bottom text."
        ),
        "youtube_title": f"⚡ {entry['hook_title'].title()} #shorts #mindset",
        "youtube_description": f"{entry['script']}\n\n💭 {entry['q']}\n\nSubscribe to {get_persistent_yt_handle()} for daily life lessons.\n\n#mindset #lifelessons #selfgrowth #shorts",
        "youtube_tags": "life lessons, personal growth, mindset, emotional control, discipline, daily reflection, shorts",
        "youtube_pinned_comment": f"💭 {entry['q']}",
        "caption_hook": entry["hook_title"].title(),
        "caption_lesson": entry["script"],
        "reflection_question": entry["q"],
        "meta_hashtags": "#Mindset #LifeLessons #PersonalGrowth #SelfRespect #Wisdom"
    }

def generate_varied_package(raw_api_key, day_entry, custom_char=None, custom_setting=None):
    clean_key = raw_api_key.strip().strip('"').strip("'") if raw_api_key else ""
    base_pkg = build_package_from_day_entry(day_entry, custom_char, custom_setting)
    if not clean_key:
        return base_pkg, f"30-Day Non-Repeating Vault (Day {day_entry['day']} - {day_entry['fmt']})"

    used_h = "\n".join([f"- {h}" for h in db.get("used_hooks", [])[-40:]]) or "None."
    style_meta = CINEMATOGRAPHY_MATRIX.get(day_entry["style"], CINEMATOGRAPHY_MATRIX["MODERN_LIFE_REAL"])

    prompt = (
        f"You are writing a fresh, non-repetitive 18-20 second short-form reel script for an audience of men aged 35-65+ in the US, UK, Canada, and Australia.\n"
        f"DAY FORMAT / ANGLE: {day_entry['fmt']} | STYLE: {style_meta['label']} | PILLAR: {day_entry['pl']}\n"
        f"INSPIRATION SEED: {day_entry['hook_title']} — {day_entry['script']}\n"
        f"FORBIDDEN HOOKS (DO NOT REPEAT): {used_h}\n"
        f"RULES:\n"
        f"1. Write a natural, conversational spoken script of 45 to 52 words that sounds human when read aloud—never stiff, preachy, or robotic. Do NOT force every video to start with the exact same hook phrase.\n"
        f"2. Use clean commas and periods (avoid em-dashes or ellipses that cause voice pauses/breaks).\n"
        f"3. Include a concrete real-world shift around second 4 and an open, thoughtful reflection question (no 'Drop 1 or 2' or numeric polls).\n"
        f"4. Keep all 4 scene prompts starting with '[4-second vertical 9:16 cinematic video clip]' and matching {style_meta['grade']}.\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        "{\n"
        '  "title_concept": "Short title",\n'
        '  "hook_banner": "3-5 WORD TITLE",\n'
        '  "video_overlay_text": "2-3 WORD BADGE",\n'
        '  "script": "45-52 word conversational script with natural punctuation.",\n'
        '  "scene1_prompt": "[4-second vertical 9:16 cinematic video clip] ...",\n'
        '  "scene2_prompt": "[4-second vertical 9:16 cinematic video clip] ...",\n'
        '  "scene3_prompt": "[4-second vertical 9:16 cinematic video clip] ...",\n'
        '  "scene4_prompt": "[4-second vertical 9:16 cinematic video clip] ...",\n'
        '  "thumbnail_prompt": "...",\n'
        '  "youtube_title": "...",\n'
        '  "reflection_question": "Open-ended question?"\n'
        "}"
    )

    try:
        client = get_fast_gemini_client(clean_key)
        for m in ["gemini-3.8-flash", "gemini-3.8-flash-lite"]:
            try:
                cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.92, max_output_tokens=1500)
                r = client.models.generate_content(model=m, contents=prompt, config=cfg)
                raw = r.text.strip()
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                parsed = json.loads(match.group(0) if match else raw)
                if isinstance(parsed, dict) and "script" in parsed:
                    merged = dict(base_pkg)
                    for k, v in parsed.items():
                        if v: merged[k] = v
                    return merged, f"Gemini AI + Day {day_entry['day']} ({day_entry['fmt']})"
            except Exception:
                continue
    except Exception:
        pass

    return base_pkg, f"30-Day Non-Repeating Vault (Day {day_entry['day']} - {day_entry['fmt']})"

# ---------------------------------------------------------
# 8. HEADER & SETTINGS
# ---------------------------------------------------------
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 600;">v9.2 // CREDIT-SAFE PERSISTENT CLIPS, SCRIPT, AUDIO & FULL EXPORTS</span>
</div>
""", unsafe_allow_html=True)

recent_ids = db.get("used_theme_ids", [])[-30:]
st.markdown(f"""
<div style="margin-bottom: 14px;">
    <span class="badge badge-green">● 30 UNIQUE DAILY FORMATS</span>
    <span class="badge badge-purple">🎙️ NATURAL PACING AUDIO</span>
    <span class="badge badge-blue">✨ FULL METADATA & EXPORTS</span>
    <span class="badge badge-amber">📅 {target_d} @ {target_t} IST ({target_s})</span>
</div>
""", unsafe_allow_html=True)

if "status_banner" in st.session_state:
    st.success(st.session_state.pop("status_banner"))

curr_saved_key = get_persistent_api_key()
curr_gsheet_url = get_persistent_gsheet_url()
curr_yt_handle = get_persistent_yt_handle()
curr_meta_handle = get_persistent_meta_handle()

with st.expander("🔑 API CREDENTIALS, PLATFORM HANDLES & SYNC", expanded=(not bool(curr_saved_key))):
    uk = st.text_input("Gemini API Key", value=curr_saved_key, type="password", placeholder="AIzaSy...", key="user_key_input")
    if uk:
        save_persistent_api_key(uk)
        st.caption("✓ Gemini API Key active")

    st.divider()
    st.markdown("#### 🏛️ Platform-Specific Brand Handles (Rule Locked)")
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        u_yt = st.text_input("YouTube Shorts Handle", value=curr_yt_handle, placeholder="@AJ-Echoes-of-Wisdom", key="user_yt_handle_input")
        if u_yt != curr_yt_handle:
            save_persistent_yt_handle(u_yt)
    with col_h2:
        u_meta = st.text_input("Facebook & Instagram Handle", value=curr_meta_handle, placeholder="@EchoesOfWisdomOfficial", key="user_meta_handle_input")
        if u_meta != curr_meta_handle:
            save_persistent_meta_handle(u_meta)

    st.divider()
    gurl = st.text_input("Google Sheets Webhook URL (Optional)", value=curr_gsheet_url, placeholder="https://script.google.com/macros/s/.../exec", key="user_sheet_url")
    if gurl:
        save_persistent_gsheet_url(gurl)

def render_copy(bid, label, text):
    b64_val = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    components.html(f"""
    <div style="margin: 0; padding: 0;">
        <button id="b_{bid}" onclick="copyFromB64('{bid}', '{b64_val}', '{label}')" style="width:100%;height:2.6rem;background:rgba(56,189,248,0.12);color:#38BDF8;border:1px solid rgba(56,189,248,0.35);border-radius:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-weight:700;font-size:12px;cursor:pointer;letter-spacing:0.02em;">
            📋 {label}
        </button>
    </div>
    <script>
    function copyFromB64(id, b64, lbl) {{
        const decoded = decodeURIComponent(escape(window.atob(b64)));
        navigator.clipboard.writeText(decoded).then(() => {{
            const el = document.getElementById('b_' + id);
            el.innerText = '✓ COPIED!';
            el.style.background = '#059669';
            el.style.color = '#FFF';
            setTimeout(() => {{
                el.innerText = '📋 ' + lbl;
                el.style.background = 'rgba(56,189,248,0.12)';
                el.style.color = '#38BDF8';
            }}, 2000);
        }});
    }}
    </script>
    """, height=48)

# ---------------------------------------------------------
# 9. TABS
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["⚡ 1. 30-DAY SCRIPT & PROMPTS", "🎬 2. RENDER, CROP & METADATA", "📋 3. QUEUE LEDGER & TRACKER"])

with tab1:
    if "active_video_pkg" in st.session_state:
        with st.expander("✏️ EDIT CURRENT ACTIVE SCRIPT & VOICEOVER (KEEP EXISTING CLIPS)", expanded=False):
            cur_p = st.session_state["active_video_pkg"]
            cur_pkg = cur_p.get("pkg", {})
            ed_hook = st.text_input("Current Hook / Title", value=cur_pkg.get("hook_banner", ""), key="ed_cur_hook")
            ed_scr = st.text_area("Current Spoken Script", value=cur_pkg.get("script", ""), height=95, key="ed_cur_scr")
            ed_q = st.text_input("Current Reflection Question", value=cur_pkg.get("reflection_question", ""), key="ed_cur_q")
            if st.button("💾 Update Script & Re-Sync Audio (Keep Clips)", key="btn_upd_cur_scr"):
                cur_pkg["hook_banner"] = ed_hook.strip().upper()
                cur_pkg["script"] = ed_scr.strip()
                cur_pkg["reflection_question"] = ed_q.strip()
                cur_p["pkg"] = cur_pkg
                timings, v_name = asyncio.run(synthesize_speech_timed(cur_pkg["script"], DRAFT_AUDIO_PATH, api_key=get_persistent_api_key(), use_gemini_tts=False))
                cur_p["timings"] = timings
                cur_p["voice_used"] = v_name
                with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(cur_p, f, indent=2)
                st.session_state["active_video_pkg"] = cur_p
                st.success("✓ Script & audio updated while keeping your saved video clips!")
                st.rerun()

    st.markdown("### 📅 30-Day Non-Repeating Format Selector")
    day_mode = st.radio(
        "Selection Mode",
        ["🎲 Auto-Next Unused Day (No Repeat Across 30 Days)", "🗓️ Pick Specific Day (Day 1 to Day 30)"],
        horizontal=True
    )

    if "Auto-Next" in day_mode:
        unused_days = [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" not in recent_ids]
        selected_day_obj = unused_days[0] if unused_days else THIRTY_DAY_CURRICULUM[len(recent_ids) % len(THIRTY_DAY_CURRICULUM)]
    else:
        day_num = st.selectbox("Select Day (1–30)", [d["day"] for d in THIRTY_DAY_CURRICULUM], format_func=lambda n: f"Day {n:02d} — {THIRTY_DAY_CURRICULUM[n-1]['fmt']}")
        selected_day_obj = THIRTY_DAY_CURRICULUM[day_num - 1]

    col_c1, col_c2 = st.columns(2)
    with col_c1:
        chosen_arch_opt = st.selectbox("Subtitle Font & Color", ["📅 Day Preset"] + list(SUBTITLE_ARCHETYPES.keys()), format_func=lambda x: "📅 Day Preset" if x == "📅 Day Preset" else SUBTITLE_ARCHETYPES[x]["label"])
    with col_c2:
        chosen_style_opt = st.selectbox("Camera & Color Grade", ["📅 Day Preset"] + list(CINEMATOGRAPHY_MATRIX.keys()), format_func=lambda x: "📅 Day Preset" if x == "📅 Day Preset" else CINEMATOGRAPHY_MATRIX[x]["label"])

    voice_mode = st.radio(
        "Voice Delivery Mode (Natural Human Pacing)",
        [
            "🎙️ Natural Conversational Voice (Edge-TTS Calm Pace, 0% Rush)",
            "🔊 Gemini AI Voice (Deep Stoic Male, Calm Pauses)"
        ],
        index=0
    )

    if st.button("🚀 Generate Non-Repeating Day Package & Audio", type="primary"):
        k = get_persistent_api_key()
        use_gem = "Gemini AI Voice" in voice_mode
        with st.status("⚡ Building non-repeating format & natural human voice...", expanded=True) as status:
            run_entry = dict(selected_day_obj)
            if chosen_arch_opt != "📅 Day Preset":
                run_entry["arch"] = chosen_arch_opt
            if chosen_style_opt != "📅 Day Preset":
                run_entry["style"] = chosen_style_opt

            pkg, eng_src = generate_varied_package(k, run_entry)
            timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k, use_gemini_tts=use_gem))
            status.update(label="✅ Ready!", state="complete", expanded=False)

            draft_data = {
                "pkg": pkg,
                "t_id": f"DAY_{run_entry['day']:02d}",
                "p": run_entry["fmt"],
                "pl": run_entry["pl"],
                "m": run_entry["s2"],
                "s": run_entry["style"],
                "audio": DRAFT_AUDIO_PATH,
                "timings": timings,
                "voice_used": v_name,
                "engine_source": eng_src,
                "date": target_d,
                "slot": target_s,
                "time": target_t
            }
            with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f:
                json.dump(draft_data, f, indent=2)
            save_to_draft_vault(draft_data)
            st.session_state["active_video_pkg"] = draft_data
            st.session_state["rendered_director_style"] = run_entry["style"]
            st.session_state.pop("rendered_video_path", None)
            st.rerun()

    if "active_video_pkg" in st.session_state:
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data.get("pkg", {})
        st.divider()
        st.subheader(f"📜 {pkg.get('title_concept', 'Daily Reel')}")
        st.caption(f"Engine: `{p_data.get('engine_source', '')}` | Voice: `{p_data.get('voice_used', '')}`")
        st.info(f"**Spoken Script:**\n\n*{pkg.get('script')}*\n\n**Reflection Question:** *{pkg.get('reflection_question', '')}*")

        if os.path.exists(DRAFT_AUDIO_PATH):
            st.audio(DRAFT_AUDIO_PATH)

        custom_voice = st.file_uploader("Optional: Upload Your Own Recorded Voice MP3", type=["mp3"])
        if custom_voice:
            with open(DRAFT_AUDIO_PATH, "wb") as f:
                f.write(custom_voice.read())
            p_data["timings"] = []
            st.success("✓ Custom voice MP3 loaded!")
            st.rerun()

        for i, (lbl, k_name) in enumerate([
            ("SCENE 1", "scene1_prompt"),
            ("SCENE 2", "scene2_prompt"),
            ("SCENE 3", "scene3_prompt"),
            ("SCENE 4", "scene4_prompt"),
            ("THUMBNAIL", "thumbnail_prompt")
        ]):
            st.text_area(lbl, pkg.get(k_name, ""), height=72)
            render_copy(f"d30_{i}", f"COPY {lbl}", pkg.get(k_name, ""))

SAVED_CLIPS_DIR = os.path.join(DATA_DIR, "saved_clips")
os.makedirs(SAVED_CLIPS_DIR, exist_ok=True)

def get_persisted_clips():
    if not os.path.exists(SAVED_CLIPS_DIR):
        return []
    return sorted([os.path.join(SAVED_CLIPS_DIR, f) for f in os.listdir(SAVED_CLIPS_DIR) if f.lower().endswith((".mp4", ".mov"))])

with tab2:
    st.markdown("### 📥 1. Upload or Reuse Saved Video Clips (Credit-Safe Vault)")
    uploaded_clips = st.file_uploader("Drop 2 to 10+ clips (auto-saved to disk so you never lose credits)", type=["mp4", "mov"], accept_multiple_files=True)
    if uploaded_clips:
        # Clear old saved clips only when user explicitly uploads a new batch
        for old_f in os.listdir(SAVED_CLIPS_DIR):
            try: os.remove(os.path.join(SAVED_CLIPS_DIR, old_f))
            except Exception: pass
        for idx, c in enumerate(sorted(uploaded_clips, key=lambda x: x.name)):
            dest_p = os.path.join(SAVED_CLIPS_DIR, f"clip_{idx:02d}_{c.name}")
            with open(dest_p, "wb") as f:
                f.write(c.read())

    persisted_clip_paths = get_persisted_clips()
    # Also check TMP_DIR fallback if user already rendered before upgrading
    if not persisted_clip_paths and os.path.exists(TMP_DIR):
        tmp_found = sorted([os.path.join(TMP_DIR, f) for f in os.listdir(TMP_DIR) if f.startswith("clip_") and f.endswith(".mp4")])
        if tmp_found:
            persisted_clip_paths = tmp_found

    num_clips = len(persisted_clip_paths)
    if num_clips > 0:
        col_cl1, col_cl2 = st.columns([3, 1])
        with col_cl1:
            st.success(f"✓ {num_clips} saved video clip(s) locked in vault: {', '.join([os.path.basename(p) for p in persisted_clip_paths])}")
        with col_cl2:
            if st.button("🗑️ Clear Saved Clips", key="btn_clear_saved_clips"):
                for p in persisted_clip_paths:
                    try: os.remove(p)
                    except Exception: pass
                st.rerun()

    active_style_key = st.session_state.get("rendered_director_style", "MODERN_LIFE_REAL")
    chosen_director_fx = st.selectbox(
        "Color Grade & Transition Archetype",
        list(CINEMATOGRAPHY_MATRIX.keys()),
        format_func=lambda x: CINEMATOGRAPHY_MATRIX[x]["label"],
        index=list(CINEMATOGRAPHY_MATRIX.keys()).index(active_style_key) if active_style_key in CINEMATOGRAPHY_MATRIX else 0
    )

    col_o1, col_o2, col_o3 = st.columns(3)
    with col_o1: show_top_badge = st.checkbox("Show Top Badge (0–3.2s)", value=False)
    with col_o2: enable_vignette = st.checkbox("Optical Vignette", value=True)
    with col_o3: enable_film_grain = st.checkbox("35mm Film Grain", value=True)

    if st.button("🎬 Render Master 9:16 Reel", type="primary"):
        if "active_video_pkg" not in st.session_state:
            st.error("Generate or restore a script package in Tab 1 first.")
        elif num_clips < 2:
            st.error("Upload at least 2 video clips.")
        else:
            with st.spinner("⚡ Rendering master 9:16 reel from your saved clips..."):
                p_data = st.session_state["active_video_pkg"]
                pkg = p_data["pkg"]
                arch_key = pkg.get("subtitle_archetype", "IMPERIAL_GOLD")
                arch = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])
                c_paths = list(persisted_clip_paths)

                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', DRAFT_AUDIO_PATH], capture_output=True, text=True)
                dur = (float(probe.stdout.strip()) if probe.stdout.strip() else 18.5) + 0.4
                clip_speed = (dur / float(num_clips)) / 4.0

                ass_p = os.path.join(TMP_DIR, "subtitles.ass")
                build_ass_subtitles(p_data.get("timings", []), pkg["script"], ass_p, dur, arch_key)
                clean_ass_path = ass_p.replace("'", "\\'").replace(":", "\\:")
                clean_fonts_dir = FONTS_DIR.replace("'", "\\'").replace(":", "\\:")
                out_p = os.path.join(TMP_DIR, "master_output.mp4")

                v_filters = []
                for i in range(num_clips):
                    fl = [
                        "trim=0:4",
                        f"setpts=(PTS-STARTPTS)*{clip_speed:.4f}",
                        "scale=1224:2174:force_original_aspect_ratio=increase",
                        "crop=1080:1920:(in_w-1080)/2:0",
                        "fps=25"
                    ]
                    if enable_vignette: fl.append("vignette=PI/4")
                    if enable_film_grain: fl.append("noise=alls=3:allf=t+u")
                    eq_f = CINEMATOGRAPHY_MATRIX.get(chosen_director_fx, {}).get("ffmpeg_eq")
                    if eq_f: fl.append(eq_f)
                    v_filters.append(f"[{i}:v]" + ",".join(fl) + f"[v{i}];")

                v_filters.append("".join([f"[v{i}]" for i in range(num_clips)]) + f"concat=n={num_clips}:v=1:a=0[vb];")
                if show_top_badge:
                    b_txt = pkg.get("video_overlay_text", "INSIGHT").replace("'", "\\'").replace(":", "\\:")
                    v_filters.append(f"[vb]drawtext=text='{b_txt}':fontsize=34:fontcolor={arch['banner_hex']}:shadowx=2:shadowy=3:shadowcolor=black@0.85:x=(w-text_w)/2:y=160:enable='between(t,0,3.0)',ass='{clean_ass_path}':fontsdir='{clean_fonts_dir}'[vout]")
                else:
                    v_filters.append(f"[vb]ass='{clean_ass_path}':fontsdir='{clean_fonts_dir}'[vout]")

                inputs = []
                for cp in c_paths: inputs.extend(['-i', cp])
                inputs.extend(['-i', DRAFT_AUDIO_PATH])
                audio_idx = num_clips

                v_filters.append(f";[{audio_idx}:a]loudnorm=I=-14:TP=-1.0:LRA=7[aout]")
                res = subprocess.run([
                    'ffmpeg', '-y', *inputs,
                    '-filter_complex', "".join(v_filters),
                    '-map', '[vout]', '-map', '[aout]',
                    '-t', str(dur),
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2', '-crf', '22',
                    '-c:a', 'aac', '-b:a', '192k', '-pix_fmt', 'yuv420p', out_p
                ], capture_output=True, text=True)

                if res.returncode != 0:
                    st.error(f"FFmpeg Error: {res.stderr[:300]}")
                else:
                    st.session_state["rendered_video_path"] = out_p
                    st.success("✓ Master 9:16 Reel Rendered!")

    # Thumbnail Cropper & Downloader (always accessible in Tab 2)
    st.divider()
    st.markdown("### 🖼️ 2. Thumbnail Cropper & Download")
    cur_pkg_for_thumb = st.session_state.get("active_video_pkg", {}).get("pkg", {})
    cur_slug_thumb = re.sub(r'[^a-zA-Z0-9]+', '_', cur_pkg_for_thumb.get('hook_banner', 'reel')).strip('_').lower()
    thumb_file = st.file_uploader("Upload Raw Thumbnail Image", type=["png", "jpg", "jpeg", "webp"], key="v91_thumb_up")
    SAVED_THUMB_PATH = os.path.join(DATA_DIR, "saved_raw_thumb.png")
    if thumb_file:
        with open(SAVED_THUMB_PATH, "wb") as tf:
            tf.write(thumb_file.read())
    active_thumb_source = SAVED_THUMB_PATH if os.path.exists(SAVED_THUMB_PATH) else None

    if active_thumb_source:
        try:
            tim = Image.open(active_thumb_source).convert("RGB")
            tw, th = tim.size
            crop_mode = st.radio(
                "Bottom Watermark Crop",
                ["Standard (6.5% Bottom Crop)", "Deep (12.5% Bottom Crop)"],
                horizontal=True,
                key="v91_crop_mode"
            )
            pct = 0.125 if "Deep" in crop_mode else 0.065
            ch = th - int(th * pct)
            cw = int(ch * (9.0 / 16.0))
            mx = max(0, (tw - cw) // 2)
            clean_thumb = tim.crop((mx, 0, mx + cw, ch)).resize((1080, 1920), Image.Resampling.LANCZOS)
            st.image(clean_thumb, caption="Cleaned 9:16 Thumbnail Preview", use_container_width=True)
            t_buf = io.BytesIO()
            clean_thumb.save(t_buf, format="PNG", quality=98)
            t_name = f"{target_d.replace('-','')}_{cur_slug_thumb}_thumb.png"
            st.download_button(f"💾 Download Cropped Thumbnail ({t_name})", t_buf.getvalue(), t_name, "image/png", key="v91_thumb_dl")
        except Exception as e:
            st.warning(f"Could not process thumbnail: {e}")

    # Rendered Video Preview, Download & Metadata (shown whenever rendered_video_path exists OR active_video_pkg is loaded)
    has_rendered = "rendered_video_path" in st.session_state and os.path.exists(st.session_state["rendered_video_path"])
    has_pkg = "active_video_pkg" in st.session_state

    if has_rendered:
        st.divider()
        st.markdown("### 🎥 3. Rendered Master Reel & Download")
        vp = st.session_state["rendered_video_path"]
        st.video(vp)
        slot_code = "S1" if "SLOT 1" in target_s else "S2"
        pl_name_cur = st.session_state.get("active_video_pkg", {}).get("pkg", {}).get("playlist", "The art of moving in silence (stoic mindset)")
        pl_code = "SILENCE" if "silence" in pl_name_cur.lower() else ("PARABLES" if "parables" in pl_name_cur.lower() else ("FINANCE" if "financial" in pl_name_cur.lower() else ("LEGACY" if "father" in pl_name_cur.lower() else "AGING")))
        exp_name = f"{target_d}_{slot_code}_{pl_code}_{cur_slug_thumb}.mp4"
        with open(vp, "rb") as f:
            st.download_button(f"💾 Download Master Reel ({exp_name})", f.read(), exp_name, "video/mp4", key="v91_vid_dl")

    if has_pkg:
        pkg = st.session_state["active_video_pkg"]["pkg"]
        pl_name = pkg.get("playlist", "The art of moving in silence (stoic mindset)")
        q_ref = pkg.get("reflection_question", "")
        raw_hook = pkg.get("hook_banner", "DAILY INSIGHT").title()
        yt_title = pkg.get("youtube_title", f"⚡ {raw_hook} #shorts #mindset")

        st.divider()
        st.markdown("### 📝 4. Complete Metadata & Copy Suite")

        st.text_input("YouTube Title", yt_title, key="v91_yt_title")
        render_copy("v91_ytt", "COPY YOUTUBE TITLE", yt_title)

        yt_desc = f"{pkg.get('script','')}\n\n💭 {q_ref}\n\nSubscribe to {get_persistent_yt_handle()} for daily life lessons.\n\n#mindset #lifelessons #selfgrowth #shorts"
        st.text_area("YouTube Description (@AJ-Echoes-of-Wisdom)", yt_desc, height=115, key="v91_yt_desc")
        render_copy("v91_ytd", "COPY YOUTUBE DESCRIPTION", yt_desc)

        st.text_input("YouTube Playlist", pl_name, key="v91_yt_pl")
        render_copy("v91_ytp", "COPY YOUTUBE PLAYLIST", pl_name)

        yt_tags = pkg.get("youtube_tags", "life lessons, personal growth, mindset, emotional control, discipline, shorts")
        st.text_input("YouTube Tags", yt_tags, key="v91_yt_tags")
        render_copy("v91_yttg", "COPY YOUTUBE TAGS", yt_tags)

        yt_pin = f"💭 {q_ref}"
        st.text_input("YouTube Pinned Comment", yt_pin, key="v91_yt_pin")
        render_copy("v91_ytpn", "COPY PINNED COMMENT", yt_pin)

        meta_cap = f"{pkg.get('caption_hook','')}\n\n{pkg.get('caption_lesson','')}\n\n💭 {q_ref}\n\n• Follow {get_persistent_meta_handle()}\n\n{pkg.get('meta_hashtags','')}"
        st.text_area("Meta Caption (@EchoesOfWisdomOfficial)", meta_cap, height=130, key="v91_fb_cap")
        render_copy("v91_fbc", "COPY META CAPTION", meta_cap)

        meta_first = (
            f"🏛️ Want a structured daily system to build composure and clarity?\n\n"
            f"Explore The 30-Day Stoic Emotional Mastery Guide here:\n"
            f"{get_persistent_guide_url()}\n"
            f"(Use code FIRST50 at checkout)"
        )
        st.text_area("Meta First Comment", meta_first, height=95, key="v91_fb_first")
        render_copy("v91_fbf", "COPY META FIRST COMMENT", meta_first)

        if st.button("✅ Lock Day & Advance", type="primary", key="v91_lock_btn"):
            p_data = st.session_state["active_video_pkg"]
            db["scheduled_videos"].append({"date": target_d, "slot": target_s, "time": target_t, "theme_id": p_data.get("t_id"), "title": yt_title})
            if p_data.get("t_id") and p_data["t_id"] not in db.get("used_theme_ids", []):
                db.setdefault("used_theme_ids", []).append(p_data["t_id"])
            db["last_scheduled_date"], db["last_scheduled_slot"] = target_d, target_s
            save_db(db)
            st.session_state["status_banner"] = f"✓ Locked {p_data.get('t_id')}!"
            st.rerun()

with tab3:
    st.markdown(f"### Scheduled Days ({len(db.get('used_theme_ids', []))}/30 Used)")
    for item in reversed(db.get("scheduled_videos", [])):
        st.write(f"- **{item.get('date')}** ({item.get('theme_id')}): {item.get('title')}")
