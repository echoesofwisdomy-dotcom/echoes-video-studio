import os, io, json, re, random, asyncio, subprocess, requests, base64
from datetime import datetime, timedelta, timezone, time as dt_time
from PIL import Image
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

st.set_page_config(page_title="Echoes Video Studio", page_icon="🎬", layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    header[data-testid="stHeader"] { background: transparent !important; }
    .stApp { background-color: #080B11 !important; color: #E2E8F0 !important; }
    .block-container { padding-top: 3.2rem !important; padding-bottom: 3rem !important; max-width: 720px !important; }
    div[data-testid="stExpander"] { background: #0E1626 !important; border: 1px solid rgba(56,189,248,0.25) !important; border-radius: 12px !important; }
    .stTextInput>div>div>input, .stTextArea textarea { background-color: #0A0F1D !important; border: 1px solid rgba(56,189,248,0.25) !important; color: #F8FAFC !important; border-radius: 8px !important; }
    .stButton>button[kind="primary"] { background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important; color: #FFF !important; border-radius: 10px !important; height: 3.3rem !important; font-weight: 700 !important; width: 100% !important; }
    .stButton>button:not([kind="primary"]) { background: #111B30 !important; color: #E2E8F0 !important; border: 1px solid rgba(56,189,248,0.25) !important; border-radius: 8px !important; }
    .stDownloadButton>button { background: linear-gradient(135deg, #059669 0%, #047857 100%) !important; color: #FFF !important; border-radius: 10px !important; height: 3.2rem !important; font-weight: 700 !important; width: 100% !important; }
    .badge { font-family: monospace; font-size: 11px; font-weight: 600; padding: 5px 10px; border-radius: 6px; display: inline-flex; margin: 2px; }
    .badge-green { background: rgba(16,185,129,0.12); color: #34D399; border: 1px solid rgba(52,211,153,0.25); }
    .badge-blue { background: rgba(56,189,248,0.12); color: #38BDF8; border: 1px solid rgba(56,189,248,0.25); }
    .badge-amber { background: rgba(245,158,11,0.12); color: #FBBF24; border: 1px solid rgba(251,191,36,0.25); }
    .badge-purple { background: rgba(168,85,247,0.12); color: #C084FC; border: 1px solid rgba(168,85,247,0.25); }
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TMP_DIR = os.path.join(BASE_DIR, "tmp")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")
SAVED_CLIPS_DIR = os.path.join(DATA_DIR, "saved_clips")
for d in [DATA_DIR, TMP_DIR, FONTS_DIR, SAVED_CLIPS_DIR]:
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
DB_PATH = os.path.join(DATA_DIR, "video_schedule.json")
USED_SCRIPTS_PATH = os.path.join(DATA_DIR, "used_scripts_history.json")

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

def _read_pref(state_key, secret_key, file_path, fallback=""):
    if st.session_state.get(state_key):
        return str(st.session_state[state_key]).strip().strip('"').strip("'")
    if secret_key in st.secrets:
        return str(st.secrets[secret_key]).strip().strip('"').strip("'")
    if os.getenv(secret_key):
        return str(os.getenv(secret_key)).strip()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                v = f.read().strip()
                if v:
                    return v
        except Exception:
            pass
    return fallback

def _write_pref(state_key, file_path, val):
    clean = val.strip().strip('"').strip("'")
    st.session_state[state_key] = clean
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception:
        pass

def get_persistent_api_key(): return _read_pref("api_key", "GEMINI_API_KEY", API_KEY_FILE, "")
def save_persistent_api_key(v): _write_pref("api_key", API_KEY_FILE, v)
def get_persistent_gsheet_url(): return _read_pref("user_sheet_url", "GSHEET_WEBHOOK_URL", GSHEET_URL_FILE, "")
def save_persistent_gsheet_url(v): _write_pref("user_sheet_url", GSHEET_URL_FILE, v)
def get_persistent_yt_handle(): return _read_pref("user_yt_handle", "YT_CHANNEL_HANDLE", CHANNEL_HANDLE_FILE, "@AJ-Echoes-of-Wisdom")
def save_persistent_yt_handle(v):
    c = v.strip()
    if c and not c.startswith("@"): c = "@" + c
    _write_pref("user_yt_handle", CHANNEL_HANDLE_FILE, c)
def get_persistent_meta_handle(): return _read_pref("user_meta_handle", "META_CHANNEL_HANDLE", META_HANDLE_FILE, "@EchoesOfWisdomOfficial")
def save_persistent_meta_handle(v):
    c = v.strip()
    if c and not c.startswith("@"): c = "@" + c
    _write_pref("user_meta_handle", META_HANDLE_FILE, c)
def get_persistent_guide_url(): return _read_pref("user_guide_url", "GUIDE_URL", GUIDE_URL_FILE, "https://theechoesofwisdom.gumroad.com/l/stoic-guide")

def load_db():
    d = {"scheduled_videos": [], "used_hooks": [], "used_theme_ids": [], "last_scheduled_date": None, "last_scheduled_slot": None, "slot1_time": "05:00", "slot2_time": "18:00"}
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                d.update(json.load(f))
        except Exception:
            pass
    return d

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

db = load_db()

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
    for entry in load_used_scripts_history():
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

def load_draft_vault():
    if os.path.exists(DRAFT_VAULT_PATH):
        try:
            with open(DRAFT_VAULT_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
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
    except Exception:
        pass

def get_next_slot(base_d=None, base_s=None):
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    ld_str = base_d if base_d else db.get("last_scheduled_date")
    ls = base_s if base_s else db.get("last_scheduled_slot")
    s1_t, s2_t = db.get("slot1_time", "05:00"), db.get("slot2_time", "18:00")
    if ld_str and ls:
        try: ld = datetime.strptime(str(ld_str), "%Y-%m-%d").date()
        except Exception: ld = now_ist.date()
        return (ld.strftime("%Y-%m-%d"), "SLOT 2 (EVENING)", s2_t) if "SLOT 1" in str(ls).upper() else ((ld + timedelta(days=1)).strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t)
    td = now_ist.date()
    t1 = dt_time(int(s1_t.split(":")[0]), int(s1_t.split(":")[1]))
    t2 = dt_time(int(s2_t.split(":")[0]), int(s2_t.split(":")[1]))
    if now_ist.time() < t1: return td.strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t
    if now_ist.time() < t2: return td.strftime("%Y-%m-%d"), "SLOT 2 (EVENING)", s2_t
    return (td + timedelta(days=1)).strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t

target_d, target_s, target_t = get_next_slot()

def append_to_excel_tracker(row_data):
    if not OPENPYXL_AVAILABLE:
        return False
    headers = ["Video ID", "Target Date", "Slot (IST)", "YouTube Status", "Meta Status", "Assigned Playlist", "Concept Title", "Hook Banner", "Drive Batch Folder", "Video Link / Path", "Thumbnail Link / Path", "YouTube Title", "YouTube Description", "YouTube Tags", "YouTube Pinned Comment", "Meta Reel Caption (One-Box)", "Meta First Comment", "Director Visual FX", "Notes / Link to Post"]
    if os.path.exists(EXCEL_TRACKER_PATH):
        try:
            wb = openpyxl.load_workbook(EXCEL_TRACKER_PATH)
            ws = wb["Content & Schedule Tracker"] if "Content & Schedule Tracker" in wb.sheetnames else wb.active
        except Exception:
            wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Content & Schedule Tracker"; ws.append(headers)
    else:
        wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Content & Schedule Tracker"; ws.append(headers)
    ws.append([row_data.get("videoId", f"EV-{ws.max_row:03d}"), row_data.get("targetDate", ""), row_data.get("slot", ""), row_data.get("ytStatus", "Ready in Drive"), row_data.get("metaStatus", "Ready in Drive"), row_data.get("playlist", ""), row_data.get("titleConcept", ""), row_data.get("hookBanner", ""), row_data.get("driveFolder", ""), row_data.get("videoLink", ""), row_data.get("thumbLink", ""), row_data.get("ytTitle", ""), row_data.get("ytDesc", ""), row_data.get("ytTags", ""), row_data.get("ytPinned", ""), row_data.get("metaCaption", ""), row_data.get("metaComment", ""), row_data.get("directorFx", ""), row_data.get("notes", "Staged in Drive")])
    wb.save(EXCEL_TRACKER_PATH)
    return True

SUBTITLE_ARCHETYPES = {
    "IMPERIAL_GOLD":   {"label": "👑 Imperial Gold (Sans Block)",       "ass_primary": "&H0000E5FF", "ass_outline": "&H00000000", "ass_font": "DejaVu Sans",      "ass_size": 74, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0xFFE500", "thumb_font": "thick distressed sans-serif block lettering in radiant imperial gold"},
    "GLACIAL_ICE":     {"label": "❄️ Glacial Ice (Clean Geometric)",    "ass_primary": "&H00FFF500", "ass_outline": "&H00120A04", "ass_font": "DejaVu Sans",      "ass_size": 72, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0x00F5FF", "thumb_font": "crisp geometric industrial block lettering in frost glacial cyan"},
    "FORGE_AMBER":     {"label": "🔥 Forge Amber (Heavy Slab)",         "ass_primary": "&H000099FF", "ass_outline": "&H00050510", "ass_font": "DejaVu Sans",      "ass_size": 76, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0xFF9900", "thumb_font": "heavy chiseled slab-serif lettering in molten forge amber"},
    "CRIMSON_IVORY":   {"label": "🩸 Crimson & Ivory (Editorial Serif)","ass_primary": "&H003838FF", "ass_outline": "&H00F8FAFC", "ass_font": "DejaVu Serif",     "ass_size": 72, "ass_italic": 0, "case_mode": "TITLE", "banner_hex": "0xFF5555", "thumb_font": "bold editorial serif condensed display lettering in deep crimson and warm ivory"},
    "EMERALD_BONE":    {"label": "🌿 Emerald & Bone (Modern Stencil)",  "ass_primary": "&H0086EFAC", "ass_outline": "&H0006120B", "ass_font": "DejaVu Sans",      "ass_size": 74, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0x4ADE80", "thumb_font": "tall condensed stencil display lettering in luminous emerald and bone white"},
    "ROYAL_VIOLET":    {"label": "🔮 Violet & Gold (Classic Serif)",    "ass_primary": "&H00F5D0FE", "ass_outline": "&H002E0845", "ass_font": "DejaVu Serif",     "ass_size": 72, "ass_italic": 0, "case_mode": "TITLE", "banner_hex": "0xE879F9", "thumb_font": "high-contrast classic serif lettering in electric orchid violet and gold"},
    "SILVER_MONO":     {"label": "⌨️ Silver & Charcoal (Typewriter)",   "ass_primary": "&H00F8FAFC", "ass_outline": "&H00111318", "ass_font": "DejaVu Sans Mono", "ass_size": 68, "ass_italic": 0, "case_mode": "UPPER", "banner_hex": "0xE2E8F0", "thumb_font": "stark typewriter monospace stencil lettering in crisp silver-white"},
    "LITERARY_ITALIC": {"label": "📜 Warm Parchment (Literary Italic)", "ass_primary": "&H0077CCFF", "ass_outline": "&H001A0F08", "ass_font": "DejaVu Serif",     "ass_size": 72, "ass_italic": -1,"case_mode": "TITLE", "banner_hex": "0xFBBF24", "thumb_font": "refined literary italic serif lettering in warm champagne gold"}
}

CINEMATOGRAPHY_MATRIX = {
    "PUNCH_FLASH":      {"label": "⚡ Dynamic Kinetic Arc & Probe",       "ffmpeg_eq": "eq=contrast=1.12:brightness=0.01:saturation=1.08", "grade": "High-contrast chiaroscuro, volumetric dust motes, 35mm film grain"},
    "PULL_VIGN":        {"label": "🌊 Atmospheric Parallax & Macro Whip", "ffmpeg_eq": "eq=contrast=1.16:brightness=-0.02:saturation=0.78","grade": "Moody slate-grey palette, deep shadows, muted earth tones"},
    "WARM_DRIFT":       {"label": "🔥 Forge Ember & Optical Rack Focus",  "ffmpeg_eq": "eq=contrast=1.10:brightness=0.02:saturation=1.24", "grade": "Warm tungsten highlights, soft ambient haze, 35mm analog warmth"},
    "NORDIC_CUT":       {"label": "❄️ Nordic Citadel & Fast Shutter Tilt","ffmpeg_eq": "eq=contrast=1.20:brightness=0.0:saturation=0.65",  "grade": "Cold overcast daylight, desaturated steel-blue grading, crisp edges"},
    "OVERHEAD_NOIR":    {"label": "🌑 High-Angle Bird's Eye Noir",        "ffmpeg_eq": "eq=contrast=1.24:brightness=-0.03:saturation=0.85","grade": "High-angle top-down noir shadows and dramatic rim lighting"},
    "GOLDEN_HOUR_ARC":  {"label": "🌅 Low-Horizon Golden Ray Sweep",      "ffmpeg_eq": "eq=contrast=1.08:brightness=0.02:saturation=1.20", "grade": "Warm low-angle golden hour sunbeams and soft depth"},
    "MONOCHROME_GRIT":  {"label": "🖤 Stark Monochrome Documentary",      "ffmpeg_eq": "eq=contrast=1.22:brightness=0.0:saturation=0.0",   "grade": "Stark black-and-white documentary realism and crisp grain"},
    "MODERN_LIFE_REAL": {"label": "🏙️ Modern Everyday Window Realism",    "ffmpeg_eq": "eq=contrast=1.08:brightness=0.01:saturation=1.05", "grade": "Naturalistic modern interior and street daylight, authentic emotion"},
    "TEAL_ORANGE_CINE": {"label": "🎬 Teal & Warm Amber Cinema Grade",    "ffmpeg_eq": "eq=contrast=1.15:brightness=0.0:saturation=1.18,colorbalance=bs=0.08:gs=0.02:rs=-0.05:rh=0.08:gh=0.02:bh=-0.06", "grade": "Cinematic teal shadows with warm amber highlights, anamorphic depth"},
    "EMERALD_DUSK":     {"label": "🌲 Deep Forest Emerald & Silver Dusk", "ffmpeg_eq": "eq=contrast=1.14:brightness=-0.01:saturation=0.92,colorbalance=gs=0.06:bs=0.04:gm=0.03", "grade": "Moody deep emerald-slate twilight atmosphere with crisp rim highlights"}
}

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
    "LIVED CONFESSION", "LEADER QUOTE BREAKDOWN", "CONTRARIAN REALITY CHECK",
    "BEHAVIORAL OBSERVATION", "PROVOKING QUESTION", "QUIET PARABLE"
]

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
    {"day": d, "fmt": fmt, "leader": ldr, "pl": pl, "style": st_k, "arch": ar_k, "badge": bdg, "hook_title": hk,
     "script": f"Day {d} reflection with {ldr}: steady habits beat loud claims when pressure arrives. Stay composed, protect your focus, and let quiet action speak for itself. {q}",
     "q": q,
     "s1": f"35mm wide shot establishing {hk.lower()} in {fmt.lower().replace('_', ' ')}",
     "s2": f"85mm close detail capturing {ldr} theme of {bdg.lower()}",
     "s3": f"35mm tracking shot reinforcing {bdg.lower()} in motion",
     "s4": "85mm portrait close-up with steady calm gaze"}
    for (d, fmt, ldr, pl, st_k, ar_k, bdg, hk, q) in _DAY_SPECS
]

DIVERSE_ARCHETYPES = [
    "A thoughtful man in his late thirties in a dark olive knit sweater by a sunlit window. Strictly two arms only.",
    "An elder mentor with silver-streaked beard and calm eyes with a young apprentice in a courtyard. Strictly two arms per person.",
    "A disciplined craftsman in his fifties in a rugged canvas jacket inspecting precision tools. Strictly two arms only.",
    "A seasoned traveler in his fifties walking along a misty alpine ridge at sunrise. Strictly two arms only.",
    "A composed mature man in a tailored dark coat walking calmly down a dusk street. Strictly two arms only.",
    "A mature Roman centurion with stern weathered face and dark iron shoulder plates over crimson tunic. Strictly two arms only."
]

SETTINGS_MATRIX = [
    {"n": "Modern Sunlit Apartment", "d": "Calm modern apartment window with natural daylight."},
    {"n": "Quiet Dusk Street", "d": "Peaceful evening street with warm reflections."},
    {"n": "Wood-Paneled Study", "d": "Quiet library study with warm desk lamp light."},
    {"n": "Misty Coastal Cliffs", "d": "High coastal cliffs overlooking ocean mist."},
    {"n": "Craftsman Workshop", "d": "Sunlit timber and stone workshop with hand tools."},
    {"n": "Sunlit Alpine Ridge", "d": "High rocky granite ridge in crisp daylight."}
]

@st.cache_resource(show_spinner=False)
def get_fast_gemini_client(clean_k):
    try:
        return genai.Client(api_key=clean_k, http_options=types.HttpOptions(timeout=15000))
    except Exception:
        return genai.Client(api_key=clean_k)

def normalize_spoken_text(text):
    t = text.replace("...", ".").replace("…", ".").replace("—", ", ").replace("–", ", ").replace(" / ", ", ")
    return re.sub(r"\s+", " ", t).strip()

async def synthesize_speech_timed(text, audio_path, primary_voice="Edge-Christopher", api_key="", use_gemini_tts=False):
    spoken = normalize_spoken_text(text)
    if api_key and use_gemini_tts:
        try:
            client = get_fast_gemini_client(api_key)
            res = client.models.generate_content(
                model="gemini-3.8-flash-lite-tts",
                contents=f"Read calmly at a natural pace: {spoken}",
                config=types.GenerateContentConfig(response_modalities=["AUDIO"], speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Charon"))))
            )
            for cand in res.candidates:
                for part in cand.content.parts:
                    if part.inline_data and part.inline_data.data:
                        raw_f = audio_path + ".raw"
                        with open(raw_f, "wb") as f: f.write(part.inline_data.data)
                        subprocess.run(["ffmpeg", "-y", "-i", raw_f, "-c:a", "libmp3lame", "-b:a", "192k", audio_path], capture_output=True)
                        if os.path.exists(raw_f): os.remove(raw_f)
                        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 3000:
                            return [], "Gemini Natural (Charon)"
        except Exception:
            pass
    try:
        comm = edge_tts.Communicate(spoken, voice="en-US-ChristopherNeural", rate="+0%", pitch="-2Hz")
        timings = []
        with open(audio_path, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio": f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    timings.append({"word": chunk.get("text", ""), "start": round(chunk["offset"]/1e7, 3), "end": round((chunk["offset"]+chunk["duration"])/1e7, 3)})
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 6000:
            return timings, "Christopher Natural (US Male)"
    except Exception:
        pass
    subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", "-t", "18.5", "-c:a", "libmp3lame", audio_path], capture_output=True)
    return [], "Ambient Timing Bed"
    def build_ass_subtitles(timed_words, script_text, ass_path, total_dur, arch_key="IMPERIAL_GOLD"):
    arch_cfg = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])
    events = []
    if timed_words and len(timed_words) >= 5:
        clean_words = []
        for tw in timed_words:
            w_txt = re.sub(r"[^\w\s',.!?]", "", tw["word"].replace("-", " ")).strip()
            if w_txt:
                for sub_w in w_txt.split():
                    clean_words.append({"word": sub_w.upper() if arch_cfg["case_mode"] == "UPPER" else sub_w, "start": tw["start"], "end": tw["end"]})
        chunk = []
        for i, tw in enumerate(clean_words):
            chunk.append(tw)
            if any(tw["word"].endswith(p) for p in [".", "!", "?", ","]) or len(chunk) >= 3:
                st_t = chunk[0]["start"]
                en_t = clean_words[i+1]["start"] if i+1 < len(clean_words) else min(total_dur, chunk[-1]["end"]+0.3)
                events.append((st_t, en_t, " ".join(c["word"] for c in chunk).strip()))
                chunk = []
        if chunk:
            events.append((chunk[0]["start"], min(total_dur, chunk[-1]["end"]+0.3), " ".join(c["word"] for c in chunk).strip()))
    else:
        tokens = normalize_spoken_text(script_text).split()
        groups = [tokens[i:i+3] for i in range(0, len(tokens), 3)]
        step = max(0.45, (total_dur - 0.7) / max(1, len(groups)))
        for idx, grp in enumerate(groups):
            txt = re.sub(r"[^\w\s',.!?]", "", " ".join(grp)).strip()
            if txt:
                events.append((0.35 + idx*step, min(total_dur, 0.35 + (idx+1)*step), txt.upper() if arch_cfg["case_mode"] == "UPPER" else txt))
    def fmt(s): return f"{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}"
    ass_doc = f"[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,{arch_cfg['ass_font']},{arch_cfg['ass_size']},{arch_cfg['ass_primary']},&H000000FF,{arch_cfg['ass_outline']},&H80000000,-1,{arch_cfg['ass_italic']},0,0,100,100,0,0,1,6,3,2,50,50,420,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    for st_t, en_t, txt in events:
        ass_doc += f"Dialogue: 0,{fmt(st_t)},{fmt(en_t)},Default,,0,0,0,,{txt}\n"
    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_doc)

def build_unique_fallback_script(day_entry, leader_pick):
    variants = [
        f"Most people chase loud approval until pressure exposes what holds. {leader_pick['leader']} reminded us that {leader_pick['thought'].lower().rstrip('.')} Guard your focus and let quiet action speak. {day_entry['q']}",
        f"Real character shows up when plans get inconvenient. {leader_pick['leader']} left a clear standard: {leader_pick['thought'].lower().rstrip('.')} Keep your discipline steady in ordinary weeks. {day_entry['q']}",
        f"A calm mind beats a crowded schedule every time. Drawing from {leader_pick['leader']}, {leader_pick['thought'].lower().rstrip('.')} Pause before answering and protect your peace. {day_entry['q']}"
    ]
    random.shuffle(variants)
    for v in variants:
        c = normalize_spoken_text(v)
        if not is_script_already_used(c):
            return c
    return normalize_spoken_text(f"{leader_pick['leader']} note: {leader_pick['thought'].lower().rstrip('.')} Stay steady today. {day_entry['q']}")

def generate_varied_package(raw_api_key, day_entry, custom_setting=None):
    clean_key = raw_api_key.strip().strip('"').strip("'") if raw_api_key else ""
    sett_desc = custom_setting or random.choice(SETTINGS_MATRIX)["d"]
    char_desc = random.choice(DIVERSE_ARCHETYPES)
    leader_pick = random.choice(LEADER_WISDOM_POOL)
    hook_style = random.choice(HOOK_FRAMEWORKS)
    style_meta = CINEMATOGRAPHY_MATRIX.get(day_entry["style"], CINEMATOGRAPHY_MATRIX["MODERN_LIFE_REAL"])
    arch_cfg = SUBTITLE_ARCHETYPES.get(day_entry["arch"], SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])

    pkg = {
        "title_concept": f"Day {day_entry['day']}: {day_entry['hook_title'].title()} ({leader_pick['leader']})",
        "playlist": day_entry["pl"],
        "hook_banner": day_entry["hook_title"].upper(),
        "video_overlay_text": day_entry["badge"],
        "subtitle_archetype": day_entry["arch"],
        "director_style": day_entry["style"],
        "script": day_entry["script"],
        "scene1_prompt": f"[4-second vertical 9:16 cinematic video clip] {day_entry['s1']}. Context: {sett_desc}. {style_meta['grade']}. Strictly two arms.",
        "scene2_prompt": f"[4-second vertical 9:16 cinematic video clip] {day_entry['s2']}. {style_meta['grade']}.",
        "scene3_prompt": f"[4-second vertical 9:16 cinematic video clip] {day_entry['s3']}. Same subject ({char_desc[:60]}). {style_meta['grade']}.",
        "scene4_prompt": f"[4-second vertical 9:16 cinematic video clip] {day_entry['s4']}. {style_meta['grade']}.",
        "thumbnail_prompt": f"9:16 vertical frame with {char_desc} in {sett_desc}. Upper-third text \"{day_entry['hook_title'].upper()}\" in {arch_cfg['thumb_font']}.",
        "youtube_title": f"⚡ {day_entry['hook_title'].title()} ({leader_pick['leader']}) #shorts #mindset",
        "reflection_question": day_entry["q"],
        "caption_lesson": day_entry["script"]
    }

    if is_script_already_used(pkg["script"], pkg["hook_banner"]):
        pkg["hook_banner"] = f"{leader_pick['leader'].upper()} • {day_entry['badge']}"
        pkg["script"] = build_unique_fallback_script(day_entry, leader_pick)
        pkg["caption_lesson"] = pkg["script"]

    hist = load_used_scripts_history()
    if clean_key:
        used_s = "\n".join([f"- {h.get('script','')[:140]}" for h in hist[-35:] if h.get("script")]) or "None."
        prompt = f"Write a fresh 45-52 word spoken script for men 35-65+ using {leader_pick['leader']} ({leader_pick['thought']}) and format {hook_style}. Avoid these used scripts:\n{used_s}\nOutput JSON only with keys: title_concept, hook_banner, script, scene1_prompt, scene2_prompt, scene3_prompt, scene4_prompt, thumbnail_prompt, youtube_title, reflection_question."
        try:
            client = get_fast_gemini_client(clean_key)
            r = client.models.generate_content(model="gemini-3.8-flash", contents=prompt, config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.98))
            m = re.search(r"\{.*\}", r.text.strip(), re.DOTALL)
            parsed = json.loads(m.group(0) if m else r.text.strip())
            if isinstance(parsed, dict) and parsed.get("script"):
                if is_script_already_used(parsed["script"], parsed.get("hook_banner", "")):
                    parsed["script"] = build_unique_fallback_script(day_entry, leader_pick)
                pkg.update({k: v for k, v in parsed.items() if v})
                pkg["caption_lesson"] = pkg["script"]
        except Exception:
            pass

    record_generated_script(pkg["script"], pkg["hook_banner"], f"DAY_{day_entry['day']:02d}")
    return pkg, f"Unique History ({leader_pick['leader']} • {len(load_used_scripts_history())} Locked)"

if "active_video_pkg" not in st.session_state and os.path.exists(DRAFT_JSON_PATH):
    try:
        with open(DRAFT_JSON_PATH, "r", encoding="utf-8") as f:
            d_data = json.load(f)
            d_data["audio"] = DRAFT_AUDIO_PATH
            st.session_state["active_video_pkg"] = d_data
    except Exception:
        pass

if "rendered_video_path" not in st.session_state:
    mp = os.path.join(TMP_DIR, "master_output.mp4")
    if os.path.exists(mp) and os.path.getsize(mp) > 10000:
        st.session_state["rendered_video_path"] = mp

recent_ids = db.get("used_theme_ids", [])[-30:]
_locked_total = len(load_used_scripts_history())

st.markdown(f"""
<div style="font-size:22px;font-weight:800;color:#F8FAFC;margin-bottom:8px;">🎬 ECHOES VIDEO STUDIO <span style="font-size:12px;color:#38BDF8;font-family:monospace;">v9.6</span></div>
<div style="margin-bottom:12px;">
    <span class="badge badge-green">● {_locked_total} SCRIPTS LOCKED FOREVER</span>
    <span class="badge badge-purple">🏛️ 15+ LEADERS</span>
    <span class="badge badge-blue">🎨 8 FONTS & 10 GRADES</span>
    <span class="badge badge-amber">📅 {target_d} @ {target_t} IST ({target_s})</span>
</div>
""", unsafe_allow_html=True)

if "status_banner" in st.session_state:
    st.success(st.session_state.pop("status_banner"))

with st.expander("🔑 API CREDENTIALS & PLATFORM HANDLES", expanded=(not bool(get_persistent_api_key()))):
    uk = st.text_input("Gemini API Key", value=get_persistent_api_key(), type="password", key="user_key_input")
    if uk: save_persistent_api_key(uk)
    c1, c2 = st.columns(2)
    with c1:
        uyt = st.text_input("YouTube Handle", value=get_persistent_yt_handle())
        if uyt != get_persistent_yt_handle(): save_persistent_yt_handle(uyt)
    with c2:
        umeta = st.text_input("Meta Handle", value=get_persistent_meta_handle())
        if umeta != get_persistent_meta_handle(): save_persistent_meta_handle(umeta)
    ug = st.text_input("Google Sheets Webhook (Optional)", value=get_persistent_gsheet_url())
    if ug: save_persistent_gsheet_url(ug)

def render_copy(bid, label, text):
    b64_v = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    components.html(f"""<button id="b_{bid}" onclick="navigator.clipboard.writeText(decodeURIComponent(escape(atob('{b64_v}'))));this.innerText='✓ COPIED!';" style="width:100%;height:2.5rem;background:rgba(56,189,248,0.12);color:#38BDF8;border:1px solid rgba(56,189,248,0.35);border-radius:8px;font-weight:700;font-size:12px;cursor:pointer;">📋 {label}</button>""", height=44)

def run_day_generation(day_obj, arch_opt, style_opt, sett_opt, use_gem):
    k = get_persistent_api_key()
    entry = dict(day_obj)
    if arch_opt != "📅 Day Preset": entry["arch"] = arch_opt
    if style_opt != "📅 Day Preset": entry["style"] = style_opt
    s_desc = None if sett_opt.startswith("🎲") else next((x["d"] for x in SETTINGS_MATRIX if x["n"] == sett_opt), None)
    pkg, eng_src = generate_varied_package(k, entry, custom_setting=s_desc)
    timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k, use_gemini_tts=use_gem))
    draft = {"pkg": pkg, "t_id": f"DAY_{entry['day']:02d}", "p": entry["fmt"], "pl": entry["pl"], "s": entry["style"], "audio": DRAFT_AUDIO_PATH, "timings": timings, "voice_used": v_name, "engine_source": eng_src}
    with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f: json.dump(draft, f, indent=2)
    save_to_draft_vault(draft)
    st.session_state["active_video_pkg"] = draft
    st.session_state["rendered_director_style"] = entry["style"]
    st.session_state.pop("rendered_video_path", None)

tab1, tab2, tab3 = st.tabs(["⚡ 1. SCRIPT & PROMPTS", "🎬 2. RENDER & METADATA", "📋 3. QUEUE & TRACKER"])

with tab1:
    vault_items = load_draft_vault()
    if vault_items:
        with st.expander(f"📦 RESTORE PREVIOUS DRAFT ({len(vault_items)} SAVED)", expanded=False):
            v_idx = st.selectbox("Saved Drafts", range(len(vault_items)), format_func=lambda i: f"⚡ {vault_items[i].get('pkg',{}).get('hook_banner','Draft')} — {vault_items[i].get('t_id','')}")
            if st.button("🔄 Restore Draft"):
                st.session_state["active_video_pkg"] = vault_items[v_idx]
                st.rerun()

    day_mode = st.radio("Day Selection", ["🎲 Auto-Next Unused", "🗓️ Pick Day 1–30"], horizontal=True)
    used_norms = {h.get("norm_script", "") for h in load_used_scripts_history()}
    if "Auto-Next" in day_mode:
        unused_days = [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" not in recent_ids and normalize_script_key(d.get("script", "")) not in used_norms]
        if not unused_days:
            unused_days = [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" not in recent_ids]
        selected_day = unused_days[0] if unused_days else THIRTY_DAY_CURRICULUM[len(recent_ids) % 30]
    else:
        dn = st.selectbox("Select Day", [d["day"] for d in THIRTY_DAY_CURRICULUM], format_func=lambda n: f"Day {n:02d} — {THIRTY_DAY_CURRICULUM[n-1]['fmt']}")
        selected_day = THIRTY_DAY_CURRICULUM[dn - 1]

    c1, c2, c3 = st.columns(3)
    with c1: chosen_arch = st.selectbox("Font & Color", ["📅 Day Preset"] + list(SUBTITLE_ARCHETYPES.keys()), format_func=lambda x: "📅 Day Preset" if x == "📅 Day Preset" else SUBTITLE_ARCHETYPES[x]["label"])
    with c2: chosen_style = st.selectbox("Camera & Grade", ["📅 Day Preset"] + list(CINEMATOGRAPHY_MATRIX.keys()), format_func=lambda x: "📅 Day Preset" if x == "📅 Day Preset" else CINEMATOGRAPHY_MATRIX[x]["label"])
    with c3: chosen_sett = st.selectbox("Background", ["🎲 Auto-Rotate"] + [s["n"] for s in SETTINGS_MATRIX])

    voice_mode = st.radio("Voice", ["🎙️ Natural Calm Voice (Edge-TTS)", "🔊 Gemini AI Voice (Charon)"], horizontal=True)

    if st.button("🚀 Generate Non-Repeating Day Package & Audio", type="primary"):
        with st.spinner("⚡ Generating non-repeating script & audio..."):
            run_day_generation(selected_day, chosen_arch, chosen_style, chosen_sett, "Gemini" in voice_mode)
        st.rerun()

    if "active_video_pkg" in st.session_state:
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data.get("pkg", {})
        st.divider()
        st.subheader(f"📜 {pkg.get('title_concept', 'Reel')}")
        st.caption(f"Engine: `{p_data.get('engine_source','')}` | Voice: `{p_data.get('voice_used','')}`")
        st.info(f"**Script:** {pkg.get('script','')}\n\n**Question:** *{pkg.get('reflection_question','')}*")

        b_col1, b_col2 = st.columns(2)
        with b_col1:
            if st.button("🔄 Discard & Generate New Script", use_container_width=True):
                cur_tid = p_data.get("t_id", "")
                cur_norms = {h.get("norm_script", "") for h in load_used_scripts_history()}
                alts = [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" != cur_tid and normalize_script_key(d.get("script","")) not in cur_norms] or [d for d in THIRTY_DAY_CURRICULUM if f"DAY_{d['day']:02d}" != cur_tid]
                run_day_generation(random.choice(alts), chosen_arch, chosen_style, chosen_sett, "Gemini" in voice_mode)
                st.rerun()
        with b_col2:
            if st.button("🗑️ Discard Draft", use_container_width=True):
                for fp in [DRAFT_JSON_PATH, DRAFT_AUDIO_PATH]:
                    if os.path.exists(fp):
                        try: os.remove(fp)
                        except Exception: pass
                st.session_state.pop("active_video_pkg", None)
                st.rerun()

        if os.path.exists(DRAFT_AUDIO_PATH):
            st.audio(DRAFT_AUDIO_PATH)

        up_v = st.file_uploader("Upload Custom Voice MP3", type=["mp3"])
        if up_v:
            with open(DRAFT_AUDIO_PATH, "wb") as f: f.write(up_v.read())
            p_data["timings"] = []
            st.rerun()

        for idx, (lbl, k_n) in enumerate([("SCENE 1", "scene1_prompt"), ("SCENE 2", "scene2_prompt"), ("SCENE 3", "scene3_prompt"), ("SCENE 4", "scene4_prompt"), ("THUMBNAIL", "thumbnail_prompt")]):
            st.text_area(lbl, pkg.get(k_n, ""), height=68, key=f"pr_{idx}")
            render_copy(f"pr_{idx}", f"COPY {lbl}", pkg.get(k_n, ""))

def get_persisted_clips():
    return sorted([os.path.join(SAVED_CLIPS_DIR, f) for f in os.listdir(SAVED_CLIPS_DIR) if f.lower().endswith((".mp4", ".mov"))])

with tab2:
    up_clips = st.file_uploader("Upload 2+ Video Clips (Saved on Disk)", type=["mp4", "mov"], accept_multiple_files=True)
    if up_clips:
        for old_f in os.listdir(SAVED_CLIPS_DIR):
            try: os.remove(os.path.join(SAVED_CLIPS_DIR, old_f))
            except Exception: pass
        for idx, c in enumerate(sorted(up_clips, key=lambda x: x.name)):
            with open(os.path.join(SAVED_CLIPS_DIR, f"clip_{idx:02d}_{c.name}"), "wb") as f:
                f.write(c.read())

    clip_paths = get_persisted_clips()
    if clip_paths:
        st.success(f"✓ {len(clip_paths)} clip(s) saved in vault.")

    fx_key = st.selectbox("Color Grade", list(CINEMATOGRAPHY_MATRIX.keys()), format_func=lambda x: CINEMATOGRAPHY_MATRIX[x]["label"])
    if st.button("🎬 Render Master 9:16 Reel", type="primary"):
        if "active_video_pkg" not in st.session_state or len(clip_paths) < 2:
            st.error("Generate a script in Tab 1 and upload at least 2 clips.")
        else:
            p_data = st.session_state["active_video_pkg"]
            pkg = p_data["pkg"]
            arch_key = pkg.get("subtitle_archetype", "IMPERIAL_GOLD")
            probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", DRAFT_AUDIO_PATH], capture_output=True, text=True)
            dur = (float(probe.stdout.strip()) if probe.stdout.strip() else 18.5) + 0.4
            speed = (dur / float(len(clip_paths))) / 4.0
            ass_p = os.path.join(TMP_DIR, "subtitles.ass")
            build_ass_subtitles(p_data.get("timings", []), pkg["script"], ass_p, dur, arch_key)
            out_p = os.path.join(TMP_DIR, "master_output.mp4")
            c_ass = ass_p.replace(":", "\\:")
            c_fnt = FONTS_DIR.replace(":", "\\:")
            v_f = []
            for i in range(len(clip_paths)):
                v_f.append(f"[{i}:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed:.4f},scale=1224:2174:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:0,fps=25,vignette=PI/4,noise=alls=3:allf=t+u,{CINEMATOGRAPHY_MATRIX[fx_key]['ffmpeg_eq']}[v{i}];")
            v_f.append("".join(f"[v{i}]" for i in range(len(clip_paths))) + f"concat=n={len(clip_paths)}:v=1:a=0,ass='{c_ass}':fontsdir='{c_fnt}'[vout];[{len(clip_paths)}:a]loudnorm=I=-14:TP=-1.0:LRA=7[aout]")
            inputs = []
            for cp in clip_paths: inputs.extend(["-i", cp])
            inputs.extend(["-i", DRAFT_AUDIO_PATH])
            res = subprocess.run(["ffmpeg", "-y", *inputs, "-filter_complex", "".join(v_f), "-map", "[vout]", "-map", "[aout]", "-t", str(dur), "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", out_p], capture_output=True, text=True)
            if res.returncode == 0:
                st.session_state["rendered_video_path"] = out_p
                st.success("✓ Master 9:16 Reel Rendered!")
            else:
                st.error(res.stderr[:250])

    st.divider()
    st.markdown("### 🖼️ Thumbnail Cropper")
    up_th = st.file_uploader("Upload Raw Thumbnail", type=["png", "jpg", "jpeg", "webp"], key="th_up")
    if up_th:
        with open(SAVED_THUMB_PATH, "wb") as f: f.write(up_th.read())
    if os.path.exists(SAVED_THUMB_PATH):
        tim = Image.open(SAVED_THUMB_PATH).convert("RGB")
        pct = 0.125 if "Deep" in st.radio("Crop", ["Standard (6.5%)", "Deep (12.5%)"], horizontal=True) else 0.065
        tw, th = tim.size
        ch = th - int(th * pct)
        cw = int(ch * (9.0 / 16.0))
        mx = max(0, (tw - cw) // 2)
        clean_t = tim.crop((mx, 0, mx + cw, ch)).resize((1080, 1920), Image.Resampling.LANCZOS)
        st.image(clean_t, use_container_width=True)
        t_buf = io.BytesIO(); clean_t.save(t_buf, format="PNG")
        st.download_button("💾 Download Cropped Thumbnail", t_buf.getvalue(), f"{target_d.replace('-','')}_thumb.png", "image/png")

    slug = re.sub(r"[^a-zA-Z0-9]+", "_", st.session_state.get("active_video_pkg", {}).get("pkg", {}).get("hook_banner", "reel")).strip("_").lower()
    if "rendered_video_path" in st.session_state and os.path.exists(st.session_state["rendered_video_path"]):
        st.video(st.session_state["rendered_video_path"])
        with open(st.session_state["rendered_video_path"], "rb") as vf:
            st.download_button(f"💾 Download Master Reel ({target_d}_{slug}.mp4)", vf.read(), f"{target_d}_{slug}.mp4", "video/mp4")

    if "active_video_pkg" in st.session_state:
        pkg = st.session_state["active_video_pkg"]["pkg"]
        q_ref = pkg.get("reflection_question", "")
        hook_t = pkg.get("hook_banner", "DAILY INSIGHT").title()
        yt_title = pkg.get("youtube_title", f"⚡ {hook_t} 🎯 #shorts #mindset")
        if "#shorts" not in yt_title.lower(): yt_title += " #shorts #mindset"
        yt_desc = f"⚡ {hook_t} 🏛️\n\n🎙️ {pkg.get('script','')}\n\n💬 {q_ref}\n\n🔔 Subscribe to {get_persistent_yt_handle()}\n\n#mindset #lifelessons #selfgrowth #discipline #wisdom #shorts"
        meta_cap = f"⚡ {hook_t} 🏛️\n\n{pkg.get('caption_lesson','')}\n\n💬 {q_ref}\n\n🔖 Save or share.\n✨ Follow {get_persistent_meta_handle()}\n\n#Mindset #LifeLessons #PersonalGrowth #SelfRespect #Discipline #Wisdom"
        st.divider()
        st.text_input("YouTube Title", yt_title, key="yt_t_in"); render_copy("ytt", "COPY YOUTUBE TITLE", yt_title)
        st.text_area("YouTube Description", yt_desc, height=130, key="yt_d_in"); render_copy("ytd", "COPY YOUTUBE DESCRIPTION", yt_desc)
        st.text_input("YouTube Playlist", pkg.get("playlist", PLAYLIST_OPTIONS[0]), key="yt_p_in"); render_copy("ytp", "COPY YOUTUBE PLAYLIST", pkg.get("playlist", PLAYLIST_OPTIONS[0]))
        st.text_area("Meta Caption", meta_cap, height=145, key="fb_c_in"); render_copy("fbc", "COPY META CAPTION", meta_cap)
        st.markdown('<a href="https://business.facebook.com/latest/reels_composer" target="_blank"><button style="width:100%;height:3rem;background:#1877F2;color:#FFF;border:none;border-radius:8px;font-weight:700;margin:10px 0;">🌐 OPEN META REELS COMPOSER</button></a>', unsafe_allow_html=True)

        if st.button("✅ Lock Day & Advance", type="primary"):
            p_data = st.session_state["active_video_pkg"]
            db["scheduled_videos"].append({"date": target_d, "slot": target_s, "time": target_t, "theme_id": p_data.get("t_id"), "title": yt_title, "file": f"{target_d}_{slug}.mp4"})
            if p_data.get("t_id") and p_data["t_id"] not in db.get("used_theme_ids", []):
                db.setdefault("used_theme_ids", []).append(p_data["t_id"])
            db["last_scheduled_date"], db["last_scheduled_slot"] = target_d, target_s
            save_db(db)
            append_to_excel_tracker({"targetDate": target_d, "slot": target_s, "playlist": pkg.get("playlist",""), "titleConcept": pkg.get("title_concept",""), "hookBanner": pkg.get("hook_banner",""), "videoLink": f"{target_d}_{slug}.mp4", "ytTitle": yt_title, "ytDesc": yt_desc, "metaCaption": meta_cap})
            nd, ns, nt = get_next_slot(target_d, target_s)
            st.session_state["status_banner"] = f"✓ Locked {p_data.get('t_id')}! Next: {nd} @ {nt} IST ({ns})"
            st.rerun()

with tab3:
    if os.path.exists(EXCEL_TRACKER_PATH):
        with open(EXCEL_TRACKER_PATH, "rb") as ef:
            st.download_button("📊 Download Tracker (.xlsx)", ef.read(), "Echoes_Of_Wisdom_Content_Tracker.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.markdown(f"### Scheduled Days ({len(db.get('used_theme_ids', []))}/30)")
    for item in reversed(db.get("scheduled_videos", [])):
        st.write(f"- **{item.get('date')}** ({item.get('theme_id')}): {item.get('title')}")

    st.divider()
    used_hist_list = load_used_scripts_history()
    st.markdown(f"### 🔒 All Previously Used Scripts ({len(used_hist_list)} Saved in `used_scripts_history.json`)")
    if not used_hist_list:
        st.info("No scripts recorded in `used_scripts_history.json` yet. Generate a script in Tab 1 to start tracking.")
    else:
        for idx, h_item in enumerate(reversed(used_hist_list), 1):
            with st.expander(f"#{idx} • {h_item.get('hook') or h_item.get('theme_id') or 'Script'} ({h_item.get('created_at', '')})", expanded=False):
                st.write(h_item.get("script", ""))
