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
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# ---------------------------------------------------------
# 1. PAGE SETUP & MODERN CLEAN STUDIO UI
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
# 2. FILE PATHWAYS & PERSISTENCE
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
# DRAFT VAULT ENGINE (Survives App Reboots & Inactivity)
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
    vault = vault[:25]
    try:
        with open(DRAFT_VAULT_PATH, "w", encoding="utf-8") as f:
            json.dump(vault, f, indent=2)
    except Exception: pass

SUBTITLE_ARCHETYPES = {
    "IMPERIAL_GOLD": {"label": "👑 Imperial Gold", "ass_primary": "&H0000E5FF", "banner_hex": "0xFFE500", "prefix": "gold_"},
    "GLACIAL_ICE":   {"label": "❄️ Glacial Ice",   "ass_primary": "&H00FFF500", "banner_hex": "0x00F5FF", "prefix": "ice_"},
    "FORGE_AMBER":   {"label": "🔥 Forge Amber",   "ass_primary": "&H000099FF", "banner_hex": "0xFF9900", "prefix": "amber_"}
}

# ---------------------------------------------------------
# DYNAMIC CINEMATOGRAPHY & INTRA-SHOT KINETIC MATRIX
# ---------------------------------------------------------
CINEMATOGRAPHY_MATRIX = {
    "PUNCH_FLASH": {
        "label": "⚡ Dynamic Kinetic Arc & Probe (High Retention)",
        "lens_s1": "24mm ultra-wide cinema prime lens with subtle anamorphic barrel distortion",
        "cam_s1": "0s-2s: Low-angle Dutch tilt in deep shadow; 2s-4s: rapid forward push-in accelerating smoothly towards protagonist's piercing eyes as a sharp shaft of sunlight strikes his face",
        "lens_s2": "100mm macro probe lens, extreme shallow depth of field (f/1.8)",
        "cam_s2": "0s-2s: Microscopic close-up tracking fine surface textures and golden light glints; 2s-4s: smooth dynamic whip-pan revealing the entire object in dramatic chiaroscuro motion",
        "lens_s3": "35mm anamorphic cinema lens, natural horizontal streak flare",
        "cam_s3": "0s-2s: Fast over-the-shoulder tracking dolly following deliberate strides; 2s-4s: camera sweeps around subject in a dramatic 45-degree parallax arc against towering cliff peaks",
        "lens_s4": "85mm portrait telephoto lens, creamy optical bokeh",
        "cam_s4": "0s-2s: Slow breathing push-in on weathered skin texture; 2s-4s: protagonist raises piercing calm eyes directly into camera lens",
        "grade": "Cinematic high-contrast chiaroscuro, volumetric dust motes, rich dark shadows, textured 35mm film stock quality"
    },
    "PULL_VIGN": {
        "label": "🌊 Atmospheric Parallax & Macro Whip (Epic Scale)",
        "lens_s1": "35mm prime cinema lens with natural optical vignetting and peripheral falloff",
        "cam_s1": "0s-2s: Tight framing on protagonist's stoic composure; 2s-4s: continuous smooth pull-back dolly shot revealing the vast scale of ancient towering stone colonnades",
        "lens_s2": "90mm macro cine lens, hyper-sharp plane of focus",
        "cam_s2": "0s-2s: Extreme close-up rack focus starting blurred on flying embers; 2s-4s: snaps into tack-sharp focus on the rugged moving mechanism with cinematic speed ramp feel",
        "lens_s3": "28mm wide-angle documentary lens, deep depth of field",
        "cam_s3": "0s-2s: Low ground-level pedestal shot tracking protagonist's boots pacing across wet stone; 2s-4s: camera cranes smoothly upward to reveal his full silhouette against stormy horizon",
        "lens_s4": "85mm prime lens, soft feathered vignette framing",
        "cam_s4": "0s-2s: Profile angle cloaked in deep cool shadow; 2s-4s: subject turns slowly to face camera, piercing steady gaze, atmospheric fog swirling behind",
        "grade": "Moody slate-grey palette, deep blacks, muted cinematic earth tones, desaturated epic atmosphere"
    },
    "WARM_DRIFT": {
        "label": "🔥 Forge Ember & Optical Rack Focus (Warm 35mm)",
        "lens_s1": "50mm high-speed cinema lens, soft vintage warmth and natural perspective",
        "cam_s1": "0s-2s: Camera drifts slowly laterally past foreground stone pillar; 2s-4s: reveals protagonist standing resolute with golden rim light outlining his woolen mantle",
        "lens_s2": "100mm macro lens, ultra-high magnification",
        "cam_s2": "0s-2s: Macro shot of glowing orange ember particles floating in air; 2s-4s: dynamic camera drift downward tracking intense impact and heat waves",
        "lens_s3": "35mm anamorphic cinema lens, warm flare halation",
        "cam_s3": "0s-2s: Medium tracking shot pacing beside protagonist; 2s-4s: camera elevates into high-angle perspective showing him walking resolutely through misty stone courtyard",
        "lens_s4": "85mm portrait lens with warm amber backlighting",
        "cam_s4": "0s-2s: Tight close-up, warm torchlight flicker dancing across lined forehead and weathered eyes; 2s-4s: steady resolute nod of timeless acceptance",
        "grade": "3200K warm tungsten glow, rich golden hour highlights, soft ambient haze, 35mm analog warmth"
    },
    "NORDIC_CUT": {
        "label": "❄️ Nordic Citadel & Fast Shutter Tilt (Cold Steel)",
        "lens_s1": "24mm ultra-wide cinema lens, dramatic angular perspective",
        "cam_s1": "0s-2s: Symmetrical centered locked-off wide shot in gale-force mountain mist; 2s-4s: sudden aggressive snap-zoom forward locking onto protagonist's unflinching eyes",
        "lens_s2": "100mm probe lens, needle-sharp crystalline detail",
        "cam_s2": "0s-2s: Extreme macro tracking frost crystals and glistening surface edges; 2s-4s: fast downward tilt capturing raw mechanical power in freezing mist",
        "lens_s3": "50mm prime lens, stark documentary clarity",
        "cam_s3": "0s-2s: Handheld camera movement following protagonist along narrow rocky precipice; 2s-4s: camera stabilizes as dark woolen cloak billows violently against jagged peaks",
        "lens_s4": "105mm telephoto portrait lens, intense subject isolation",
        "cam_s4": "0s-2s: Extreme macro close-up on eye iris reflecting mountain horizon; 2s-4s: pulls back to reveal weathered stoic face exhaling cold visible breath mist",
        "grade": "5600K cold daylight overcast, desaturated blue-grey grading, stark razor-sharp edges, high visual tension"
    }
}

DIRECTOR_STYLES = {k: v["label"] for k, v in CINEMATOGRAPHY_MATRIX.items()}

VOICE_PROFILES = {
    "Gemini-Charon":           "🎙️ Charon (Gemini 3.8 AI - Deep Stoic US Male, 100% Reliable)",
    "Gemini-Fenrir":           "🎙️ Fenrir (Gemini 3.8 AI - Resonant Authoritative US Male)",
    "en-US-ChristopherNeural": "🎙️ Christopher (Edge-TTS Natural US Male)",
    "en-US-GuyNeural":         "🎙️ Guy (Edge-TTS Natural US Male)"
}

PLAYLIST_OPTIONS = [
    "The art of moving in silence (stoic mindset)",
    "Mastering human nature and fake friends ancient parables",
    "Financial Sovereignty and Relentless Discipline",
    "Father to Son: Ancient Legacy Lessons",
    "Aging Well: Habits for Mind and Body"
]

def get_library_tracks():
    if not os.path.exists(MUSIC_DIR): return []
    return sorted([f for f in os.listdir(MUSIC_DIR) if f.lower().endswith((".mp3", ".wav", ".m4a"))])

def resolve_background_track(choice_key, archetype_key):
    if choice_key == "NONE": return None, "None"
    all_tracks = get_library_tracks()
    if not all_tracks: return None, "None"
    if choice_key == "AUTO":
        target_prefix = SUBTITLE_ARCHETYPES.get(archetype_key, {}).get("prefix", "gold_")
        matched = [f for f in all_tracks if f.lower().startswith(target_prefix)]
        chosen_file = random.choice(matched if matched else all_tracks)
        return os.path.join(MUSIC_DIR, chosen_file), chosen_file
    if choice_key in all_tracks:
        return os.path.join(MUSIC_DIR, choice_key), choice_key
    return None, "None"

def to_unicode_bold(text):
    res = []
    for char in text:
        if "A" <= char <= "Z": res.append(chr(0x1D5D4 + ord(char) - ord("A")))
        elif "a" <= char <= "z": res.append(chr(0x1D5EE + ord(char) - ord("a")))
        elif "0" <= char <= "9": res.append(chr(0x1D7EC + ord(char) - ord("0")))
        else: res.append(char)
    return "".join(res)

# ---------------------------------------------------------
# 3. 25 HIGH-RETENTION THEMES (45-52 WORDS / ~18-20s + MEN 35-65+)
# ---------------------------------------------------------
THEMES_DATABASE = [
    # Playlist 1: The art of moving in silence (stoic mindset)
    {
        "id": "SILENT_EXIT",
        "pl": "The art of moving in silence (stoic mindset)",
        "p": "Emotional Immunity",
        "t": "The Silent Exit",
        "prem": "Never announce when you cut someone off. Withdrawing your presence without conflict strips away their leverage.",
        "h": "NEVER ANNOUNCE YOUR EXIT",
        "badge": "SILENT SOVEREIGNTY",
        "s_tight": "Never announce your exit. When disrespect enters your circle, explaining yourself only hands your adversary a target. Close the gate without a sound. Your presence was a privilege they failed to honor, not a lifelong debt. Walk forward in quiet command, and remember that true strength means you—",
        "q_open": "What boundary took you the longest to enforce without explaining yourself?",
        "a": "GLACIAL_ICE",
        "m": ["Heavy bronze portal latch locking into dark stone", "Single fraying linen cord burning cleanly through over a flame", "Solitary timber skiff drifting silently into dense lake mist"]
    },
    {
        "id": "WEAPON_INDIFFERENCE",
        "pl": "The art of moving in silence (stoic mindset)",
        "p": "Emotional Immunity",
        "t": "Weaponized Indifference",
        "prem": "If their disrespect triggers your anger, they own you. Cold composure strips away their control.",
        "h": "YOUR REACTION GIVES THEM POWER",
        "badge": "MASTER YOUR TEMPER",
        "s_tight": "Your reaction gives them power. The moment an insult pulls you out of character, a stranger becomes your master. Watch closely: calm silence forces them to choke on their own poison. Guard your composure like a fortress wall, and never forget that real authority begins when you—",
        "q_open": "How do you stop yourself from reacting when someone tries to provoke you?",
        "a": "GLACIAL_ICE",
        "m": ["Monolithic basalt cliff unmoved against crashing storm waves", "Torrential rain pouring down a marble statue without leaving a mark", "Glowing ember dropping onto cold slate and extinguishing to ash"]
    },
    {
        "id": "QUIET_EXECUTION",
        "pl": "The art of moving in silence (stoic mindset)",
        "p": "Relentless Focus",
        "t": "Quiet Execution",
        "prem": "A falling tree makes thunder, yet an entire forest grows in total silence. Build your roots unseen.",
        "h": "THE NOISE IS NOT THE PROOF",
        "badge": "BUILD IN SILENCE",
        "s_tight": "The noise is not the proof. A falling tree crashes with thunder, yet an entire forest grows in complete silence. Stop broadcasting your plans for cheap applause. Let others talk while you lay stone upon stone in the dark, knowing that real power is built when you—",
        "q_open": "What are you quietly building right now without telling anyone?",
        "a": "IMPERIAL_GOLD",
        "m": ["Deep underground oak roots splitting granite bedrock in total darkness", "Heavy blacksmith hammer shaping glowing steel on a dark anvil", "Stonemason chisel carving deep Roman numerals into solid granite"]
    },
    {
        "id": "TWO_ARROWS",
        "pl": "The art of moving in silence (stoic mindset)",
        "p": "Radical Acceptance",
        "t": "The Parable of Two Arrows",
        "prem": "Fate shoots the first arrow; your own mind drives the second arrow into your chest by replaying the wound.",
        "h": "DROP THE SECOND ARROW",
        "badge": "ANCIENT PARABLE",
        "s_tight": "Drop the second arrow. When someone betrays or insults you, fate strikes the first wound—and it is out of your hands. Yet replaying that moment for three sleepless nights drives a second blade into your own chest. Absorb the strike, release the poison, and remember why you—",
        "q_open": "What is one setback or insult you finally learned to stop replaying?",
        "a": "IMPERIAL_GOLD",
        "m": ["Bronze arrow deflecting cleanly off a heavy iron shield", "Troubled pool of dark water settling into a still crystal mirror", "Morning mist dissolving off ancient stone arches under warm sunlight"]
    },
    {
        "id": "SOLITUDE_ADVANTAGE",
        "pl": "The art of moving in silence (stoic mindset)",
        "p": "Relentless Focus",
        "t": "The Solitude Advantage",
        "prem": "A man who cannot sit quietly alone is an easy target for anyone promising distraction.",
        "h": "LEARN TO SIT IN SILENCE",
        "badge": "INNER CITADEL",
        "s_tight": "Learn to sit in silence. A man who cannot endure an hour alone with his own thoughts is easily manipulated by anyone offering noise. Step away from the crowd, sharpen your judgment in quiet hours, and stand firm—because unshakeable clarity only arrives when you—",
        "q_open": "How do you protect quiet time for yourself during a demanding week?",
        "a": "IMPERIAL_GOLD",
        "m": ["Single stone watchtower standing resolute above a sea of mountain fog", "Lone golden eagle gliding motionless on thermal winds above clouds", "Solitary stone lighthouse holding a steady beam through night waves"]
    },

    # Playlist 2: Mastering human nature and fake friends ancient parables
    {
        "id": "THREE_TYPES_PEOPLE",
        "pl": "Mastering human nature and fake friends ancient parables",
        "p": "Emotional Immunity",
        "t": "Never Blame People",
        "prem": "Good people bring happiness, difficult people bring experience, and the worst people leave lessons forever.",
        "h": "NEVER BLAME PEOPLE IN LIFE",
        "badge": "HUMAN NATURE LAW",
        "s_tight": "Never blame people in life. Good people bring happiness, difficult people bring experience, and the worst people leave lessons that sharpen your discernment forever. Every betrayal simply reveals who cannot walk into your next chapter. Extract the wisdom, tighten your standards, and understand why you—",
        "q_open": "Did your sharpest discernment come from an easy season or a hard betrayal?",
        "a": "GLACIAL_ICE",
        "m": ["Solid bronze compass needle locking onto true North in gale winds", "Refining crucible separating pure gold from dark slag", "Weathered antique theater mask cracking open on wet cobblestones"]
    },
    {
        "id": "UNRETURNED_LOYALTY",
        "pl": "Mastering human nature and fake friends ancient parables",
        "p": "Emotional Immunity",
        "t": "Unreturned Loyalty",
        "prem": "Blind loyalty to people who only call when they need a favor is self-betrayal. Close the vault.",
        "h": "STOP BLEEDING FOR USERS",
        "badge": "LOYALTY RULE",
        "s_tight": "Stop bleeding for users. Notice who only remembers your number when their roof is leaking, yet vanishes the moment you need support. Loyalty without reciprocity is slow self-destruction. Close the vault quietly, reserve your strength for those who show up, and remember that you—",
        "q_open": "What is the clearest sign that someone only values your usefulness?",
        "a": "FORGE_AMBER",
        "m": ["Heavy iron vault door swinging shut on oiled hinges", "Cracked clay water vessel draining into barren desert sand", "Sharp pruning sickle cleanly cutting a dead vine from an olive branch"]
    },
    {
        "id": "GOSSIP_STARVE",
        "pl": "Mastering human nature and fake friends ancient parables",
        "p": "Emotional Immunity",
        "t": "Gossip Starvation",
        "prem": "Whoever brings you gossip about others will carry your name to strangers tomorrow.",
        "h": "NEVER FEED SMALL MINDS",
        "badge": "DISCERNMENT",
        "s_tight": "Never feed small minds. Anyone eager to whisper another man's secrets at your table will sell your reputation the moment you leave the room. Starve rumors with cold silence, guard your private affairs, and keep your circle clean—because real respect is earned when you—",
        "q_open": "How do you shut down gossip at work or in your circle without drama?",
        "a": "GLACIAL_ICE",
        "m": ["Dark iron snuffer descending over a guttering candle flame", "Deep stone cistern swallowing a pebble without producing an echo", "Heavy oak door bolting shut from the inside"]
    },
    {
        "id": "COST_LIKABLE",
        "pl": "Mastering human nature and fake friends ancient parables",
        "p": "Emotional Immunity",
        "t": "The Cost of Being Likable",
        "prem": "Trying to please everyone is not kindness; it is fear of conflict. Respect matters more than approval.",
        "h": "STOP TRYING TO BE LIKED",
        "badge": "SELF-RESPECT",
        "s_tight": "Stop trying to be liked. Bending your principles to keep every room comfortable does not earn loyalty—it invites disrespect. Men of character choose integrity over popularity every single time. Stand by your word even when you stand alone, and remember that real freedom starts when you—",
        "q_open": "When did saying 'no' earn you more respect than saying 'yes'?",
        "a": "FORGE_AMBER",
        "m": ["Jagged granite headland breaking crashing ocean waves without yielding", "Brittle dried clay seal crumbling under thumb pressure", "Ancient judge stone bench standing empty and resolute under open skies"]
    },

    # Playlist 3: Financial Sovereignty and Relentless Discipline
    {
        "id": "SAVING_IS_CONTROL",
        "pl": "Financial Sovereignty and Relentless Discipline",
        "p": "Financial Sovereignty",
        "t": "Saving Is Control",
        "prem": "You do not feel reckless spending on a sunny day; you feel it when life tests your household.",
        "h": "SAVING IS NOT FEAR. IT IS CONTROL.",
        "badge": "FINANCIAL SOVEREIGNTY",
        "s_tight": "Saving is not fear; it is control. You never feel the cost of impulse spending on a sunny afternoon—you feel it when an emergency tests your household. Every dollar you refuse to waste on empty status buys your freedom to walk away. Build your reserve, and remember—",
        "q_open": "What is one financial rule you wish you had followed in your twenties?",
        "a": "IMPERIAL_GOLD",
        "m": ["Heavy iron-bound oak chest locking securely by warm lantern light", "Balance scale holding a single gold bar steady against heaps of straw", "Fine golden sand measuring time inside an ancient brass hourglass"]
    },
    {
        "id": "BUY_WHAT_YOU_DONT_NEED",
        "pl": "Financial Sovereignty and Relentless Discipline",
        "p": "Financial Sovereignty",
        "t": "The Trap of Empty Status",
        "prem": "He who buys luxuries to impress strangers will soon sell what he truly needs.",
        "h": "DO NOT GO BROKE LOOKING RICH",
        "badge": "WEALTH DISCIPLINE",
        "s_tight": "Do not go broke looking rich. Buying luxuries to impress people who would never help your family in a crisis is quiet slavery. True wealth is silent—it is peace of mind, zero debt, and owning your time. Master your appetites today, or you will find that you—",
        "q_open": "What purchase did you skip that ended up giving you far more peace of mind?",
        "a": "FORGE_AMBER",
        "m": ["Heavy broken iron shackles lying in dust beside an open cell gate", "Simple earthenware cup filled with cool clear mountain well water", "Antique gold coin resting untouched on dark slate"]
    },
    {
        "id": "SUNK_COST_TRAP",
        "pl": "Financial Sovereignty and Relentless Discipline",
        "p": "Relentless Focus",
        "t": "The Sunk Cost Trap",
        "prem": "Spending years on a bad investment or dead obligation does not mean you owe it your future.",
        "h": "STOP FEEDING DEAD DREAMS",
        "badge": "STRATEGIC CUT",
        "s_tight": "Stop feeding dead dreams. Just because you spent years pouring time or money into a mistake does not mean you owe it your future. Wise men cut their losses early and redeploy their strength where it compounds. Sever the anchor, move forward cleanly, and remember—",
        "q_open": "What is the hardest habit, deal, or commitment you ever had to walk away from?",
        "a": "FORGE_AMBER",
        "m": ["Sharp pruning sickle cleanly slicing a taut anchor rope under tension", "Antique weighing scale dumping heavy slag to return to level balance", "Heavy dry branch snapping off an ancient oak in storm winds"]
    },
    {
        "id": "ACTION_CURES_DOUBT",
        "pl": "Financial Sovereignty and Relentless Discipline",
        "p": "Relentless Focus",
        "t": "Discipline Over Moods",
        "prem": "Motivation is a fair-weather friend. Discipline is executing your duty when emotions protest.",
        "h": "ACTION CURES SELF-PITY",
        "badge": "IRON DISCIPLINE",
        "s_tight": "Action cures self-pity. Waiting to feel inspired before doing hard work is a trap that steals decades. Fleeting moods abandon you the moment pressure rises, but iron discipline carries you through storms. Honor your daily standard without excuses, and never forget that you—",
        "q_open": "What daily non-negotiable keeps you grounded when motivation disappears?",
        "a": "FORGE_AMBER",
        "m": ["Heavy waterwheel turning relentlessly against turbulent mountain currents", "Flint and steel striking violently to ignite a bright spark in darkness", "Team of draft oxen pulling a heavy plow through frost-hardened soil"]
    },

    # Playlist 4: Father to Son: Ancient Legacy Lessons
    {
        "id": "SON_BUILD_CHARACTER",
        "pl": "Father to Son: Ancient Legacy Lessons",
        "p": "Legacy Counsel",
        "t": "Son, Learn This Early",
        "prem": "Success is not luck; it is built through discipline, skill, and self-command no one can strip away.",
        "h": "SON, IF YOU WANT TO SUCCEED",
        "badge": "FATHER TO SON",
        "s_tight": "Son, if you want to succeed, learn this early. Luck changes with the weather, but skill, integrity, and self-command remain yours when every title is stripped away. Master a craft, keep your word, and control your temper. Build your character daily, because the man you become means you—",
        "q_open": "What is the single best lesson your father or an older mentor ever taught you?",
        "a": "IMPERIAL_GOLD",
        "m": ["Master craftsman hands guiding an apprentice over wooden drafting plans", "Glowing iron blade being tempered in cold water inside a stone forge", "Ancient stone archway standing intact across centuries of weather"]
    },
    {
        "id": "KEEP_YOUR_WORD",
        "pl": "Father to Son: Ancient Legacy Lessons",
        "p": "Legacy Counsel",
        "t": "A Man's Word Is His Bond",
        "prem": "In a world of cheap excuses, a man who keeps quiet promises commands instant authority.",
        "h": "LET YOUR WORD BE IRON",
        "badge": "LEGACY PRINCIPLE",
        "s_tight": "Let your word be iron. Most men promise loudly when it is easy and vanish when it costs them comfort. If you commit, deliver—even when nobody is checking. Over years, that quiet reliability becomes an unbreakable reputation. Guard your name fiercely, and remember that you—",
        "q_open": "Who is someone in your life whose word you trust without needing a contract?",
        "a": "IMPERIAL_GOLD",
        "m": ["Deep subterranean bedrock supporting an entire stone citadel", "Heavy iron anchor resting steadily on the ocean floor", "Carved stone seal pressed cleanly into warm crimson wax"]
    },
    {
        "id": "CHOOSE_YOUR_TABLE",
        "pl": "Father to Son: Ancient Legacy Lessons",
        "p": "Legacy Counsel",
        "t": "Guard Who Sits at Your Table",
        "prem": "Your standards are quietly shaped by the five voices you tolerate closest to your life.",
        "h": "CHOOSE YOUR CIRCLE WISELY",
        "badge": "MENTORSHIP",
        "s_tight": "Choose your circle wisely. Over five years, you absorb the habits, excuses, and standards of the people closest to your table. Step back from chronic complainers and walk with those who value duty, honesty, and growth. Guard your environment, because your future depends on how you—",
        "q_open": "How has changing your inner circle changed your mindset over the years?",
        "a": "GLACIAL_ICE",
        "m": ["Two armored commanders standing beside a mountain watchtower at dawn", "Sundial tracking the sun steadily above passing clouds", "Craftsman magnifying lens focusing strictly on fine gold engraving"]
    },

    # Playlist 5: Aging Well: Habits for Mind and Body
    {
        "id": "STRENGTH_AFTER_40",
        "pl": "Aging Well: Habits for Mind and Body",
        "p": "Longevity & Vitality",
        "t": "Protect Your Strength for Old Age",
        "prem": "Your later years deserve strength, clarity, and independence—not regret over neglected habits.",
        "h": "PROTECT YOUR BODY FOR LATER YEARS",
        "badge": "AGING WELL",
        "s_tight": "Protect your body for later years. Every walk you take, every clean meal you choose, and every hour of deep sleep is an investment in your independence at seventy and eighty. Do not trade your future mobility for today's laziness. Train your body with respect, and remember—",
        "q_open": "Which daily physical habit has made the biggest difference in your energy?",
        "a": "IMPERIAL_GOLD",
        "m": ["Mountain pine tree growing dense and unshakeable in freezing winds", "Clear mountain spring water pouring over smooth granite stones", "Weathered elder craftsman carving timber steadily in morning sunlight"]
    },
    {
        "id": "STOP_CARRYING_BITTERNESS",
        "pl": "Aging Well: Habits for Mind and Body",
        "p": "Longevity & Vitality",
        "t": "Resentment Ages You Faster",
        "prem": "Carrying bitterness for people who have already forgotten your name poisons your health and peace.",
        "h": "GUARD YOUR PEACE AS YOU AGE",
        "badge": "PEACE AFTER 40",
        "s_tight": "Guard your peace as you age. Nothing wears down a strong man faster than carrying resentment for people who no longer deserve space in his mind. After forty, protect your quiet mornings, forgive for your own freedom, and refuse pointless arguments—so you can live with clarity when you—",
        "q_open": "What is one thing you have completely stopped worrying about as you got older?",
        "a": "GLACIAL_ICE",
        "m": ["Boiling water in a bronze cauldron cooling down to smooth stillness", "Wild brushfire hitting a wide stone trench and running out of fuel", "Constellations revolving calmly in clear dark night skies over peaks"]
    },
    {
        "id": "MEMENTO_MORI_TIME",
        "pl": "Aging Well: Habits for Mind and Body",
        "p": "Radical Acceptance",
        "t": "Value What Remains",
        "prem": "You have already lived part of your life. Take what remains and live it with deliberate purpose.",
        "h": "TAKE WHAT IS LEFT AND LIVE WELL",
        "badge": "MARCUS AURELIUS",
        "s_tight": "Take what is left and live well. Stop treating your remaining years as if you have a thousand summers in reserve. Drop petty grudges, spend real time with your family, and focus only on work that matters. Time is your only non-renewable asset, so remember why you—",
        "q_open": "If you could give your younger self one reminder about time, what would it be?",
        "a": "FORGE_AMBER",
        "m": ["Shadow lengthening across Roman stone numerals on a sundial face", "Single dried autumn leaf detaching and drifting on a brisk wind", "Ancient Roman stone columns standing tranquil against centuries of weather"]
    }
]

DIVERSE_ARCHETYPES = [
    "An authentic mature Roman centurion, age 45, short military crop, clean-shaven with subtle facial scar, wearing polished dark iron shoulder plates over a crimson tunic. Strictly two arms only, flawless human anatomy.",
    "An elder master mentor, age 60, silver-streaked beard and calm authoritative eyes, seated across a low stone table from a young apprentice in a sunlit courtyard. Strictly two arms per person, flawless human anatomy.",
    "A disciplined medieval merchant, age 45, neatly trimmed short beard, short dark hair, wearing a heavy dark wool and leather cloak, inspecting an iron-bound ledger chest by warm lantern light. Strictly two arms only, flawless human anatomy.",
    "A weathered seasoned craftsman, age 52, silver-gray short beard, strong forearms, calm eyes, walking along a misty alpine granite ridge at sunrise in a dark wool tunic. Strictly two arms only, flawless human anatomy.",
    "An ancient Eastern scholar, age 50, calm penetrating eyes, fine dark silk robes, hair tied in a clean topknot, holding a bamboo writing brush. Strictly two arms only, flawless human anatomy.",
    "A hooded desert ascetic, age 48, sun-bronzed skin, short dark beard, piercing eyes, wrapped in rugged linen travel cloaks against windblown dust. Strictly two arms only, flawless human anatomy.",
    "A focused medieval blacksmith, age 42, soot-dusted cheeks, short dark hair, clean-shaven, rolled leather sleeves showing muscular forearms at an anvil. Strictly two arms only, flawless human anatomy."
]

SETTINGS_MATRIX = [
    {"n": "The Ancient Citadel Colonnades", "d": "Within towering monolithic ancient stone colonnades and rain-slicked courtyards with bronze braziers casting dramatic shadows."},
    {"n": "The Windswept Coastal Cliffs", "d": "Atop high windswept coastal cliffs overlooking turbulent dark ocean waves crashing against jagged basalt rocks in atmospheric fog."},
    {"n": "The Secluded Stone Workshop", "d": "Inside a secluded ancient stone workshop with drafting parchment, beeswax candles, deep shadows, and glowing forge embers."},
    {"n": "The Rugged Mountain Summit", "d": "Traversing a barren rocky mountain pass under cold dramatic grey skies and swirling morning mist beside weathered stone shrines."},
    {"n": "The Subterranean Torchlit Vault", "d": "Inside an ancient subterranean granite archive illuminated by burning torchlight and flickering oil lamps."},
    {"n": "The Sunlit Alpine Ridge", "d": "Along a high rocky granite ridge at sunrise with golden rays breaking through cool morning mist."}
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
    
    new_entry = [
        row_data.get("videoId", next_id),
        row_data.get("targetDate", ""),
        row_data.get("slot", ""),
        row_data.get("ytStatus", "Ready in Drive"),
        row_data.get("metaStatus", "Ready in Drive"),
        row_data.get("playlist", ""),
        row_data.get("titleConcept", ""),
        row_data.get("hookBanner", ""),
        row_data.get("driveFolder", ""),
        row_data.get("videoLink", ""),
        row_data.get("thumbLink", ""),
        row_data.get("ytTitle", ""),
        row_data.get("ytDesc", ""),
        row_data.get("ytTags", ""),
        row_data.get("ytPinned", ""),
        row_data.get("metaCaption", ""),
        row_data.get("metaComment", ""),
        row_data.get("directorFx", ""),
        row_data.get("notes", "Staged in Drive")
    ]
    ws.append(new_entry)
    wb.save(EXCEL_TRACKER_PATH)
    return True

# ---------------------------------------------------------
# 6. CACHED TURBO CLIENT & RESILIENT VOICE SYNTHESIZER
# ---------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_fast_gemini_client(clean_k):
    try:
        return genai.Client(
            api_key=clean_k,
            http_options=types.HttpOptions(timeout=15000)
        )
    except Exception:
        return genai.Client(api_key=clean_k)

def synthesize_with_gemini_audio(api_key, text, audio_path, voice_name="Charon"):
    clean_k = api_key.strip().strip('"').strip("'")
    if not clean_k: return False, None
    client = get_fast_gemini_client(clean_k)
    target_voice = "Charon" if "Charon" in voice_name else "Fenrir"
    for m in ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]:
        try:
            res = client.models.generate_content(
                model=m,
                contents=text,
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
                            label_m = "3.8 Lite" if "lite" in m else "3.8 Flash"
                            return True, f"Gemini {label_m} ({target_voice} US Male)"
        except Exception:
            continue
    return False, None

async def synthesize_speech_timed(text, audio_path, primary_voice="Gemini-Charon", api_key="", use_gemini_tts=True):
    if api_key and use_gemini_tts and "Gemini" in primary_voice:
        ok, v_desc = synthesize_with_gemini_audio(api_key, text, audio_path, voice_name=primary_voice)
        if ok: return [], v_desc
    try:
        comm = edge_tts.Communicate(text, voice="en-US-ChristopherNeural", rate="+8%", pitch="+0Hz")
        timings = []
        with open(audio_path, "wb") as f:
            async for chunk in comm.stream():
                if chunk["type"] == "audio": f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    st_s = chunk["offset"] / 10_000_000.0
                    dur_s = chunk["duration"] / 10_000_000.0
                    timings.append({"word": chunk.get("text", ""), "start": round(st_s, 3), "end": round(st_s + dur_s, 3)})
        if os.path.exists(audio_path) and os.path.getsize(audio_path) > 6000:
            return timings, "Christopher (US Male Word-Sync)"
    except Exception: pass
    cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '18.5', '-c:a', 'libmp3lame', audio_path]
    subprocess.run(cmd, capture_output=True)
    return [], "Ambient Timing Bed (Upload Ready)"

def build_ass_subtitles(timed_words, script_text, ass_path, total_dur, arch_key="IMPERIAL_GOLD"):
    color = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])["ass_primary"]
    events = []
    if timed_words and len(timed_words) >= 5:
        clean_words = []
        for tw in timed_words:
            raw_w = tw['word'].replace("—", " ").replace("–", " ").replace("-", " ")
            w_txt = re.sub(r"[^\w\s',.!?]", "", raw_w).upper().strip()
            if w_txt:
                for sub_w in w_txt.split():
                    clean_words.append({'word': sub_w, 'start': tw['start'], 'end': tw['end']})
        chunk = []
        for i, tw in enumerate(clean_words):
            chunk.append(tw)
            is_punct = any(tw['word'].endswith(p) for p in ['.', '!', '?', ':', ';'])
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
        clean_script = script_text.replace("—", " ").replace("–", " ").replace("-", " ")
        tokens = clean_script.split()
        token_groups = [tokens[i:i + 3] for i in range(0, len(tokens), 3)]
        vocal_start = 0.35
        step = max(0.45, (total_dur - vocal_start - 0.35) / max(1, len(token_groups)))
        for idx, grp in enumerate(token_groups):
            st_t = vocal_start + (idx * step)
            en_t = min(total_dur, vocal_start + ((idx + 1) * step))
            raw_grp = " ".join(grp)
            txt = re.sub(r"[^\w\s',.!?]", "", raw_grp).upper().strip()
            if txt: events.append((st_t, en_t, txt))

    def fmt(s): return f"{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}"
    ass_doc = f"""[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,DejaVu Sans,76,{color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,50,50,420,1\n\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"""
    for st_t, en_t, txt in events: ass_doc += f"Dialogue: 0,{fmt(st_t)},{fmt(en_t)},Default,,0,0,0,,{txt}\n"
    with open(ass_path, "w", encoding="utf-8") as f: f.write(ass_doc)
    return events

# Draft vault loader & video persistence
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
# 7. ZERO-FAIL STOIC VAULT FALLBACK & TURBO GENERATOR (18-20s)
# ---------------------------------------------------------
def select_archetype_for_playlist(pl_name):
    pl_l = pl_name.lower()
    if "father" in pl_l or "legacy" in pl_l:
        return DIVERSE_ARCHETYPES[1]
    if "financial" in pl_l:
        return DIVERSE_ARCHETYPES[2]
    if "aging" in pl_l:
        return DIVERSE_ARCHETYPES[3]
    return random.choice(DIVERSE_ARCHETYPES)

def build_curated_stoic_package(t_obj, macro_c, sett_obj, style_key="PUNCH_FLASH"):
    hook = t_obj["h"]
    badge_txt = t_obj.get("badge", hook)
    premise = t_obj["prem"]
    style_meta = CINEMATOGRAPHY_MATRIX.get(style_key, CINEMATOGRAPHY_MATRIX["PUNCH_FLASH"])
    pl_name = t_obj.get("pl", "The art of moving in silence (stoic mindset)")
    q_open = t_obj.get("q_open", "What is one hard truth life taught you that changed how you handle pressure?")
    
    script = t_obj.get("s_tight") or (
        f"{hook.title()}. {premise} Most people waste years explaining themselves to rooms that never listen. "
        f"Quiet discipline requires no applause; it proves itself through consistent action when nobody is watching. "
        f"Guard your energy, honor your standards, and remember why you—"
    )
    
    char_desc = select_archetype_for_playlist(pl_name)

    return {
        "title_concept": t_obj["t"],
        "playlist": pl_name,
        "hook_banner": hook,
        "video_overlay_text": badge_txt,
        "subtitle_archetype": t_obj["a"],
        "director_style": style_key,
        "script": script,
        "scene1_prompt": f"[4-second vertical 9:16 cinematic video clip] Protagonist ({char_desc}) in {sett_obj['n'].lower()}. {style_meta['cam_s1']}. LENS: {style_meta['lens_s1']}. {style_meta['grade']}. Flawless anatomy, strictly two arms, photorealistic 8k.",
        "scene2_prompt": f"[4-second vertical 9:16 cinematic video clip] {macro_c}. {style_meta['cam_s2']}. LENS: {style_meta['lens_s2']}. {style_meta['grade']}. Photorealistic micro-details, extreme texture resolution.",
        "scene3_prompt": f"[4-second vertical 9:16 cinematic video clip] Protagonist ({char_desc}) traversing {sett_obj['n'].lower()}. {style_meta['cam_s3']}. LENS: {style_meta['lens_s3']}. {style_meta['grade']}. Realistic cloth physics, strictly two arms.",
        "scene4_prompt": f"[4-second vertical 9:16 cinematic video clip] Protagonist ({char_desc}) intense composure shot. {style_meta['cam_s4']}. LENS: {style_meta['lens_s4']}. {style_meta['grade']}. Piercing stoic resolve, flawless human face, identical character appearance to Scene 1.",
        "thumbnail_prompt": (
            f"Dramatic 9:16 vertical cinematic portrait of {char_desc} in {sett_obj['n'].lower()}, "
            f"intense steady gaze, cinematic volumetric lighting. Prominently centered in the upper-third (20% to 35% from the top margin, strictly above character's head) is massive, ultra-bold typography reading exactly: \"{hook}\". "
            f"The text is rendered in thick distressed sans-serif block lettering, high-contrast {'radiant imperial gold' if t_obj.get('a') == 'IMPERIAL_GOLD' else ('frost glacial cyan' if t_obj.get('a') == 'GLACIAL_ICE' else 'molten forge amber')} color with a dark ambient drop shadow for maximum legibility against atmospheric fog. "
            f"The typography does not obscure the character's face. Strictly NO text in the lower half of the frame. Flawless human anatomy, strictly two arms."
        ),
        "youtube_title": f"⚡ {hook.title()} 🏛️ #shorts #stoicism",
        "youtube_description": f"⚡ {hook}\n\n{premise}\n\n💭 {q_open}\n\n🏛️ Subscribe to {get_persistent_yt_handle()} for timeless clarity.\n\n#stoicism #lifelessons #discipline #echoesofwisdom #shorts",
        "youtube_tags": "stoicism, echoes of wisdom, life lessons, stoic mindset, discipline, self improvement, marcus aurelius, mental strength, mens wisdom, shorts",
        "youtube_pinned_comment": f"💭 {q_open}",
        "caption_hook": hook,
        "caption_lesson": premise,
        "reflection_question": q_open,
        "meta_hashtags": "#Stoicism #LifeLessons #Mindset #SelfRespect #Wisdom"
    }

def generate_video_package(raw_api_key, t_obj, macro_c, sett_obj, style_key="PUNCH_FLASH"):
    clean_key = raw_api_key.strip().strip('"').strip("'") if raw_api_key else ""
    clean_yt_handle = get_persistent_yt_handle()
    used_h = "\n".join([f"- {h}" for h in db.get("used_hooks", [])[-40:]]) or "None."
    style_meta = CINEMATOGRAPHY_MATRIX.get(style_key, CINEMATOGRAPHY_MATRIX["PUNCH_FLASH"])
    pl_name = t_obj.get("pl", "The art of moving in silence (stoic mindset)")
    char_desc = select_archetype_for_playlist(pl_name)
    
    prompt = (
        f"You are Executive Creative Director for 'Echoes of Wisdom' (9:16 vertical short-form reels).\n"
        f"CORE AUDIENCE: Men aged 35-65+ in the United States, UK, Canada, and Australia.\n"
        f"PLAYLIST: {pl_name} | THEME: {t_obj['t']}\nPREMISE: {t_obj['prem']}\nDEFAULT HOOK: {t_obj['h']}\n"
        f"MACRO METAPHOR (SCENE 2): {macro_c}\nENVIRONMENT: {sett_obj['d']}\n"
        f"DIRECTOR CINEMATOGRAPHY MATRIX INSTRUCTIONS:\n"
        f"- Scene 1 Camera & Lens: {style_meta['cam_s1']}. Lens: {style_meta['lens_s1']}.\n"
        f"- Scene 2 Camera & Lens: {style_meta['cam_s2']}. Lens: {style_meta['lens_s2']}.\n"
        f"- Scene 3 Camera & Lens: {style_meta['cam_s3']}. Lens: {style_meta['lens_s3']}.\n"
        f"- Scene 4 Camera & Lens: {style_meta['cam_s4']}. Lens: {style_meta['lens_s4']}.\n"
        f"- Color & Atmosphere: {style_meta['grade']}\n"
        f"FORBIDDEN HOOKS (DO NOT USE):\n{used_h}\n"
        f"CRITICAL RETENTION & ALGORITHM RULES:\n"
        f"1. STRICT SCRIPT LENGTH: Exactly 45 to 52 words total (engineered for an 18 to 20 second Reel so completion stays above 45%).\n"
        f"2. SECOND-4 PATTERN INTERRUPT: Sentence 1 is a 3-5 word hook. Sentence 2 MUST deliver an immediate psychological twist or vivid real-world contrast right at the 4-second mark so viewers do not swipe away at the first cut.\n"
        f"3. SEAMLESS LOOP: The final clause must flow grammatically back into Sentence 1.\n"
        f"4. ZERO ENGAGEMENT BAIT: Strictly NEVER use 'Drop 1 or 2', '1️⃣ vs 2️⃣', 'Comment YES', or numeric polls. 'reflection_question' and 'youtube_pinned_comment' MUST be authentic, open-ended questions inviting a real sentence from mature men.\n"
        f"5. Google Flow Character & Visual Continuity Rule: {char_desc} CRITICAL: Maintain the EXACT same character age, facial hair, hairstyle, and clothing across Scenes 1, 3, and 4 so the person never morphs into a different age or face.\n"
        f"6. Prompt Formatting: All 4 video prompts MUST start with '[4-second vertical 9:16 cinematic video clip]' and embed 0s-2s and 2s-4s camera kinetics, lens focal length, and lighting.\n"
        f"7. DYNAMIC OVERLAY VARIATION: 'video_overlay_text' (2-3 uppercase words) must be a thematic category pill distinct from 'hook_banner'.\n"
        f"8. THUMBNAIL TYPOGRAPHY MANDATE: 'thumbnail_prompt' MUST command bold typography reading exactly: 'typography reading exactly: \"[HOOK_BANNER]\"' in the upper third (20%-35% from top, above character's head), distressed sans-serif block lettering, high-contrast {('radiant imperial gold' if t_obj.get('a') == 'IMPERIAL_GOLD' else ('frost glacial cyan' if t_obj.get('a') == 'GLACIAL_ICE' else 'molten forge amber'))} color with dark drop shadow, clear of face, NO bottom text.\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        "{\n"
        '  "title_concept": "Short Concept Title",\n'
        f'  "playlist": "{pl_name}",\n'
        '  "hook_banner": "3-5 WORDS IN CAPS",\n'
        '  "video_overlay_text": "2-3 WORD PILL BADGE",\n'
        f'  "subtitle_archetype": "{t_obj["a"]}",\n'
        f'  "director_style": "{style_key}",\n'
        '  "script": "Tight 45-52 word script with second-4 twist and seamless loop.",\n'
        '  "scene1_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 1 protagonist with 0s-2s and 2s-4s camera kinetics, lens and lighting",\n'
        f'  "scene2_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 2 macro ({macro_c}) with intra-shot tilt/pan, lens and lighting",\n'
        '  "scene3_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 3 same protagonist action with tracking parallax, lens and lighting",\n'
        '  "scene4_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 4 same protagonist extreme resolve portrait with intra-shot glance and lighting",\n'
        '  "thumbnail_prompt": "High-contrast 9:16 vertical portrait with centered upper-third distressed bold typography reading: \\"[HOOK_BANNER]\\", color with dark drop shadow, clear of face, strictly no bottom text, strictly two arms",\n'
        '  "youtube_title": "⚡ Hook Title 🏛️ #shorts #stoicism",\n'
        f'  "youtube_description": "⚡ HOOK\\n\\nLesson text...\\n\\n💭 Open reflection question?\\n\\n🏛️ Subscribe to {clean_yt_handle}\\n\\n#stoicism #lifelessons #shorts",\n'
        '  "youtube_tags": "stoicism, echoes of wisdom, life lessons, stoic mindset, discipline, self improvement, marcus aurelius, mental strength, mens wisdom, shorts",\n'
        '  "youtube_pinned_comment": "💭 Open-ended reflection question for viewers?",\n'
        '  "caption_hook": "PUNCHY 4-6 WORD HOOK",\n'
        '  "caption_lesson": "Two crisp sentences expanding the insight.",\n'
        '  "reflection_question": "Open-ended question inviting a real sentence in comments?",\n'
        '  "meta_hashtags": "#Stoicism #LifeLessons #Mindset #Wisdom #PersonalGrowth"\n'
        "}"
    )

    if clean_key:
        try:
            client = get_fast_gemini_client(clean_key)
            models = ["gemini-3.8-flash", "gemini-3.8-flash-lite"]
            for m in models:
                try:
                    try:
                        gen_cfg = types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.85,
                            max_output_tokens=1600,
                            thinking_config=types.ThinkingConfig(thinking_level="MINIMAL")
                        )
                    except Exception:
                        gen_cfg = types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.85,
                            max_output_tokens=1600
                        )
                    r = client.models.generate_content(
                        model=m,
                        contents=prompt,
                        config=gen_cfg
                    )
                    raw = r.text.strip()
                    match = re.search(r'\{.*\}', raw, re.DOTALL)
                    clean_json = match.group(0) if match else raw
                    parsed = json.loads(clean_json)
                    if isinstance(parsed, dict) and "script" in parsed:
                        tag_name = "Gemini 3.8 Flash-Lite (Fast)" if "lite" in m else "Gemini 3.8 Flash (Turbo)"
                        return parsed, tag_name
                except Exception:
                    continue
        except Exception:
            pass

    return build_curated_stoic_package(t_obj, macro_c, sett_obj, style_key), "Stoic Vault (18-20s Retention Mode)"

# ---------------------------------------------------------
# 8. TELEMETRY BAR & PUBLISHING SETTINGS
# ---------------------------------------------------------
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 600;">v8.1 // 18-20s RETENTION, CONTINUITY & DUAL-HANDLE ENGINE</span>
</div>
""", unsafe_allow_html=True)

recent_ids = db.get("used_theme_ids", [])[-14:]
fresh_count = len(THEMES_DATABASE) - len(set(recent_ids))
track_count = len(get_library_tracks())

st.markdown(f"""
<div style="margin-bottom: 14px;">
    <span class="badge badge-green">● TURBO ENGINE ONLINE</span>
    <span class="badge badge-purple">🎯 18-20s HIGH-COMPLETION</span>
    <span class="badge badge-blue">🛡️ NON-BAIT CAPTIONS</span>
    <span class="badge badge-amber">📅 {target_d} @ {target_t} IST ({target_s})</span>
</div>
""", unsafe_allow_html=True)

if "status_banner" in st.session_state:
    st.success(st.session_state.pop("status_banner"))

with st.expander("📅 PUBLISHING CADENCE & BATCH VAULT SETTINGS"):
    st.markdown("#### ⏰ Release Cadence (05:00 IST = Peak US Evening Window)")
    c1, c2 = st.columns(2)
    saved_d = datetime.strptime(db["last_scheduled_date"], "%Y-%m-%d").date() if db.get("last_scheduled_date") else datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    with c1:
        cd = st.date_input("Last Scheduled Date", value=saved_d)
        cs = st.selectbox("Last Slot", ["SLOT 1 (MORNING)", "SLOT 2 (EVENING)"], index=(0 if "SLOT 1" in str(db.get("last_scheduled_slot","")).upper() else 1))
    with c2:
        ct1 = st.time_input("Slot 1 (IST - Optimal 05:00)", value=dt_time(int(db.get("slot1_time","05:00").split(":")[0]), int(db.get("slot1_time","05:00").split(":")[1])))
        ct2 = st.time_input("Slot 2 (IST - Optimal 18:00)", value=dt_time(int(db.get("slot2_time","18:00").split(":")[0]), int(db.get("slot2_time","18:00").split(":")[1])))
    
    st.markdown("#### 📺 Active Channel Playlists (5 Men 35-65+ Pillars)")
    for pl_name in PLAYLIST_OPTIONS:
        st.markdown(f"- **{pl_name}**")

    if st.button("💾 Save Cadence Settings"):
        db.update({
            "last_scheduled_date": cd.strftime("%Y-%m-%d"), 
            "last_scheduled_slot": cs, 
            "slot1_time": ct1.strftime("%H:%M"), 
            "slot2_time": ct2.strftime("%H:%M")
        })
        save_db(db)
        nd, ns, nt = get_next_slot(db["last_scheduled_date"], db["last_scheduled_slot"])
        st.session_state["status_banner"] = f"Settings saved! Next slot: {nd} @ {nt} IST ({ns})"
        st.rerun()

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
    st.markdown("#### 📊 Optional: Google Sheets Webhook Sync")
    st.caption("Paste your Google Apps Script Web App URL below to auto-sync scheduled rows in real time.")
    gurl = st.text_input("Google Apps Script Web App URL", value=curr_gsheet_url, placeholder="https://script.google.com/macros/s/.../exec", key="user_sheet_url")
    if gurl:
        save_persistent_gsheet_url(gurl)
        st.caption("✓ Google Sheets live sync active")

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
# 9. WORKSPACE TABS
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["⚡ 1. SCRIPT & PROMPTS", "🎬 2. RENDER MASTER REEL", "📋 3. QUEUE LEDGER & TRACKER"])

# --- TAB 1: SCRIPT & GOOGLE FLOW PROMPTS ---
with tab1:
    vault_items = load_draft_vault()
    if vault_items:
        with st.expander(f"📦 RESTORE PREVIOUS DRAFT ({len(vault_items)} SAVED IN VAULT)", expanded=False):
            st.caption("Select any recently generated script below to restore it instantly into Tab 2.")
            vault_labels = [f"⚡ {v.get('pkg',{}).get('hook_banner', 'Untitled')} — {v.get('t_id','Theme')} ({v.get('date','')})" for v in vault_items]
            chosen_vault_idx = st.selectbox("Choose Draft to Restore", range(len(vault_items)), format_func=lambda i: vault_labels[i])
            if st.button("🔄 Restore Selected Draft", key="btn_restore_vault"):
                restored = vault_items[chosen_vault_idx]
                with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(restored, f, indent=2)
                st.session_state["active_video_pkg"] = restored
                st.session_state["rendered_director_style"] = restored.get("pkg", {}).get("director_style", "PUNCH_FLASH")
                st.success(f"✓ Restored '{restored.get('pkg',{}).get('hook_banner')}' into active memory!")
                st.rerun()

    with st.expander("📝 QUICK-PASTE SCRIPT RESTORE (FOR EXISTING CLIPS)", expanded=False):
        st.caption("Have clips and thumbnail ready? Paste your hook and 45-52 word script here to synthesize audio & subtitles in 2 seconds.")
        col_qp1, col_qp2 = st.columns([2, 1])
        with col_qp1:
            qp_hook = st.text_input("Hook Banner", value="NEVER ANNOUNCE YOUR EXIT", placeholder="e.g. SAVING IS NOT FEAR")
        with col_qp2:
            qp_pl = st.selectbox("Playlist", PLAYLIST_OPTIONS, index=0)
            
        qp_script = st.text_area(
            "Tight 18-20s Script (45-52 words)",
            value="Never announce your exit. When disrespect enters your circle, explaining yourself only hands your adversary a target. Close the gate without a sound. Your presence was a privilege they failed to honor, not a lifelong debt. Walk forward in quiet command, and remember that true strength means you—",
            height=95
        )
        if st.button("⚡ Restore Script & Generate Audio Bed", type="primary"):
            k = get_persistent_api_key()
            with st.spinner("⚡ Synthesizing audio narration bed & calibrating subtitles..."):
                t_obj_match = next((t for t in THEMES_DATABASE if t["h"].upper() == qp_hook.strip().upper()), THEMES_DATABASE[0])
                s_obj = SETTINGS_MATRIX[0]
                pkg = build_curated_stoic_package(t_obj_match, random.choice(t_obj_match["m"]), s_obj, "PUNCH_FLASH")
                clean_h = qp_hook.strip().upper()
                pkg["script"] = qp_script.strip()
                pkg["hook_banner"] = clean_h
                pkg["playlist"] = qp_pl
                timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k, use_gemini_tts=False))
                
                draft_data = {
                    "pkg": pkg,
                    "t_id": t_obj_match["id"],
                    "p": t_obj_match["p"],
                    "pl": qp_pl,
                    "m": t_obj_match["m"][0],
                    "s": s_obj["n"],
                    "audio": DRAFT_AUDIO_PATH,
                    "timings": timings,
                    "voice_used": v_name,
                    "engine_source": "Quick-Paste Vault Restore",
                    "date": target_d,
                    "slot": target_s,
                    "time": target_t
                }
                with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f:
                    json.dump(draft_data, f, indent=2)
                save_to_draft_vault(draft_data)
                st.session_state["active_video_pkg"] = draft_data
                st.session_state["rendered_director_style"] = "PUNCH_FLASH"
                st.success("✓ Script & Audio Bed restored! Head to Tab 2 to render.")
                st.rerun()

    st.markdown("---")
    st.markdown("### 🎲 Synthesize Fresh 18–20s Retention Package")
    
    chosen_pl_filter = st.selectbox(
        "Filter by Audience Pillar / Playlist (Men 35-65+)",
        ["ALL"] + PLAYLIST_OPTIONS,
        format_func=lambda x: "🎲 Smart Rotation Across All 5 Pillars" if x == "ALL" else f"📺 {x}"
    )

    filtered_themes = [t for t in THEMES_DATABASE if chosen_pl_filter == "ALL" or t.get("pl") == chosen_pl_filter]
    theme_opts = ["🎲 Smart AI Rotation (Cooldown-Protected)"] + filtered_themes
    chosen_theme = st.selectbox(
        "Core Topic",
        theme_opts,
        format_func=lambda x: "🎲 Smart AI Rotation" if isinstance(x, str) else f"{'⏳' if x['id'] in recent_ids else '✨'} {x['t']} ➔ [{x.get('pl','')[:24]}...]"
    )
    
    col_v1, col_v2, col_v3 = st.columns([1, 1, 1])
    with col_v1:
        chosen_setting = st.selectbox("Cinematic Setting", ["🎲 Random Environment"] + [s["n"] for s in SETTINGS_MATRIX])
    with col_v2:
        chosen_style_key = st.selectbox(
            "Cinematography Matrix", 
            ["🎲 Auto-Randomize Style"] + list(CINEMATOGRAPHY_MATRIX.keys()), 
            format_func=lambda k: "🎲 Auto-Randomize Style" if k.startswith("🎲") else CINEMATOGRAPHY_MATRIX[k]["label"]
        )
    with col_v3:
        chosen_arch = st.selectbox(
            "Subtitle Color", 
            ["🤖 Match Theme Archetype"] + list(SUBTITLE_ARCHETYPES.keys()), 
            format_func=lambda x: "🤖 Match Archetype" if x.startswith("🤖") else SUBTITLE_ARCHETYPES[x]["label"]
        )

    speed_mode = st.radio(
        "Generation Speed & Voice Mode",
        [
            "⚡ Ultra-Fast (~2-3s): Gemini 3.8 Script + Edge-TTS Word-Sync Audio",
            "🎙️ Studio Voice (~4-6s): Gemini 3.8 Script + Gemini 3.8 Lite TTS Audio"
        ],
        index=0,
        horizontal=False
    )

    if st.button("🚀 Synthesize Fresh 18-20s Reel Package", type="primary"):
        k = get_persistent_api_key()
        t_start = time.time()
        use_gem_tts = "Studio Voice" in speed_mode
        with st.status("⚡ Running Turbo 18-20s Retention Pipeline...", expanded=True) as status:
            st.write("1/2 Writing 45-52 word script with Second-4 pattern interrupt...")
            pool = [t for t in filtered_themes if t["id"] not in recent_ids] or filtered_themes
            t_obj = random.choice(pool) if isinstance(chosen_theme, str) else chosen_theme
            s_obj = random.choice(SETTINGS_MATRIX) if chosen_setting.startswith("🎲") else next(s for s in SETTINGS_MATRIX if s["n"] == chosen_setting)
            m_choice = random.choice(t_obj["m"])
            
            resolved_style = random.choice(list(CINEMATOGRAPHY_MATRIX.keys())) if chosen_style_key.startswith("🎲") else chosen_style_key
            
            pkg, engine_source = generate_video_package(k, t_obj, m_choice, s_obj, resolved_style)
            pkg["subtitle_archetype"] = chosen_arch if not chosen_arch.startswith("🤖") else t_obj["a"]
            pkg["playlist"] = t_obj.get("pl", "The art of moving in silence (stoic mindset)")
            pkg["director_style"] = resolved_style
            t_script = time.time() - t_start
            
            st.write(f"2/2 Synthesizing crisp narration audio ({t_script:.1f}s)...")
            timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k, use_gemini_tts=use_gem_tts))
            total_elapsed = time.time() - t_start
            status.update(label=f"✅ Package Ready in {total_elapsed:.1f}s!", state="complete", expanded=False)
            
            draft_data = {
                "pkg": pkg,
                "t_id": t_obj["id"],
                "p": t_obj["p"],
                "pl": pkg["playlist"],
                "m": m_choice,
                "s": s_obj["n"],
                "audio": DRAFT_AUDIO_PATH,
                "timings": timings,
                "voice_used": v_name,
                "engine_source": f"{engine_source} ({total_elapsed:.1f}s)",
                "date": target_d,
                "slot": target_s,
                "time": target_t
            }
            with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f: json.dump(draft_data, f, indent=2)
            save_to_draft_vault(draft_data)
            st.session_state["active_video_pkg"] = draft_data
            st.session_state["rendered_director_style"] = resolved_style
            st.session_state.pop("rendered_video_path", None)
            st.rerun()

    if "active_video_pkg" in st.session_state:
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data.get("pkg", {})
        active_director_style = pkg.get("director_style", "PUNCH_FLASH")
        word_cnt = len(pkg.get("script", "").split())
        est_sec = round(word_cnt / 2.65, 1)
        st.divider()
        st.subheader(f"📜 Concept: {pkg.get('title_concept', 'Stoic Reel')}")
        st.markdown(f"**Target Playlist:** `{pkg.get('playlist', '')}`")
        st.markdown(f"**Runtime Target:** `{word_cnt} words (~{est_sec}s)` &nbsp;|&nbsp; **Engine:** `{p_data.get('engine_source', 'Active')}`")
        st.markdown(f"**Palette:** {SUBTITLE_ARCHETYPES.get(pkg.get('subtitle_archetype', 'FORGE_AMBER'), SUBTITLE_ARCHETYPES['FORGE_AMBER'])['label']} &nbsp;|&nbsp; **Voice:** `{p_data.get('voice_used', 'Christopher')}`")
        st.info(
            f"🎯 **Thumbnail Hook:** `{pkg.get('hook_banner')}` &nbsp;|&nbsp; **Video Badge:** `{pkg.get('video_overlay_text', pkg.get('hook_banner'))}`\n\n"
            f"🗣️ **Script (~{est_sec}s):**\n\n*{pkg.get('script')}*\n\n"
            f"💬 **Non-Bait Discussion Question:** *{pkg.get('reflection_question', pkg.get('youtube_pinned_comment', ''))}*"
        )
        
        if os.path.exists(DRAFT_AUDIO_PATH):
            st.audio(DRAFT_AUDIO_PATH)

        custom_voice = st.file_uploader("Optional: Replace Narration with Own MP3 File", type=["mp3"])
        if custom_voice:
            with open(DRAFT_AUDIO_PATH, "wb") as f: f.write(custom_voice.read())
            p_data["timings"] = []
            st.success("Custom narration file loaded into vault!")
            st.rerun()
        
        st.markdown("### 📋 Copy Google Flow Prompts (Intra-Shot Moves & Lenses Embedded)")
        for i, (lbl, k) in enumerate([
            ("SCENE 1 (0-4s Hook - Intra-Shot Push/Tilt)", "scene1_prompt"), 
            ("SCENE 2 (4-8s Pattern Interrupt - Macro Probe/Whip)", "scene2_prompt"), 
            ("SCENE 3 (8-13s Action - Tracking Parallax Arc)", "scene3_prompt"), 
            ("SCENE 4 (13-19s Resolve - Portrait Lighting Shift)", "scene4_prompt"), 
            ("THUMBNAIL (9:16 - Embedded Typography)", "thumbnail_prompt")
        ]):
            st.text_area(lbl, pkg.get(k, ""), height=80)
            render_copy(f"pr_{i}", f"COPY {lbl}", pkg.get(k, ""))

        if st.button("🗑️ Discard Draft & Start Fresh"):
            if os.path.exists(DRAFT_JSON_PATH): os.remove(DRAFT_JSON_PATH)
            if os.path.exists(DRAFT_AUDIO_PATH): os.remove(DRAFT_AUDIO_PATH)
            st.session_state.pop("active_video_pkg", None)
            st.session_state.pop("rendered_video_path", None)
            st.rerun()

# --- TAB 2: COMPOSE & RENDER MASTER REEL ---
with tab2:
    st.markdown("### 📥 1. Upload Video Clips (Dynamic 2 to 10+ Clips)")
    uploaded_clips = st.file_uploader(
        "Drop clips (scene1.mp4, scene2.mp4, scene3.mp4, scene4.mp4)",
        type=["mp4", "mov"],
        accept_multiple_files=True
    )

    num_clips = len(uploaded_clips) if uploaded_clips else 0
    if uploaded_clips:
        uploaded_clips = sorted(uploaded_clips, key=lambda x: x.name)
        st.markdown(f'<div style="color: #34D399; font-size: 13px; font-weight: 600; margin-bottom: 8px;">📁 Files loaded: {num_clips} clips ready — {", ".join([c.name for c in uploaded_clips])}</div>', unsafe_allow_html=True)

    st.markdown("### 🎬 2. Post-Render Polish & Visual Overlay Styling")
    active_style_key = st.session_state.get("rendered_director_style", "PUNCH_FLASH")
    
    col_fx1, col_fx2 = st.columns(2)
    with col_fx1:
        chosen_director_fx = st.selectbox(
            "Transition Burst Archetype",
            list(CINEMATOGRAPHY_MATRIX.keys()),
            format_func=lambda x: CINEMATOGRAPHY_MATRIX[x]["label"],
            index=list(CINEMATOGRAPHY_MATRIX.keys()).index(active_style_key) if active_style_key in CINEMATOGRAPHY_MATRIX else 0,
            help="Defines the transition flashes and grading mood for video cuts."
        )
    with col_fx2:
        flash_intensity = st.slider(
            "CutCap Transition Flash Length",
            min_value=0.0, max_value=0.25, value=0.12, step=0.02,
            help="Duration of the shutter flash between scene cuts."
        )

    col_ov1, col_ov2 = st.columns(2)
    with col_ov1:
        overlay_style = st.selectbox(
            "On-Screen Badge Style",
            ["Floating Shadow (Clean)", "Minimalist Top Pill", "Subtle Border Frame", "Glass Box (Classic)"],
            index=0,
            help="Select how the opening category badge is displayed on screen."
        )
    with col_ov2:
        custom_overlay_txt = st.text_input(
            "Video Category Pill Text (Distinct from Thumbnail)",
            value=st.session_state.get("active_video_pkg", {}).get("pkg", {}).get("video_overlay_text", ""),
            placeholder="e.g. SILENT SOVEREIGNTY"
        )

    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        apply_digital_zoom = st.checkbox(
            "🔬 Apply Digital FFmpeg Zoom",
            value=False,
            help="Leave unchecked when Google Flow clips already contain 3D camera motion."
        )
    with col_opt2:
        enable_vignette = st.checkbox("🌑 Optical Vignette", value=True, help="Darkens outer corners to frame the subject.")
    with col_opt3:
        enable_film_grain = st.checkbox("🎞️ 35mm Film Grain", value=True, help="Adds subtle 35mm analog grain.")

    st.markdown("### 🎵 3. Dynamic Background Audio (EBU R128 + Auto-Ducking)")
    current_arch_key = st.session_state.get("active_video_pkg", {}).get("pkg", {}).get("subtitle_archetype", "FORGE_AMBER")
    
    avail_tracks = get_library_tracks()
    bgm_options = {
        "AUTO": f"🤖 Auto-Match Theme ({SUBTITLE_ARCHETYPES.get(current_arch_key, {})['label']})",
        "NONE": "🔇 Narration Only (Silent background)",
        "UPLOAD": "📁 Upload New MP3 File"
    }
    for t in avail_tracks: bgm_options[t] = f"🎵 {t}"

    col_bg1, col_bg2 = st.columns([3, 2])
    with col_bg1:
        chosen_bgm_mode = st.selectbox("Background Music Source", list(bgm_options.keys()), format_func=lambda x: bgm_options[x])
    with col_bg2:
        bgm_vol_level = st.slider("Music Bed Loudness", min_value=-36, max_value=-22, value=-28, step=1, help="-28 LUFS broadcast standard.")

    custom_music_file = None
    if chosen_bgm_mode == "UPLOAD" or len(avail_tracks) == 0:
        custom_music_file = st.file_uploader("Upload / Direct-Add MP3 Track to Vault", type=["mp3"])
        if custom_music_file:
            save_dest = os.path.join(MUSIC_DIR, custom_music_file.name)
            with open(save_dest, "wb") as f: f.write(custom_music_file.read())
            st.success(f"✓ Saved '{custom_music_file.name}' to music library!")
            st.rerun()

    res_path, res_name = resolve_background_track(chosen_bgm_mode, current_arch_key)
    if res_path and os.path.exists(res_path):
        st.markdown(f'<div style="color: #34D399; font-size: 12px; font-weight: 600; margin-top: -6px; margin-bottom: 8px;">✓ Active Background Track: {res_name}</div>', unsafe_allow_html=True)

    st.markdown("### 🖼️ 4. Thumbnail Safe-Zone Engine (Upper 20%-45% Placement)")
    thumb = st.file_uploader("Upload raw Google Flow thumbnail", type=["png", "jpg", "jpeg", "webp"])
    if thumb:
        try:
            im = Image.open(thumb).convert("RGB")
            w, h = im.size
            crop_mode = st.radio(
                "Watermark Removal Depth",
                ["Standard (Single Watermark - 6.5% Bottom Crop)", "Deep (Expanded Watermark - 12.5% Bottom Crop)"],
                horizontal=True
            )
            pct = 0.125 if "Deep" in crop_mode else 0.065
            crop_h = h - int(h * pct)
            target_aspect = 9.0 / 16.0
            crop_w = int(crop_h * target_aspect)
            margin_x = max(0, (w - crop_w) // 2)
            
            clean_im = im.crop((margin_x, 0, margin_x + crop_w, crop_h)).resize((1080, 1920), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            clean_im.save(buf, format="PNG", quality=98)
            st.image(clean_im, caption=f"✓ Clean 9:16 Master ({crop_mode.split()[0]} Crop Applied)", use_container_width=True)
            
            cur_pkg = st.session_state.get("active_video_pkg", {}).get("pkg", {})
            cur_slug = re.sub(r'[^a-zA-Z0-9]+', '_', cur_pkg.get('hook_banner', 'reel')).strip('_').lower()
            thumb_save_name = f"{target_d.replace('-','')}_{cur_slug}_thumb.png"
            st.download_button(f"💾 Download Cleaned Thumbnail ({thumb_save_name})", buf.getvalue(), thumb_save_name, "image/png")
        except Exception as e: 
            st.warning(f"Could not crop thumbnail: {e}")

    if st.button("🎬 Render Master 9:16 Vertical Reel", type="primary"):
        if "active_video_pkg" not in st.session_state:
            st.error("No active draft loaded in Tab 1. Synthesize or restore a draft in Tab 1 first!")
        elif not uploaded_clips or num_clips < 2:
            st.error(f"Please upload at least 2 video clips. (Currently loaded: {num_clips})")
        else:
            with st.spinner(f"⚡ Rendering high-retention master reel with pure optical crop across {num_clips} clips..."):
                p_data = st.session_state["active_video_pkg"]
                pkg = p_data["pkg"]
                a_path = DRAFT_AUDIO_PATH
                arch_key = pkg.get("subtitle_archetype", "FORGE_AMBER")
                arch = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["FORGE_AMBER"])
                
                timings = p_data.get("timings", [])
                c_paths = []
                for idx, c in enumerate(uploaded_clips):
                    cp = os.path.join(TMP_DIR, f"clip_{idx}.mp4")
                    with open(cp, "wb") as f: f.write(c.read())
                    c_paths.append(cp)

                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', a_path], capture_output=True, text=True)
                dur = (float(probe.stdout.strip()) if probe.stdout.strip() else 18.5) + 0.5
                
                clip_target_dur = dur / float(num_clips)
                clip_speed = clip_target_dur / 4.0

                ass_p = os.path.join(TMP_DIR, "subtitles.ass")
                build_ass_subtitles(timings, pkg["script"], ass_p, dur, arch_key)
                clean_ass_path = ass_p.replace("'", "\\'").replace(":", "\\:")
                clean_fonts_dir = FONTS_DIR.replace("'", "\\'").replace(":", "\\:")

                active_overlay_text = custom_overlay_txt.strip() if custom_overlay_txt.strip() else pkg.get("video_overlay_text", "TIMELESS LAW")
                banner = active_overlay_text.replace("'", "\\'").replace(":", "\\:")
                out_p = os.path.join(TMP_DIR, "master_output.mp4")
                
                active_style = chosen_director_fx
                st.session_state["rendered_director_style"] = active_style

                if "Floating Shadow" in overlay_style:
                    dt_filter = f"drawtext=text='{banner}':fontsize=38:fontcolor={arch['banner_hex']}:box=0:shadowx=3:shadowy=4:shadowcolor=black@0.9:x=(w-text_w)/2:y=170:enable='between(t,0,3.2)'"
                elif "Minimalist Top Pill" in overlay_style:
                    dt_filter = f"drawtext=text='{banner}':fontsize=34:fontcolor={arch['banner_hex']}:box=1:boxcolor=black@0.7:boxborderw=10:x=(w-text_w)/2:y=145:enable='between(t,0,3.2)'"
                elif "Subtle Border Frame" in overlay_style:
                    dt_filter = f"drawtext=text='{banner}':fontsize=36:fontcolor={arch['banner_hex']}:box=1:boxcolor=black@0.65:boxborderw=14:borderw=1:bordercolor={arch['banner_hex']}@0.5:x=(w-text_w)/2:y=170:enable='between(t,0,3.2)'"
                else:
                    dt_filter = f"drawtext=text='{banner}':fontsize=40:fontcolor={arch['banner_hex']}:box=1:boxcolor=black@0.85:boxborderw=16:x=(w-text_w)/2:y=170:enable='between(t,0,3.2)'"

                v_filters = []
                for i in range(num_clips):
                    filters_for_clip = [
                        f"trim=0:4",
                        f"setpts=(PTS-STARTPTS)*{clip_speed:.4f}",
                        # Pure optical scale & top-crop removing bottom 254px (100% clears Google Flow watermark)
                        f"scale=1224:2174:force_original_aspect_ratio=increase",
                        f"crop=1080:1920:(in_w-1080)/2:0",
                        f"fps=25"
                    ]
                    
                    if i == 0 and apply_digital_zoom:
                        z_step = 0.15 / max(1, (clip_target_dur * 25))
                        filters_for_clip.append(f"zoompan=z='min(zoom+{z_step:.5f},1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=25")

                    if i > 0 and flash_intensity > 0:
                        if active_style in ["PUNCH_FLASH", "NORDIC_CUT"]:
                            filters_for_clip.append(f"fade=t=in:st=0:d={flash_intensity:.2f}:color=white")
                        elif active_style == "WARM_DRIFT":
                            filters_for_clip.append(f"fade=t=in:st=0:d={flash_intensity * 1.5:.2f}:color=black")

                    if enable_vignette:
                        filters_for_clip.append("vignette=PI/4")
                    if enable_film_grain:
                        filters_for_clip.append("noise=alls=4:allf=t+u")

                    v_filters.append(f"[{i}:v]" + ",".join(filters_for_clip) + f"[v{i}];")
                
                concat_labels = "".join([f"[v{i}]" for i in range(num_clips)])
                v_filters.append(f"{concat_labels}concat=n={num_clips}:v=1:a=0[vb];")
                v_filters.append(f"[vb]{dt_filter},ass='{clean_ass_path}':fontsdir='{clean_fonts_dir}'[vsub]")
                
                inputs = []
                for cp in c_paths: inputs.extend(['-i', cp])
                inputs.extend(['-i', a_path])
                audio_idx = num_clips

                logo = "logo.png" if os.path.exists("logo.png") else None
                if logo:
                    inputs.extend(['-i', logo])
                    logo_idx = num_clips + 1
                    v_filters.append(f";[{logo_idx}:v]scale=120:-1,format=rgba,fade=t=in:st=0.4:d=0.8:alpha=1[ls];[vsub][ls]overlay=W-w-50:150:enable='gte(t,0.4)'[vout]")
                else: 
                    v_filters.append(";[vsub]copy[vout]")

                active_bgm_path = None
                if chosen_bgm_mode == "UPLOAD" and custom_music_file:
                    active_bgm_path = os.path.join(MUSIC_DIR, custom_music_file.name)
                else:
                    active_bgm_path, _ = resolve_background_track(chosen_bgm_mode, arch_key)

                if active_bgm_path and os.path.exists(active_bgm_path):
                    inputs.extend(['-i', active_bgm_path])
                    bgm_idx = len(inputs) // 2 - 1
                    v_filters.append(
                        f";[{audio_idx}:a]loudnorm=I=-14:TP=-1.0:LRA=7,asplit=2[vo_out][vo_sc];"
                        f"[{bgm_idx}:a]aloop=loop=-1:size=2e+09,loudnorm=I={bgm_vol_level}:TP=-2.0:LRA=7,afade=t=out:st={dur-1.8:.1f}:d=1.8[bg_clean];"
                        f"[bg_clean][vo_sc]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=350[bg_ducked];"
                        f"[vo_out][bg_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
                    )
                else: 
                    v_filters.append(f";[{audio_idx}:a]loudnorm=I=-14:TP=-1.0:LRA=7[aout]")

                res = subprocess.run([
                    'ffmpeg', '-y', *inputs, 
                    '-filter_complex', "".join(v_filters), 
                    '-map', '[vout]', '-map', '[aout]', 
                    '-t', str(dur), 
                    '-c:v', 'libx264', '-preset', 'ultrafast', '-threads', '2', '-crf', '22', 
                    '-c:a', 'aac', '-b:a', '192k', 
                    '-pix_fmt', 'yuv420p', out_p
                ], capture_output=True, text=True)
                
                if res.returncode != 0: 
                    st.error(f"FFmpeg Error: {res.stderr[:300]}")
                else:
                    st.session_state["rendered_video_path"] = out_p
                    st.success(f"🎉 Master {dur:.1f}s Reel Rendered! Zero Watermarks, High-Retention Pacing.")

    if "rendered_video_path" in st.session_state and "active_video_pkg" in st.session_state:
        vp = st.session_state["rendered_video_path"]
        st.video(vp)
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data["pkg"]
        
        st.divider()
        st.markdown("### 🎯 GOOGLE DRIVE VAULT & QUEUE SLOT")
        
        col_qd1, col_qd2 = st.columns(2)
        default_target_date = datetime.strptime(target_d, "%Y-%m-%d").date()
        with col_qd1: chosen_date_target = st.date_input("Target Schedule Date", value=default_target_date)
        with col_qd2: chosen_slot_target = st.selectbox("Target Schedule Slot", ["SLOT 1 (MORNING)", "SLOT 2 (EVENING)"], index=(0 if "SLOT 1" in target_s else 1))
            
        s1_t, s2_t = db.get("slot1_time", "05:00"), db.get("slot2_time", "18:00")
        chosen_time_target = s1_t if "SLOT 1" in chosen_slot_target else s2_t
        c_d = chosen_date_target.strftime("%Y-%m-%d")
        c_s = chosen_slot_target
        c_t = chosen_time_target

        slot_code = "S1" if "SLOT 1" in c_s else "S2"
        pl_name = pkg.get("playlist", "The art of moving in silence (stoic mindset)")
        pl_code = "SILENCE" if "silence" in pl_name.lower() else ("PARABLES" if "parables" in pl_name.lower() else ("FINANCE" if "financial" in pl_name.lower() else ("LEGACY" if "father" in pl_name.lower() else "AGING")))
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', pkg.get('hook_banner', 'reel')).strip('_').lower()
        
        exp_name = f"{c_d}_{slot_code}_{pl_code}_{slug}.mp4"
        folder_name = f"{c_d}_{slot_code}_{pl_code}_{slug}"

        st.info(f"Targeting: **{c_d} @ {c_t} IST ({c_s})**\n\nDrive Folder: `EchoesOfWisdom/01_READY_TO_SCHEDULE/{folder_name}`")

        with open(vp, "rb") as f: vb = f.read()
        st.download_button(f"💾 Download Master Reel ({exp_name})", vb, exp_name, "video/mp4")

        # -------------------------------------------------
        # 🔴 YOUTUBE SHORTS PUBLISHING FLOW (@AJ-Echoes-of-Wisdom)
        # -------------------------------------------------
        st.divider()
        st.markdown("### 🔴 1. YOUTUBE SHORTS PUBLISHING FLOW")
        
        raw_hook = pkg.get("hook_banner", "NEVER ANNOUNCE YOUR EXIT").title()
        yt_t = pkg.get("youtube_title", f"⚡ {raw_hook} 🏛️ #shorts #stoicism")
        if not yt_t.startswith("⚡"): yt_t = f"⚡ {yt_t}"
        st.text_input("1. YouTube Title (100 char limit)", yt_t, key="yt_t_val")
        render_copy("yt_t", "COPY YOUTUBE TITLE", yt_t)
        
        q_ref = pkg.get("reflection_question", pkg.get("youtube_pinned_comment", "What is one hard truth life taught you that changed how you handle pressure?"))
        raw_desc = (
            f"⚡ {pkg.get('hook_banner', '').upper()}\n\n"
            f"{pkg.get('caption_lesson', '')}\n\n"
            f"💭 {q_ref}\n\n"
            f"🏛️ Subscribe to {get_persistent_yt_handle()} for timeless clarity.\n\n"
            f"#stoicism #lifelessons #discipline #echoesofwisdom #shorts"
        )
        st.text_area("2. YouTube Description", raw_desc, height=135, key="yt_d_val")
        render_copy("yt_d", "COPY YOUTUBE DESCRIPTION", raw_desc)
        
        st.text_input("3. Exact YouTube Playlist Name", pl_name, key="yt_pl_val")
        render_copy("yt_pl", "COPY PLAYLIST NAME", pl_name)
        
        default_tags = "stoicism, echoes of wisdom, life lessons, stoic mindset, discipline, self improvement, marcus aurelius, mental strength, mens wisdom, shorts"
        yt_tags = pkg.get("youtube_tags", default_tags)
        st.text_area("4. YouTube Video Tags", yt_tags, height=65, key="yt_tags_val")
        render_copy("yt_tags", "COPY YOUTUBE TAGS", yt_tags)
        
        yt_pin = f"💭 {q_ref}"
        st.text_area("5. YouTube Pinned Comment (Non-Bait)", yt_pin, height=65, key="yt_pin_val")
        render_copy("yt_p", "COPY PINNED COMMENT", yt_pin)

        # -------------------------------------------------
        # 🔵 META REELS PUBLISHING FLOW (@EchoesOfWisdomOfficial)
        # -------------------------------------------------
        st.divider()
        st.markdown("### 🔵 2. FACEBOOK & INSTAGRAM REELS FLOW (ZERO ENGAGEMENT BAIT)")

        raw_fb_hook = pkg.get("caption_hook", pkg.get("hook_banner", "NEVER ANNOUNCE YOUR EXIT"))
        fb_hook = to_unicode_bold(re.sub(r"[^\w\s-]", "", raw_fb_hook).strip().upper())
        fb_cap = (
            f"⚡ {fb_hook} 🏛️\n\n"
            f"{pkg.get('caption_lesson', '')}\n\n"
            f"💭 {q_ref}\n\n"
            f"Save this reminder for difficult days, or share it with someone building their future.\n\n"
            f"• Follow {get_persistent_meta_handle()} for timeless clarity.\n\n"
            f"{pkg.get('meta_hashtags', '#Stoicism #LifeLessons #Mindset #Wisdom #PersonalGrowth')}"
        )
        st.text_area("1. Meta Reel Caption (Non-Bait)", fb_cap, height=175, key="fb_cap_val")
        render_copy("fb_c", "COPY META REEL CAPTION", fb_cap)

        fb_first_comment = (
            f"🏛️ Want a structured daily system to build emotional composure and mental discipline?\n\n"
            f"Explore The 30-Day Stoic Emotional Mastery Guide & Workbook here:\n"
            f"{get_persistent_guide_url()}\n"
            f"(Use code FIRST50 at checkout)"
        )
        st.text_area("2. Meta First Comment (Clean Guide Link)", fb_first_comment, height=105, key="fb_comm_val")
        render_copy("fb_comm", "COPY META FIRST COMMENT", fb_first_comment)

        st.text_input("3. Meta Topic Tags", "Stoicism, Philosophy, Personal Growth, Life Lessons", key="fb_tags_val")
        render_copy("fb_tags", "COPY META TAGS", "Stoicism, Philosophy, Personal Growth, Life Lessons")

        st.markdown("""
        <div style="margin: 12px 0 16px 0;">
            <a href="https://business.facebook.com/latest/reels_composer" target="_blank" style="text-decoration: none;">
                <button style="width: 100%; height: 3.2rem; background: #1877F2; color: white; border: none; border-radius: 8px; font-weight: 700; font-family: -apple-system, sans-serif; font-size: 13px; cursor: pointer; box-shadow: 0 4px 15px rgba(24, 119, 242, 0.35);">
                    🌐 OPEN META REELS COMPOSER (9:16 NATIVE)
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)

        if st.button("✅ Lock & Advance Slot", type="primary"):
            director_style_resolved = st.session_state.get("rendered_director_style", chosen_director_fx)
            if director_style_resolved not in CINEMATOGRAPHY_MATRIX:
                director_style_resolved = "PUNCH_FLASH"

            row_payload = {
                "targetDate": c_d,
                "slot": f"{slot_code} - {'Morning (05:00 IST)' if slot_code == 'S1' else 'Evening (18:00 IST)'}",
                "ytStatus": "Ready in Drive",
                "metaStatus": "Ready in Drive",
                "playlist": pl_name,
                "titleConcept": pkg.get("title_concept", ""),
                "hookBanner": pkg.get("hook_banner", ""),
                "driveFolder": f"EchoesOfWisdom/01_READY_TO_SCHEDULE/{folder_name}",
                "videoLink": exp_name,
                "thumbLink": f"{c_d.replace('-','')}_{slug}_thumb.png",
                "ytTitle": yt_t,
                "ytDesc": raw_desc,
                "ytTags": yt_tags,
                "ytPinned": yt_pin,
                "metaCaption": fb_cap,
                "metaComment": fb_first_comment,
                "directorFx": CINEMATOGRAPHY_MATRIX.get(director_style_resolved, {}).get("label", "Dynamic Kinetic Arc & Probe"),
                "notes": "Staged in EchoesOfWisdom/01_READY_TO_SCHEDULE (18-20s Retention)"
            }
            
            db["scheduled_videos"].append({
                "date": c_d, 
                "slot": c_s, 
                "time": c_t, 
                "playlist": pl_name, 
                "theme_id": p_data.get("t_id", "THEME_CUSTOM"), 
                "title": yt_t, 
                "file": exp_name
            })
            if p_data.get("t_id") and p_data["t_id"] not in db.get("used_theme_ids", []): 
                db.setdefault("used_theme_ids", []).append(p_data["t_id"])
            if pkg.get("hook_banner") not in db.get("used_hooks", []): 
                db.setdefault("used_hooks", []).append(pkg.get("hook_banner"))
            db["last_scheduled_date"], db["last_scheduled_slot"] = c_d, c_s
            save_db(db)
            
            excel_updated = append_to_excel_tracker(row_payload)
            
            webhook_url = get_persistent_gsheet_url()
            cloud_synced = False
            if webhook_url:
                try:
                    r = requests.post(webhook_url, json=row_payload, timeout=6)
                    if r.status_code == 200:
                        cloud_synced = True
                except Exception:
                    pass

            if os.path.exists(DRAFT_JSON_PATH): os.remove(DRAFT_JSON_PATH)
            if os.path.exists(DRAFT_AUDIO_PATH): os.remove(DRAFT_AUDIO_PATH)
            
            nd, ns, nt = get_next_slot(c_d, c_s)
            msg_add = " + Synced to Live Sheet! 📊" if cloud_synced else (" + Added to Local Excel Tracker 📑" if excel_updated else "")
            st.session_state["status_banner"] = f"✓ LOCKED: {exp_name} scheduled{msg_add}! Next slot: {nd} @ {nt} IST ({ns})"
            st.session_state.pop("rendered_video_path", None)
            st.session_state.pop("active_video_pkg", None)
            st.session_state.pop("rendered_director_style", None)
            st.rerun()

# --- TAB 3: QUEUE LEDGER & EXCEL TRACKER ---
with tab3:
    st.markdown("### Content Tracker & Export")
    
    if os.path.exists(EXCEL_TRACKER_PATH):
        with open(EXCEL_TRACKER_PATH, "rb") as ef:
            st.download_button(
                "Download Updated Content Tracker (.xlsx)",
                ef.read(),
                "Echoes_Of_Wisdom_Content_Tracker.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        st.caption("Contains all scheduled rows with metadata, tags, and Drive folder links.")
    else:
        st.info("Excel tracker will initialize automatically on your first locked video.")

    st.markdown(f"### Scheduled Queue Ledger ({len(db.get('scheduled_videos', []))})")
    for item in reversed(db.get("scheduled_videos", [])):
        st.markdown(f"""
        <div style="background:#0A0F1D;border:1px solid rgba(56,189,248,0.2);border-radius:8px;padding:8px 12px;margin-bottom:6px;font-family:monospace;font-size:11px;">
            <span style="color:#38BDF8;font-weight:700;">{item.get('date')}</span> @ <span style="color:#FBBF24;">{item.get('time')} IST ({item.get('slot')})</span>
            <div style="color:#F8FAFC;font-weight:600;">{item.get('title')}</div>
            <div style="color:#64748B;">📁 {item.get('file')} | 📺 {item.get('playlist', 'Hard Truths')}</div>
        </div>
        """, unsafe_allow_html=True)
