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

# 1. PAGE SETUP & STUDIO UI
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

# 2. FILE PATHWAYS & PERSISTENT STORAGE
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
MUSIC_DIR = os.path.join(BASE_DIR, "music")
SAVED_CLIPS_DIR = os.path.join(DATA_DIR, "saved_clips")

for d in [DATA_DIR, TMP_DIR, FONTS_DIR, MUSIC_DIR, SAVED_CLIPS_DIR]: 
    os.makedirs(d, exist_ok=True)

DRAFT_JSON_PATH = os.path.join(DATA_DIR, "active_draft.json")
DRAFT_AUDIO_PATH = os.path.join(DATA_DIR, "active_audio.mp3")
DRAFT_VAULT_PATH = os.path.join(DATA_DIR, "draft_vault.json")
SAVED_THUMB_PATH = os.path.join(DATA_DIR, "saved_raw_thumb.png")
API_KEY_FILE = os.path.join(DATA_DIR, "gemini_key.txt")
GSHEET_URL_FILE = os.path.join(DATA_DIR, "gsheet_webhook.txt")
CHANNEL_HANDLE_FILE = os.path.join(DATA_DIR, "channel_handle.txt")
META_HANDLE_FILE = os.path.join(DATA_DIR, "meta_handle.txt")
GUIDE_URL_FILE = os.path.join(DATA_DIR, "guide_url.txt")
EXCEL_TRACKER_PATH = os.path.join(DATA_DIR, "Echoes_Of_Wisdom_Content_Tracker.xlsx")

@st.cache_resource(show_spinner=False)
def ensure_studio_fonts():
    font_urls = {
        "DejaVuSans-Bold.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf",
        "DejaVuSerif-Bold.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSerif-Bold.ttf",
        "DejaVuSerif-Italic.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSerif-Italic.ttf",
        "DejaVuSansMono-Bold.ttf": "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSansMono-Bold.ttf",
    }
    for fname, url in font_urls.items():
        fpath = os.path.join(FONTS_DIR, fname)
        if not os.path.exists(fpath) or os.path.getsize(fpath) < 10000:
            try:
                r = requests.get(url, timeout=8)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(fpath, "wb") as f:
                        f.write(r.content)
            except Exception:
                pass
    return os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")

ensure_studio_fonts()

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

# DRAFT VAULT ENGINE
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

# 3. 8 DISTINCT FONTS/COLORS, 10 CAMERA/COLOR GRADES, 12 BACKGROUNDS & LEADER WISDOM
SUBTITLE_ARCHETYPES = {
    "IMPERIAL_GOLD":   {"label": "👑 Imperial Gold (Sans Block)",       "ass_primary": "&H0000E5FF", "ass_outline": "&H00000000", "ass_font": "DejaVu Sans",      "ass_size": 74, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0xFFE500", "thumb_font": "thick distressed sans-serif block lettering in radiant imperial gold", "prefix": "gold_"},
    "GLACIAL_ICE":     {"label": "❄️ Glacial Ice (Clean Geometric)",    "ass_primary": "&H00FFF500", "ass_outline": "&H00120A04", "ass_font": "DejaVu Sans",      "ass_size": 72, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0x00F5FF", "thumb_font": "crisp geometric industrial block lettering in frost glacial cyan", "prefix": "ice_"},
    "FORGE_AMBER":     {"label": "🔥 Forge Amber (Heavy Slab)",         "ass_primary": "&H000099FF", "ass_outline": "&H00050510", "ass_font": "DejaVu Sans",      "ass_size": 76, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0xFF9900", "thumb_font": "heavy chiseled slab-serif lettering in molten forge amber", "prefix": "amber_"},
    "CRIMSON_IVORY":   {"label": "🩸 Crimson & Ivory (Editorial Serif)","ass_primary": "&H003838FF", "ass_outline": "&H00F8FAFC", "ass_font": "DejaVu Serif",     "ass_size": 72, "ass_italic": 0, "case_mode": "TITLE", "banner_hex": "0xFF5555", "thumb_font": "bold editorial serif condensed display lettering in deep crimson and warm ivory", "prefix": "crimson_"},
    "EMERALD_BONE":    {"label": "🌿 Emerald & Bone (Modern Stencil)",  "ass_primary": "&H0086EFAC", "ass_outline": "&H0006120B", "ass_font": "DejaVu Sans",      "ass_size": 74, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0x4ADE80", "thumb_font": "tall condensed stencil display lettering in luminous emerald and bone white", "prefix": "emerald_"},
    "ROYAL_VIOLET":    {"label": "🔮 Violet & Gold (Classic Serif)",    "ass_primary": "&H00F5D0FE", "ass_outline": "&H002E0845", "ass_font": "DejaVu Serif",     "ass_size": 72, "ass_italic": 0, "case_mode": "TITLE", "banner_hex": "0xE879F9", "thumb_font": "high-contrast classic serif lettering in electric orchid violet and gold", "prefix": "violet_"},
    "SILVER_MONO":     {"label": "⌨️ Silver & Charcoal (Typewriter)",   "ass_primary": "&H00F8FAFC", "ass_outline": "&H00111318", "ass_font": "DejaVu Sans Mono", "ass_size": 68, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0xE2E8F0", "thumb_font": "stark typewriter monospace stencil lettering in crisp silver-white", "prefix": "silver_"},
    "LITERARY_ITALIC": {"label": "📜 Warm Parchment (Literary Italic)", "ass_primary": "&H0077CCFF", "ass_outline": "&H001A0F08", "ass_font": "DejaVu Serif",     "ass_size": 72, "ass_italic": -1,"case_mode": "TITLE", "banner_hex": "0xFBBF24", "thumb_font": "refined literary italic serif lettering in warm champagne gold", "prefix": "parchment_"}
}

CINEMATOGRAPHY_MATRIX = {
    "PUNCH_FLASH":      {"label": "⚡ Dynamic Kinetic Arc & Probe",         "ffmpeg_eq": "eq=contrast=1.12:brightness=0.01:saturation=1.08", "grade": "High-contrast chiaroscuro, volumetric dust motes, 35mm film grain"},
    "PULL_VIGN":        {"label": "🌊 Atmospheric Parallax & Macro Whip",   "ffmpeg_eq": "eq=contrast=1.16:brightness=-0.02:saturation=0.78","grade": "Moody slate-grey palette, deep shadows, muted earth tones"},
    "WARM_DRIFT":       {"label": "🔥 Forge Ember & Optical Rack Focus",    "ffmpeg_eq": "eq=contrast=1.10:brightness=0.02:saturation=1.24", "grade": "Warm tungsten highlights, soft ambient haze, 35mm analog warmth"},
    "NORDIC_CUT":       {"label": "❄️ Nordic Citadel & Fast Shutter Tilt",  "ffmpeg_eq": "eq=contrast=1.20:brightness=0.0:saturation=0.65",  "grade": "Cold overcast daylight, desaturated steel-blue grading, crisp edges"},
    "OVERHEAD_NOIR":    {"label": "🌑 High-Angle Bird's Eye Noir",          "ffmpeg_eq": "eq=contrast=1.24:brightness=-0.03:saturation=0.85","grade": "High-angle top-down noir shadows and dramatic rim lighting"},
    "GOLDEN_HOUR_ARC":  {"label": "🌅 Low-Horizon Golden Ray Sweep",        "ffmpeg_eq": "eq=contrast=1.08:brightness=0.02:saturation=1.20", "grade": "Warm low-angle golden hour sunbeams and soft depth"},
    "MONOCHROME_GRIT":  {"label": "🖤 Stark Monochrome Documentary",        "ffmpeg_eq": "eq=contrast=1.22:brightness=0.0:saturation=0.0",   "grade": "Stark black-and-white documentary realism and crisp grain"},
    "MODERN_LIFE_REAL": {"label": "🏙️ Modern Everyday Window Realism",      "ffmpeg_eq": "eq=contrast=1.08:brightness=0.01:saturation=1.05", "grade": "Naturalistic modern interior and street daylight, authentic emotion"},
    "TEAL_ORANGE_CINE": {"label": "🎬 Teal & Warm Amber Cinema Grade",      "ffmpeg_eq": "eq=contrast=1.15:brightness=0.0:saturation=1.18,colorbalance=bs=0.08:gs=0.02:rs=-0.05:rh=0.08:gh=0.02:bh=-0.06", "grade": "Cinematic teal shadows with warm amber highlights, anamorphic depth"},
    "EMERALD_DUSK":     {"label": "🌲 Deep Forest Emerald & Silver Dusk",   "ffmpeg_eq": "eq=contrast=1.14:brightness=-0.01:saturation=0.92,colorbalance=gs=0.06:bs=0.04:gm=0.03", "grade": "Moody deep emerald-slate twilight atmosphere with crisp rim highlights"}
}

DIRECTOR_STYLES = {k: v["label"] for k, v in CINEMATOGRAPHY_MATRIX.items()}

PLAYLIST_OPTIONS = [
    "The art of moving in silence (stoic mindset)",
    "Mastering human nature and fake friends ancient parables",
    "Financial Sovereignty and Relentless Discipline",
    "Father to Son: Ancient Legacy Lessons",
    "Aging Well: Habits for Mind and Body"
]

LEADER_WISDOM_POOL = [
    {"leader": "Abraham Lincoln",   "thought": "Preparation beats last-minute panic—sharpen your axe before you swing."},
    {"leader": "Marcus Aurelius",   "thought": "You have power over your mind, not outside events; realize this and find strength."},
    {"leader": "Winston Churchill", "thought": "Success is moving from failure to failure without losing your resolve."},
    {"leader": "Nelson Mandela",    "thought": "Holding onto resentment is like drinking poison and hoping your enemy suffers."},
    {"leader": "Theodore Roosevelt","thought": "Credit belongs to the person actually in the arena, not the critic watching from the stands."},
    {"leader": "Benjamin Franklin", "thought": "Beware of little expenses; a small leak will sink a great ship."},
    {"leader": "Albert Einstein",   "thought": "Strive not to be a success, but rather to be of value."},
    {"leader": "Bruce Lee",         "thought": "Be water—adapt to the obstacle without breaking your core."},
    {"leader": "Seneca",            "thought": "We suffer more often in imagination than in reality."},
    {"leader": "Epictetus",         "thought": "It is not what happens to you, but how you react to it that matters."},
    {"leader": "Viktor Frankl",     "thought": "Between stimulus and response there is a space, and in that space lies your freedom."},
    {"leader": "Charlie Munger",    "thought": "It is remarkable how much long-term advantage people get by simply trying not to be stupid."},
    {"leader": "Miyamoto Musashi",  "thought": "Do nothing that is of no use; master the rhythm of patience and timing."},
    {"leader": "Lao Tzu",           "thought": "Those who know do not boast; those who boast do not know."},
    {"leader": "Socrates",          "thought": "When the debate is lost, slander becomes the tool of the loser."}
]

HOOK_FRAMEWORKS = [
    "LIVED CONFESSION (e.g. 'At thirty, I chased applause...')",
    "LEADER QUOTE BREAKDOWN (e.g. 'Lincoln said if I had six hours to chop a tree...')",
    "CONTRARIAN REALITY CHECK (e.g. 'Being liked by everyone is an expensive habit...')",
    "BEHAVIORAL OBSERVATION (e.g. 'Watch what a person does when nobody keeps score...')",
    "PROVOKING QUESTION (e.g. 'Why do we trade twenty years of health for temporary comfort?')",
    "QUIET PARABLE (e.g. 'Two arrows strike a man, yet only one is fired by fate...')"
]

# 30 distinct daily entries (Days 1-30) — diverse formats, leaders, styles, fonts, colors & backgrounds
_DAY_SPECS = [
    (1, "CONFESSIONAL_WINDOW", "Benjamin Franklin", "Financial Sovereignty and Relentless Discipline", "MODERN_LIFE_REAL", "EMERALD_BONE", "QUIET RESERVE", "THE SILENT BILL PAYER", "What money habit gave you the most peace of mind as you got older?"),
    (2, "TWO_ARROWS_PARABLE", "Epictetus", "The art of moving in silence (stoic mindset)", "PUNCH_FLASH", "IMPERIAL_GOLD", "FIRST VS SECOND", "STOP REPLAYING THE HIT", "How do you stop replaying an unfair remark or setback in your head?"),
    (3, "LINCOLN_AXE_PREP", "Abraham Lincoln", "Financial Sovereignty and Relentless Discipline", "TEAL_ORANGE_CINE", "SILVER_MONO", "SHARPEN FIRST", "SHARPEN BEFORE YOU SWING", "Where has extra preparation saved you from unnecessary stress?"),
    (4, "MONOCHROME_WALK_AWAY", "Lao Tzu", "Mastering human nature and fake friends ancient parables", "MONOCHROME_GRIT", "GLACIAL_ICE", "NO ARGUMENT", "WALKING AWAY CLEANLY", "When did walking away without an argument protect your self-respect?"),
    (5, "ARENA_VS_CRITIC", "Theodore Roosevelt", "The art of moving in silence (stoic mindset)", "OVERHEAD_NOIR", "FORGE_AMBER", "IN THE ARENA", "IGNORE CHEAP CRITICS", "How do you tune out critics who haven't walked in your shoes?"),
    (6, "NORDIC_COLD_DISCIPLINE", "Socrates", "Aging Well: Habits for Mind and Body", "NORDIC_CUT", "GLACIAL_ICE", "BODY AFTER 40", "YOUR FUTURE BODY IS WATCHING", "Which physical habit has helped your energy most after age thirty-five?"),
    (7, "MANDELA_RESENTMENT", "Nelson Mandela", "Aging Well: Habits for Mind and Body", "EMERALD_DUSK", "CRIMSON_IVORY", "LET IT GO", "DROP THE POISON CUP", "What old grudge or frustration did you finally let go of for your own peace?"),
    (8, "FRANKL_PAUSE_SPACE", "Viktor Frankl", "The art of moving in silence (stoic mindset)", "PULL_VIGN", "IMPERIAL_GOLD", "THE SPACE BETWEEN", "OWN YOUR RESPONSE", "What helps you pause before reacting when pressure hits suddenly?"),
    (9, "MODERN_DESK_REALISM", "Albert Einstein", "Financial Sovereignty and Relentless Discipline", "MODERN_LIFE_REAL", "EMERALD_BONE", "VALUE OVER HYPE", "BUILD REAL VALUE", "What skill or habit made you more valuable in your work or family?"),
    (10, "MENTOR_SON_DIALOGUE", "Marcus Aurelius", "Father to Son: Ancient Legacy Lessons", "WARM_DRIFT", "ROYAL_VIOLET", "HONEST WORD", "KEEP YOUR WORD SMALL", "What lesson about keeping promises do you pass on to younger people?"),
    (11, "CHURCHILL_ENDURANCE", "Winston Churchill", "The art of moving in silence (stoic mindset)", "TEAL_ORANGE_CINE", "FORGE_AMBER", "KEEP GOING", "WALK THROUGH THE STORM", "What kept you moving forward during the toughest season of your life?"),
    (12, "GOSSIP_ROOM_RULE", "Socrates", "Mastering human nature and fake friends ancient parables", "OVERHEAD_NOIR", "SILVER_MONO", "GUARD PRIVACY", "WHO TALKS BEHIND DOORS", "How do you handle people who bring drama or gossip into your space?"),
    (13, "MUNGER_AVOID_FOLLY", "Charlie Munger", "Financial Sovereignty and Relentless Discipline", "PUNCH_FLASH", "LITERARY_ITALIC", "AVOID FOLLY", "CUT AVOIDABLE MISTAKES", "What is one mistake you avoided that paid off years later?"),
    (14, "BRUCE_LEE_ADAPT", "Bruce Lee", "The art of moving in silence (stoic mindset)", "GOLDEN_HOUR_ARC", "IMPERIAL_GOLD", "STAY FLEXIBLE", "BEND WITHOUT BREAKING", "When did adapting your plan work better than forcing your original approach?"),
    (15, "SENECA_TIME_LEDGER", "Seneca", "Aging Well: Habits for Mind and Body", "MONOCHROME_GRIT", "ROYAL_VIOLET", "OWN YOUR HOURS", "GUARD YOUR HOURS FIERCELY", "What is one time-waster you stopped allowing into your week?"),
    (16, "REBUILD_QUIETLY", "Lao Tzu", "Financial Sovereignty and Relentless Discipline", "MODERN_LIFE_REAL", "EMERALD_BONE", "SILENT COMEBACK", "BUILD BEFORE YOU ANNOUNCE", "Why do you think keeping plans private works better than announcing them?"),
    (17, "FIVE_MOMENTS_SILENCE", "Confucius", "The art of moving in silence (stoic mindset)", "NORDIC_CUT", "GLACIAL_ICE", "FIVE PAUSES", "FIVE TIMES TO PAUSE FIRST", "Which moment in your day makes a three-second pause most helpful?"),
    (18, "FATHER_CRAFT_LEGACY", "Miyamoto Musashi", "Father to Son: Ancient Legacy Lessons", "GOLDEN_HOUR_ARC", "IMPERIAL_GOLD", "LASTING SKILL", "WHAT STAYS WHEN TITLES FADE", "What skill or value has stayed useful to you across every stage of life?"),
    (19, "COMPOSURE_UNDER_JABS", "Socrates", "Mastering human nature and fake friends ancient parables", "MONOCHROME_GRIT", "CRIMSON_IVORY", "STEADY NERVE", "DO NOT WRESTLE IN THE MUD", "How do you stay composed when someone uses sarcasm to provoke you?"),
    (20, "COMPOUNDING_HABITS", "Benjamin Franklin", "Financial Sovereignty and Relentless Discipline", "OVERHEAD_NOIR", "FORGE_AMBER", "DAILY COMPOUND", "SMALL STEPS BEAT BIG PLANS", "What small daily habit has been easiest for you to keep consistent?"),
    (21, "VITALITY_PACE", "Marcus Aurelius", "Aging Well: Habits for Mind and Body", "EMERALD_DUSK", "EMERALD_BONE", "STEADY PACE", "SUSTAINABLE ENERGY WINS", "How do you avoid burning out during busy weeks?"),
    (22, "SELF_RESPECT_BOUNDARY", "Epictetus", "The art of moving in silence (stoic mindset)", "WARM_DRIFT", "IMPERIAL_GOLD", "CLEAR LIMITS", "RESPECT STARTS WITH BOUNDARIES", "What boundary helped you feel more respected in your relationships?"),
    (23, "TRUE_FRIENDSHIP_TEST", "George Washington", "Mastering human nature and fake friends ancient parables", "PULL_VIGN", "GLACIAL_ICE", "REAL CIRCLE", "KEEP YOUR CIRCLE GENUINE", "What quality do you value most in a lifelong friend?"),
    (24, "MONEY_TRUTH_NO_HYPE", "Seneca", "Financial Sovereignty and Relentless Discipline", "NORDIC_CUT", "SILVER_MONO", "REAL WEALTH", "SKIP THE FAKE FLEX", "What is one status symbol or expense you realized wasn't worth it?"),
    (25, "DAUGHTER_SON_WISDOM", "Albert Schweitzer", "Father to Son: Ancient Legacy Lessons", "MODERN_LIFE_REAL", "ROYAL_VIOLET", "LASTING EXAMPLE", "THEY WATCH WHAT YOU DO", "What is one habit you hope the next generation picks up from you?"),
    (26, "AGE_WITH_CLARITY", "Marcus Aurelius", "Aging Well: Habits for Mind and Body", "GOLDEN_HOUR_ARC", "LITERARY_ITALIC", "CALM MATURITY", "MATURITY BRINGS CLARITY", "What feels much clearer to you now than it did ten years ago?"),
    (27, "OVERTHINKING_TRAP", "Seneca", "The art of moving in silence (stoic mindset)", "OVERHEAD_NOIR", "CRIMSON_IVORY", "CLEAR THE MIND", "OVERTHINKING STEALS TODAY", "How do you break out of overthinking when your mind starts racing?"),
    (28, "PATIENCE_IN_SEASON", "Lao Tzu", "Mastering human nature and fake friends ancient parables", "WARM_DRIFT", "IMPERIAL_GOLD", "SEASON OF GROWTH", "EVERY SEASON HAS ITS PACE", "When did patience help you get a better result than rushing?"),
    (29, "INTEGRITY_IN_SMALLS", "Abraham Lincoln", "Father to Son: Ancient Legacy Lessons", "NORDIC_CUT", "GLACIAL_ICE", "QUIET INTEGRITY", "INTEGRITY IN SMALL DETAILS", "Why do small everyday choices matter so much for trust?"),
    (30, "STEADY_FORWARD_MOVEMENT", "Theodore Roosevelt", "Aging Well: Habits for Mind and Body", "TEAL_ORANGE_CINE", "FORGE_AMBER", "KEEP MOVING", "KEEP MOVING FORWARD STEADILY", "What is one step you want to take this week to keep moving forward?")
]

THIRTY_DAY_CURRICULUM = [
    {
        "day": d, "fmt": fmt, "leader": ldr, "pl": pl, "style": st_k, "arch": ar_k,
        "badge": bdg, "hook_title": hk,
        "script": f"Day {d} reflection with {ldr}: steady habits beat loud claims when pressure arrives. Stay composed, protect your focus, and let quiet action speak for itself. {q}",
        "q": q,
        "s1": f"35mm wide-to-medium shot establishing {hk.lower()} in {fmt.lower().replace('_', ' ')}",
        "s2": f"85mm detail shot capturing {ldr} theme of {bdg.lower()} with crisp lighting",
        "s3": f"35mm smooth tracking shot reinforcing {bdg.lower()} in motion",
        "s4": "85mm portrait close-up with steady calm gaze and natural depth"
    }
    for (d, fmt, ldr, pl, st_k, ar_k, bdg, hk, q) in _DAY_SPECS
]
DIVERSE_ARCHETYPES = [
    "A thoughtful man in his late thirties wearing a dark olive knit sweater standing by a tall modern window looking out over a sunlit city, natural candid expression. Strictly two arms only, flawless human anatomy.",
    "An elder master mentor with silver-streaked beard and calm authoritative eyes seated across a low stone table from a young apprentice in a sunlit courtyard. Strictly two arms per person, flawless human anatomy.",
    "A disciplined craftsman in his fifties wearing a rugged canvas jacket inspecting precision tools in a warm sunlit workshop. Strictly two arms only, flawless human anatomy.",
    "A weathered seasoned traveler in his fifties walking along a misty alpine granite ridge at sunrise with steady posture. Strictly two arms only, flawless human anatomy.",
    "A composed mature man in a tailored dark coat walking calmly down a rain-slicked city street at dusk, sharp contrast and steady gaze. Strictly two arms only, flawless human anatomy.",
    "An authentic mature Roman centurion with a stern weathered face, short military crop, subtle facial scar, wearing polished dark iron shoulder plates over a crimson tunic. Strictly two arms only, flawless human anatomy.",
    "A quiet scholar in a warm wood-paneled library with brass desk lamp and leather-bound books, calm thoughtful expression. Strictly two arms only, flawless human anatomy.",
    "A seasoned coastal lighthouse keeper in a heavy wool sweater looking out over calm ocean waves at dawn. Strictly two arms only, flawless human anatomy."
]

SETTINGS_MATRIX = [
    {"n": "Modern Sunlit Apartment & City View",    "d": "Inside a calm modern living space or apartment window with natural daylight and soft depth."},
    {"n": "Quiet Rain-Slicked City Street at Dusk", "d": "Along a quiet evening street with warm streetlamp reflections on wet cobblestones."},
    {"n": "Wood-Paneled Study & Brass Lamp",        "d": "Inside a peaceful library study with warm desk lamp light, books, and deep shadows."},
    {"n": "Misty Coastal Lighthouse Cliffs",        "d": "Atop high coastal cliffs beside an old stone lighthouse overlooking ocean waves."},
    {"n": "Sunlit Bamboo & Forest Trail",           "d": "Along a tranquil forest path with morning sunbeams filtering through tall trees."},
    {"n": "Calm Wooden Lake Pier at Dawn",          "d": "On a quiet timber pier extending over still mirror-like lake water at sunrise."},
    {"n": "Minimalist Architectural Courtyard",     "d": "Inside a serene concrete and stone courtyard with sharp geometric shadows and natural light."},
    {"n": "The Secluded Craftsman Workshop",        "d": "Inside a sunlit timber and stone workshop with hand tools and warm dust motes."},
    {"n": "The Sunlit Alpine Granite Ridge",        "d": "Along a high rocky granite ridge in crisp daylight and drifting mountain mist."},
    {"n": "Quiet Train Window Overlooking Hills",   "d": "Inside a classic passenger train compartment looking out over misty rolling hills at dawn."}
]

# 4. CADENCE & PERSISTENT DATA (05:00 & 18:00 IST OPTIMAL)
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

USED_SCRIPTS_PATH = os.path.join(DATA_DIR, "used_scripts_history.json")

def normalize_script_key(txt):
    return re.sub(r"[^a-z0-9]+", " ", str(txt or "").lower()).strip()

def load_used_scripts_history():
    if os.path.exists(USED_SCRIPTS_PATH):
        try:
            with open(USED_SCRIPTS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []

def save_used_scripts_history(items):
    try:
        with open(USED_SCRIPTS_PATH, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2)
    except Exception:
        pass

def is_script_already_used(script_text, hook_text=""):
    norm_s = normalize_script_key(script_text)
    norm_h = normalize_script_key(hook_text)
    if not norm_s:
        return False
    hist = load_used_scripts_history()
    for entry in hist:
        if entry.get("norm_script") == norm_s:
            return True
        if len(norm_s) > 70 and entry.get("norm_script", "")[:90] == norm_s[:90]:
            return True
    if norm_h and norm_h in [normalize_script_key(x) for x in db.get("used_hooks", [])]:
        return True
    return False

def record_generated_script(script_text, hook_text="", theme_id=""):
    norm_s = normalize_script_key(script_text)
    if not norm_s:
        return
    hist = load_used_scripts_history()
    if not any(x.get("norm_script") == norm_s for x in hist):
        hist.append({
            "norm_script": norm_s,
            "script": str(script_text or "").strip(),
            "hook": str(hook_text or "").strip(),
            "theme_id": str(theme_id or "").strip(),
            "created_at": datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%Y-%m-%d %H:%M:%S")
        })
        save_used_scripts_history(hist)
    if hook_text and hook_text.strip().upper() not in db.get("used_hooks", []):
        db.setdefault("used_hooks", []).append(hook_text.strip().upper())
        save_db(db)

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

# 5. BUILT-IN EXCEL TRACKER ENGINE
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

# 6. NATURAL HUMAN AUDIO & SUBTITLE ENGINE
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
    ass_italic = arch_cfg.get("ass_italic", 0)
    case_mode = arch_cfg.get("case_mode", "UPPER")
    events = []

    def format_case(s):
        return s.upper() if case_mode == "UPPER" else s

    if timed_words and len(timed_words) >= 5:
        clean_words = []
        for tw in timed_words:
            raw_w = tw['word'].replace("—", " ").replace("–", " ").replace("-", " ").replace("...", " ")
            w_txt = re.sub(r"[^\w\s',.!?]", "", raw_w).strip()
            if w_txt:
                for sub_w in w_txt.split():
                    clean_words.append({'word': format_case(sub_w), 'start': tw['start'], 'end': tw['end']})
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
            txt = format_case(re.sub(r"[^\w\s',.!?]", "", " ".join(grp)).strip())
            if txt: events.append((st_t, en_t, txt))

    def fmt(s): return f"{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}"
    ass_doc = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{ass_font},{ass_size},{color},&H000000FF,{ass_outline},&H80000000,-1,{ass_italic},0,0,100,100,0,0,1,6,3,2,50,50,420,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
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

# 7. NON-REPETITIVE 30-DAY PACKAGE BUILDER & AI GENERATOR
def build_package_from_day_entry(entry, custom_char=None, custom_setting=None):
    style_key = entry["style"]
    style_meta = CINEMATOGRAPHY_MATRIX.get(style_key, CINEMATOGRAPHY_MATRIX["MODERN_LIFE_REAL"])
    arch_cfg = SUBTITLE_ARCHETYPES.get(entry["arch"], SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])
    char_desc = custom_char or random.choice(DIVERSE_ARCHETYPES)
    sett_desc = custom_setting or random.choice(SETTINGS_MATRIX)["d"]
    hook_caps = entry["hook_title"].upper()
    leader_name = entry.get("leader", "Timeless Wisdom")

    return {
        "title_concept": f"Day {entry['day']}: {entry['hook_title'].title()} ({leader_name} • {entry['fmt']})",
        "playlist": entry["pl"],
        "hook_banner": hook_caps,
        "video_overlay_text": entry["badge"],
        "subtitle_archetype": entry["arch"],
        "director_style": style_key,
        "script": entry["script"],
        "scene1_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s1']}. Background: {sett_desc}. {style_meta['grade']}. Flawless anatomy, strictly two arms.",
        "scene2_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s2']}. {style_meta['grade']}. Crisp focus and natural motion.",
        "scene3_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s3']}. Same protagonist ({char_desc[:75]}). {style_meta['grade']}. Strictly two arms.",
        "scene4_prompt": f"[4-second vertical 9:16 cinematic video clip] {entry['s4']}. Same protagonist across all scenes. {style_meta['grade']}.",
        "thumbnail_prompt": (
            f"9:16 vertical cinematic frame featuring {char_desc} in {sett_desc}. "
            f"Upper-third bold typography reading: \"{hook_caps}\" rendered in {arch_cfg['thumb_font']} with a crisp drop shadow, clear of face, no bottom text."
        ),
        "youtube_title": f"⚡ {entry['hook_title'].title()} ({leader_name}) #shorts #mindset",
        "youtube_description": f"{entry['script']}\n\n💭 {entry['q']}\n\nSubscribe to {get_persistent_yt_handle()} for daily life lessons.\n\n#mindset #lifelessons #selfgrowth #shorts",
        "youtube_tags": f"life lessons, personal growth, mindset, {leader_name.lower()}, emotional control, discipline, daily reflection, shorts",
        "youtube_pinned_comment": f"💭 {entry['q']}",
        "caption_hook": entry["hook_title"].title(),
        "caption_lesson": entry["script"],
        "reflection_question": entry["q"],
        "meta_hashtags": "#Mindset #LifeLessons #PersonalGrowth #SelfRespect #Discipline #Wisdom"
    }

def build_unique_fallback_script(day_entry, leader_pick, hook_style_pick, setting_desc):
    variants = [
        f"Most people chase loud approval until pressure exposes what actually holds. {leader_pick['leader']} reminded us that {leader_pick['thought'].lower().rstrip('.')} When you stop reacting to every passing noise, your judgment stays sharp and your peace stays yours. {day_entry['q']}",
        f"You can spot real character the moment plans get inconvenient. {leader_pick['leader']} left a clear standard: {leader_pick['thought'].lower().rstrip('.')} Quiet discipline in ordinary weeks builds the confidence you rely on when stakes rise. {day_entry['q']}",
        f"A calm mind beats a crowded schedule every single time. Drawing from {leader_pick['leader']}, {leader_pick['thought'].lower().rstrip('.')} Step back before answering, protect your time, and let steady action do the talking. {day_entry['q']}",
        f"Real strength rarely looks dramatic in the moment it is built. {leader_pick['leader']} pointed out that {leader_pick['thought'].lower().rstrip('.')} Keep your standards steady in quiet rooms so you never have to defend them loudly later. {day_entry['q']}",
        f"What you practice on ordinary days decides how you stand on hard ones. {leader_pick['leader']} understood that {leader_pick['thought'].lower().rstrip('.')} Cut what drains your focus, keep your word clean, and move forward deliberately. {day_entry['q']}"
    ]
    random.shuffle(variants)
    for v in variants:
        cleaned = normalize_spoken_text(v)
        if not is_script_already_used(cleaned):
            return cleaned
    stamp = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%H%M%S")
    return normalize_spoken_text(f"Day {day_entry['day']} note #{stamp}: {leader_pick['leader']} taught that {leader_pick['thought'].lower().rstrip('.')} Stay composed, guard your attention, and act with quiet consistency today. {day_entry['q']}")

def generate_varied_package(raw_api_key, day_entry, custom_char=None, custom_setting=None):
    clean_key = raw_api_key.strip().strip('"').strip("'") if raw_api_key else ""
    chosen_sett = custom_setting or random.choice(SETTINGS_MATRIX)["d"]
    chosen_char = custom_char or random.choice(DIVERSE_ARCHETYPES)
    leader_pick = random.choice(LEADER_WISDOM_POOL)
    hook_style_pick = random.choice(HOOK_FRAMEWORKS)

    base_pkg = build_package_from_day_entry(day_entry, chosen_char, chosen_sett)
    if is_script_already_used(base_pkg.get("script", ""), base_pkg.get("hook_banner", "")):
        unique_hook = f"{leader_pick['leader'].upper()} • {day_entry['badge']}"
        base_pkg["hook_banner"] = unique_hook
        base_pkg["youtube_title"] = f"⚡ {leader_pick['leader']} — {day_entry['badge'].title()} #shorts #mindset"
        base_pkg["script"] = build_unique_fallback_script(day_entry, leader_pick, hook_style_pick, chosen_sett)
        base_pkg["caption_lesson"] = base_pkg["script"]

    hist_entries = load_used_scripts_history()
    used_h_list = list(dict.fromkeys([str(x).strip() for x in db.get("used_hooks", []) if x] + [h.get("hook", "") for h in hist_entries if h.get("hook")]))
    used_h = "\n".join([f"- {h}" for h in used_h_list[-60:]]) or "None."
    used_s_excerpts = "\n".join([f"- {h.get('script','')[:140]}" for h in hist_entries[-35:] if h.get("script")]) or "None."

    if not clean_key:
        record_generated_script(base_pkg["script"], base_pkg.get("hook_banner", ""), f"DAY_{day_entry['day']:02d}")
        return base_pkg, f"Unique History Vault (Day {day_entry['day']} • {leader_pick['leader']} • {len(hist_entries)+1} Ever)"

    style_meta = CINEMATOGRAPHY_MATRIX.get(day_entry["style"], CINEMATOGRAPHY_MATRIX["MODERN_LIFE_REAL"])
    arch_cfg = SUBTITLE_ARCHETYPES.get(day_entry["arch"], SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])

    prompt = (
        f"You are creating a 100% NEW, NEVER-BEFORE-USED 18-20 second short-form video script for men aged 35-65+ in the US, UK, Canada, and Australia.\n"
        f"FORMAT ARCHETYPE: {day_entry['fmt']} | HOOK STRUCTURE TO USE: {hook_style_pick}\n"
        f"LEADER / THINKER INSPIRATION: {leader_pick['leader']} — \"{leader_pick['thought']}\"\n"
        f"CAMERA & COLOR GRADE: {style_meta['label']} ({style_meta['grade']})\n"
        f"BACKGROUND ENVIRONMENT: {chosen_sett}\n"
        f"PROTAGONIST CONTINUITY: {chosen_char}\n"
        f"THUMBNAIL FONT STYLE & COLOR: {arch_cfg['thumb_font']}\n"
        f"FORBIDDEN HOOKS (NEVER REPEAT):\n{used_h}\n"
        f"FORBIDDEN PREVIOUS SCRIPTS (NEVER REPEAT OR PARAPHRASE CLOSELY):\n{used_s_excerpts}\n"
        f"STRICT RULES:\n"
        f"1. Write a completely fresh, natural, human-sounding spoken script of 45 to 52 words that has NEVER appeared in the forbidden scripts list above.\n"
        f"2. Use clean commas and periods (avoid em-dashes or ellipses that cause broken voice pauses).\n"
        f"3. Include a concrete real-world shift around second 4 and an open, thoughtful reflection question (zero engagement bait like 'Drop 1 or 2').\n"
        f"4. All 4 scene prompts must start with '[4-second vertical 9:16 cinematic video clip]', feature the exact same protagonist and background ({chosen_sett}), and apply {style_meta['grade']}.\n"
        f"5. Thumbnail prompt must specify {arch_cfg['thumb_font']} in the upper third, clear of face, no bottom text.\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        "{\n"
        '  "title_concept": "Short title mentioning leader/concept",\n'
        '  "hook_banner": "3-5 WORD FRESH TITLE",\n'
        '  "video_overlay_text": "2-3 WORD BADGE",\n'
        '  "script": "45-52 word fresh conversational script with natural punctuation.",\n'
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
                cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.98, max_output_tokens=1500)
                r = client.models.generate_content(model=m, contents=prompt, config=cfg)
                raw = r.text.strip()
                match = re.search(r'\{.*\}', raw, re.DOTALL)
                parsed = json.loads(match.group(0) if match else raw)
                if isinstance(parsed, dict) and "script" in parsed:
                    cand_script = str(parsed["script"]).strip()
                    cand_hook = str(parsed.get("hook_banner", base_pkg["hook_banner"])).strip()
                    if is_script_already_used(cand_script, cand_hook):
                        r2 = client.models.generate_content(
                            model=m,
                            contents=prompt + "\nCRITICAL: Your previous output matched an already-used script. Write a completely different story, angle, and wording.",
                            config=cfg
                        )
                        match2 = re.search(r'\{.*\}', r2.text.strip(), re.DOTALL)
                        parsed2 = json.loads(match2.group(0) if match2 else r2.text.strip())
                        if isinstance(parsed2, dict) and parsed2.get("script") and not is_script_already_used(parsed2.get("script"), parsed2.get("hook_banner", "")):
                            parsed = parsed2
                        else:
                            parsed["script"] = build_unique_fallback_script(day_entry, leader_pick, hook_style_pick, chosen_sett)
                    merged = dict(base_pkg)
                    for k, v in parsed.items():
                        if v: merged[k] = v
                    merged["caption_lesson"] = merged["script"]
                    record_generated_script(merged["script"], merged.get("hook_banner", ""), f"DAY_{day_entry['day']:02d}")
                    return merged, f"Gemini AI • {leader_pick['leader']} • {day_entry['fmt']}"
            except Exception:
                continue
    except Exception:
        pass

    base_pkg["script"] = build_unique_fallback_script(day_entry, leader_pick, hook_style_pick, chosen_sett)
    base_pkg["caption_lesson"] = base_pkg["script"]
    record_generated_script(base_pkg["script"], base_pkg.get("hook_banner", ""), f"DAY_{day_entry['day']:02d}")
    return base_pkg, f"Unique History Vault (Day {day_entry['day']} • {leader_pick['leader']} • {day_entry['fmt']})"

# 8. HEADER & SETTINGS
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 600;">v9.5 // 30-DAY NON-REPEATING ENGINE, LEADER WISDOM & 1-CLICK DISCARD/REGENERATE</span>
</div>
""", unsafe_allow_html=True)

recent_ids = db.get("used_theme_ids", [])[-30:]
_used_scripts_total = len(load_used_scripts_history())
st.markdown(f"""
<div style="margin-bottom: 14px;">
    <span class="badge badge-green">● {_used_scripts_total} SCRIPTS LOCKED FOREVER</span>
    <span class="badge badge-purple">🏛️ 15+ LEADER QUOTES</span>
    <span class="badge badge-blue">🎨 8 FONTS & 10 COLOR GRADES</span>
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

def run_day_generation(day_obj, arch_override="📅 Day Preset", style_override="📅 Day Preset", setting_override="🎲 Auto-Rotate Background", use_gem=False):
    k = get_persistent_api_key()
    run_entry = dict(day_obj)
    if arch_override != "📅 Day Preset":
        run_entry["arch"] = arch_override
    if style_override != "📅 Day Preset":
        run_entry["style"] = style_override
    sett_desc = None if setting_override.startswith("🎲") else next((s["d"] for s in SETTINGS_MATRIX if s["n"] == setting_override), None)

    pkg, eng_src = generate_varied_package(k, run_entry, custom_setting=sett_desc)
    timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k, use_gemini_tts=use_gem))

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

# 9. TABS
tab1, tab2, tab3 = st.tabs(["⚡ 1. 30-DAY SCRIPT & PROMPTS", "🎬 2. RENDER, CROP & METADATA", "📋 3. QUEUE LEDGER & TRACKER"])

with tab1:
    vault_items = load_draft_vault()
    if vault_items:
        with st.expander(f"📦 RESTORE PREVIOUS DRAFT ({len(vault_items)} SAVED IN VAULT)", expanded=False):
            v_labels = [f"⚡ {v.get('pkg',{}).get('hook_banner', 'Untitled')} — {v.get('t_id','Day')} ({v.get('p','')})" for v in vault_items]
            v_idx = st.selectbox("Select Saved Draft", range(len(vault_items)), format_func=lambda i: v_labels[i], key="v95_vault_sel")
            if st.button("🔄 Restore Selected Draft", key="v95_vault_restore"):
                restored = vault_items[v_idx]
                with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(restored, f, indent=2)
                st.session_state["active_video_pkg"] = restored
                st.session_state["rendered_director_style"] = restored.get("pkg", {}).get("director_style", "MODERN_LIFE_REAL")
                st.success("✓ Draft restored!")
                st.rerun()

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

    used_script_norms = {h.get("norm_script", "") for h in load_used_scripts_history()}
    if "Auto-Next" in day_mode:
        unused_days = [
            d for d in THIRTY_DAY_CURRICULUM
            if f"DAY_{d['day']:02d}" not in recent_ids and normalize_script_key(d.get("script", "")) not in used_script_norms
        ]
        if not unused_days:
            unused_days = [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" not in recent_ids]
        selected_day_obj = unused_days[0] if unused_days else THIRTY_DAY_CURRICULUM[len(recent_ids) % len(THIRTY_DAY_CURRICULUM)]
    else:
        day_num = st.selectbox("Select Day (1–30)", [d["day"] for d in THIRTY_DAY_CURRICULUM], format_func=lambda n: f"Day {n:02d} — {THIRTY_DAY_CURRICULUM[n-1]['fmt']} ({THIRTY_DAY_CURRICULUM[n-1].get('leader','')})")
        selected_day_obj = THIRTY_DAY_CURRICULUM[day_num - 1]

    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        chosen_arch_opt = st.selectbox("Font Style & Color", ["📅 Day Preset"] + list(SUBTITLE_ARCHETYPES.keys()), format_func=lambda x: "📅 Day Preset" if x == "📅 Day Preset" else SUBTITLE_ARCHETYPES[x]["label"])
    with col_c2:
        chosen_style_opt = st.selectbox("Camera & Color Grade", ["📅 Day Preset"] + list(CINEMATOGRAPHY_MATRIX.keys()), format_func=lambda x: "📅 Day Preset" if x == "📅 Day Preset" else CINEMATOGRAPHY_MATRIX[x]["label"])
    with col_c3:
        chosen_sett_opt = st.selectbox("Background Setting", ["🎲 Auto-Rotate Background"] + [s["n"] for s in SETTINGS_MATRIX])

    voice_mode = st.radio(
        "Voice Delivery Mode (Natural Human Pacing)",
        [
            "🎙️ Natural Conversational Voice (Edge-TTS Calm Pace, 0% Rush)",
            "🔊 Gemini AI Voice (Deep Stoic Male, Calm Pauses)"
        ],
        index=0
    )

    if st.button("🚀 Generate Non-Repeating Day Package & Audio", type="primary"):
        use_gem = "Gemini AI Voice" in voice_mode
        with st.status("⚡ Building fresh non-repeating format, leader insight & natural voice...", expanded=True) as status:
            run_day_generation(selected_day_obj, chosen_arch_opt, chosen_style_opt, chosen_sett_opt, use_gem)
            status.update(label="✅ Ready!", state="complete", expanded=False)
            st.rerun()

    if "active_video_pkg" in st.session_state:
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data.get("pkg", {})
        st.divider()
        st.subheader(f"📜 {pkg.get('title_concept', 'Daily Reel')}")
        st.caption(f"Engine: `{p_data.get('engine_source', '')}` | Voice: `{p_data.get('voice_used', '')}` | Font: `{SUBTITLE_ARCHETYPES.get(pkg.get('subtitle_archetype','IMPERIAL_GOLD'), {}).get('label','')}`")
        st.info(f"**Spoken Script:**\n\n*{pkg.get('script')}*\n\n**Reflection Question:** *{pkg.get('reflection_question', '')}*")

        # Action row: Discard & Generate New Script OR Discard & Start Fresh
        col_act1, col_act2 = st.columns(2)
        with col_act1:
            if st.button("🔄 Discard & Generate New Script", key="v95_discard_regen", use_container_width=True):
                cur_tid = p_data.get("t_id", "")
                cur_used_norms = {h.get("norm_script", "") for h in load_used_scripts_history()}
                alt_days = [
                    d for d in THIRTY_DAY_CURRICULUM
                    if f"DAY_{d['day']:02d}" != cur_tid
                    and f"DAY_{d['day']:02d}" not in recent_ids
                    and normalize_script_key(d.get("script", "")) not in cur_used_norms
                ]
                if not alt_days:
                    alt_days = [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" != cur_tid]
                next_random_day = random.choice(alt_days)
                with st.spinner("⚡ Discarding old script & generating a completely different format/leader/style..."):
                    run_day_generation(next_random_day, chosen_arch_opt, chosen_style_opt, chosen_sett_opt, ("Gemini AI Voice" in voice_mode))
                st.rerun()
        with col_act2:
            if st.button("🗑️ Discard Draft & Start Fresh", key="v95_discard_fresh", use_container_width=True):
                if os.path.exists(DRAFT_JSON_PATH):
                    try: os.remove(DRAFT_JSON_PATH)
                    except Exception: pass
                if os.path.exists(DRAFT_AUDIO_PATH):
                    try: os.remove(DRAFT_AUDIO_PATH)
                    except Exception: pass
                st.session_state.pop("active_video_pkg", None)
                st.session_state.pop("rendered_video_path", None)
                st.session_state["status_banner"] = "🗑️ Active draft discarded! Select or generate a new script anytime."
                st.rerun()

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

def get_persisted_clips():
    if not os.path.exists(SAVED_CLIPS_DIR):
        return []
    return sorted([os.path.join(SAVED_CLIPS_DIR, f) for f in os.listdir(SAVED_CLIPS_DIR) if f.lower().endswith((".mp4", ".mov"))])

with tab2:
    st.markdown("### 📥 1. Upload or Reuse Saved Video Clips (Credit-Safe Vault)")
    uploaded_clips = st.file_uploader("Drop 2 to 10+ clips (auto-saved to disk so you never lose credits)", type=["mp4", "mov"], accept_multiple_files=True)
    if uploaded_clips:
        for old_f in os.listdir(SAVED_CLIPS_DIR):
            try: os.remove(os.path.join(SAVED_CLIPS_DIR, old_f))
            except Exception: pass
        for idx, c in enumerate(sorted(uploaded_clips, key=lambda x: x.name)):
            dest_p = os.path.join(SAVED_CLIPS_DIR, f"clip_{idx:02d}_{c.name}")
            with open(dest_p, "wb") as f:
                f.write(c.read())

    persisted_clip_paths = get_persisted_clips()
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

    st.divider()
    st.markdown("### 🖼️ 2. Thumbnail Cropper & Download")
    cur_pkg_for_thumb = st.session_state.get("active_video_pkg", {}).get("pkg", {})
    cur_slug_thumb = re.sub(r'[^a-zA-Z0-9]+', '_', cur_pkg_for_thumb.get('hook_banner', 'reel')).strip('_').lower()
    thumb_file = st.file_uploader("Upload Raw Thumbnail Image", type=["png", "jpg", "jpeg", "webp"], key="v91_thumb_up")
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
        yt_hashtags_str = "#mindset #lifelessons #selfgrowth #discipline #wisdom #shorts"
        fb_hashtags_str = "#Mindset #LifeLessons #PersonalGrowth #SelfRespect #Discipline #Wisdom"
        yt_title = pkg.get("youtube_title", f"⚡ {raw_hook} 🎯 #shorts #mindset")
        if "#shorts" not in yt_title.lower():
            yt_title = f"{yt_title} #shorts #mindset"

        st.divider()
        st.markdown("### 📝 4. Complete Metadata, Emojis & Hashtags Suite")

        st.text_input("YouTube Title (With Emojis & Hashtags)", yt_title, key="v94_yt_title")
        render_copy("v94_ytt", "COPY YOUTUBE TITLE", yt_title)

        yt_desc = (
            f"⚡ {raw_hook} 🏛️\n\n"
            f"🎙️ {pkg.get('script','')}\n\n"
            f"💬 {q_ref}\n\n"
            f"🔔 Subscribe to {get_persistent_yt_handle()} for daily life lessons & reflection.\n\n"
            f"{yt_hashtags_str}"
        )
        st.text_area("YouTube Description (@AJ-Echoes-of-Wisdom)", yt_desc, height=145, key="v94_yt_desc")
        render_copy("v94_ytd", "COPY YOUTUBE DESCRIPTION", yt_desc)

        st.text_input("YouTube Playlist", pl_name, key="v94_yt_pl")
        render_copy("v94_ytp", "COPY YOUTUBE PLAYLIST", pl_name)

        yt_tags = pkg.get("youtube_tags", "life lessons, personal growth, mindset, emotional control, discipline, daily reflection, shorts")
        st.text_input("YouTube Tags", yt_tags, key="v94_yt_tags")
        render_copy("v94_yttg", "COPY YOUTUBE TAGS", yt_tags)

        yt_pin = f"💬 {q_ref} 👇"
        st.text_input("YouTube Pinned Comment", yt_pin, key="v94_yt_pin")
        render_copy("v94_ytpn", "COPY PINNED COMMENT", yt_pin)

        meta_cap = (
            f"⚡ {raw_hook} 🏛️\n\n"
            f"{pkg.get('caption_lesson','')}\n\n"
            f"💬 {q_ref}\n\n"
            f"🔖 Save this reminder for tough days or share it with someone who needs it.\n"
            f"✨ Follow {get_persistent_meta_handle()} for daily clarity.\n\n"
            f"{fb_hashtags_str}"
        )
        st.text_area("Meta Caption (@EchoesOfWisdomOfficial)", meta_cap, height=160, key="v94_fb_cap")
        render_copy("v94_fbc", "COPY META CAPTION", meta_cap)

        st.text_input("Meta Hashtags Only", fb_hashtags_str, key="v94_fb_tags_only")
        render_copy("v94_fbtags", "COPY META HASHTAGS", fb_hashtags_str)

        meta_first = (
            f"🏛️ Want a structured daily system to build composure and clarity? ✨\n\n"
            f"📘 Explore The 30-Day Stoic Emotional Mastery Guide here:\n"
            f"{get_persistent_guide_url()}\n"
            f"🎟️ Use code FIRST50 at checkout"
        )
        st.text_area("Meta First Comment", meta_first, height=110, key="v94_fb_first")
        render_copy("v94_fbf", "COPY META FIRST COMMENT", meta_first)

        st.markdown("""
        <div style="margin: 12px 0 14px 0;">
            <a href="https://business.facebook.com/latest/reels_composer" target="_blank" style="text-decoration: none;">
                <button style="width: 100%; height: 3.2rem; background: #1877F2; color: white; border: none; border-radius: 8px; font-weight: 700; font-family: -apple-system, sans-serif; font-size: 13px; cursor: pointer; box-shadow: 0 4px 15px rgba(24, 119, 242, 0.35);">
                    🌐 OPEN META REELS COMPOSER (9:16 NATIVE)
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)

        if st.button("✅ Lock Day & Advance", type="primary", key="v91_lock_btn"):
            p_data = st.session_state["active_video_pkg"]
            slot_c = "S1" if "SLOT 1" in target_s else "S2"
            pl_c = "SILENCE" if "silence" in pl_name.lower() else ("PARABLES" if "parables" in pl_name.lower() else ("FINANCE" if "financial" in pl_name.lower() else ("LEGACY" if "father" in pl_name.lower() else "AGING")))
            vid_file_name = f"{target_d}_{slot_c}_{pl_c}_{cur_slug_thumb}.mp4"
            thumb_file_name = f"{target_d.replace('-','')}_{cur_slug_thumb}_thumb.png"

            row_payload = {
                "targetDate": target_d,
                "slot": f"{slot_c} - {'Morning (05:00 IST)' if slot_c == 'S1' else 'Evening (18:00 IST)'}",
                "ytStatus": "Ready in Drive",
                "metaStatus": "Ready in Drive",
                "playlist": pl_name,
                "titleConcept": pkg.get("title_concept", ""),
                "hookBanner": pkg.get("hook_banner", ""),
                "driveFolder": f"EchoesOfWisdom/01_READY_TO_SCHEDULE/{target_d}_{slot_c}_{pl_c}_{cur_slug_thumb}",
                "videoLink": vid_file_name,
                "thumbLink": thumb_file_name,
                "ytTitle": yt_title,
                "ytDesc": yt_desc,
                "ytTags": yt_tags,
                "ytPinned": yt_pin,
                "metaCaption": meta_cap,
                "metaComment": meta_first,
                "directorFx": CINEMATOGRAPHY_MATRIX.get(chosen_director_fx, {}).get("label", "Modern Everyday Window Realism"),
                "notes": "Staged in EchoesOfWisdom/01_READY_TO_SCHEDULE (30-Day Non-Repeating)"
            }

            db["scheduled_videos"].append({
                "date": target_d,
                "slot": target_s,
                "time": target_t,
                "playlist": pl_name,
                "theme_id": p_data.get("t_id"),
                "title": yt_title,
                "file": vid_file_name
            })
            if p_data.get("t_id") and p_data["t_id"] not in db.get("used_theme_ids", []):
                db.setdefault("used_theme_ids", []).append(p_data["t_id"])
            if pkg.get("hook_banner") and pkg.get("hook_banner") not in db.get("used_hooks", []):
                db.setdefault("used_hooks", []).append(pkg.get("hook_banner"))
            db["last_scheduled_date"], db["last_scheduled_slot"] = target_d, target_s
            save_db(db)

            excel_ok = append_to_excel_tracker(row_payload)
            webhook_url = get_persistent_gsheet_url()
            cloud_ok = False
            if webhook_url:
                try:
                    r = requests.post(webhook_url, json=row_payload, timeout=6)
                    if r.status_code == 200:
                        cloud_ok = True
                except Exception:
                    pass

            nd, ns, nt = get_next_slot(target_d, target_s)
            extra_msg = " + Synced to Live Sheet! 📊" if cloud_ok else (" + Added to Excel Tracker 📑" if excel_ok else "")
            st.session_state["status_banner"] = f"✓ Locked {p_data.get('t_id')}{extra_msg}! Next slot: {nd} @ {nt} IST ({ns})"
            st.rerun()

with tab3:
    st.markdown("### 📊 Content Tracker & Excel Export")
    if os.path.exists(EXCEL_TRACKER_PATH):
        with open(EXCEL_TRACKER_PATH, "rb") as ef:
            st.download_button(
                "💾 Download Content Tracker (.xlsx)",
                ef.read(),
                "Echoes_Of_Wisdom_Content_Tracker.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    st.markdown(f"### 📋 Scheduled Days ({len(db.get('used_theme_ids', []))}/30 Used)")
    for item in reversed(db.get("scheduled_videos", [])):
        st.markdown(f"""
        <div style="background:#0A0F1D;border:1px solid rgba(56,189,248,0.2);border-radius:8px;padding:8px 12px;margin-bottom:6px;font-family:monospace;font-size:11px;">
            <span style="color:#38BDF8;font-weight:700;">{item.get('date')}</span> @ <span style="color:#FBBF24;">{item.get('time')} IST ({item.get('slot')})</span>
            <div style="color:#F8FAFC;font-weight:600;">{item.get('title')}</div>
            <div style="color:#64748B;">📁 {item.get('file', '')} | 📺 {item.get('playlist', '')}</div>
        </div>
        """, unsafe_allow_html=True)
