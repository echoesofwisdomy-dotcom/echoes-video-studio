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

def get_persistent_handle():
    if "CHANNEL_HANDLE" in st.secrets:
        return str(st.secrets["CHANNEL_HANDLE"]).strip()
    if os.path.exists(CHANNEL_HANDLE_FILE):
        try:
            with open(CHANNEL_HANDLE_FILE, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val: return val
        except Exception: pass
    return st.session_state.get("user_channel_handle", "@AJ-Echoes-of-Wisdom").strip()

def save_persistent_handle(handle_val):
    clean = handle_val.strip()
    if clean and not clean.startswith("@"): clean = "@" + clean
    st.session_state["user_channel_handle"] = clean
    try:
        with open(CHANNEL_HANDLE_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception: pass

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
        "cam_s2": "0s-2s: Microscopic close-up tracking water spray and micro-textures; 2s-4s: sudden dynamic whip-pan revealing foaming water violently churning under high pressure",
        "lens_s3": "35mm anamorphic cinema lens, natural horizontal streak flare",
        "cam_s3": "0s-2s: Fast over-the-shoulder tracking dolly following deliberate strides; 2s-4s: camera sweeps around subject in a dramatic 45-degree parallax arc against towering cliff peaks",
        "lens_s4": "85mm portrait telephoto lens, creamy optical bokeh",
        "cam_s4": "0s-2s: Slow breathing push-in on weathered skin texture and salt-and-pepper beard; 2s-4s: protagonist raises piercing calm eyes directly into camera lens",
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
        "cam_s2": "0s-2s: Extreme macro tracking frost crystals and splashing icy droplets; 2s-4s: fast downward tilt capturing raw mechanical power against freezing torrents",
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
    "Hard Truths"
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
# 3. 24 THEMES DATABASE & AUTOMATED PLAYLIST MAPPING
# ---------------------------------------------------------
THEMES_DATABASE = [
    # Playlist: The art of moving in silence (stoic mindset)
    {"id": "SILENT_EXIT", "pl": "The art of moving in silence (stoic mindset)", "p": "Emotional Immunity", "t": "The Silent Exit", "prem": "Never announce when you cut someone off. Withdrawing presence without conflict is sovereign power.", "h": "NEVER ANNOUNCE YOUR EXIT", "a": "GLACIAL_ICE", "m": ["Heavy bronze portal latch locking into dark stone", "Single fraying linen cord burning through over a flame", "Solitary timber skiff drifting into dense lake mist"]},
    {"id": "WEAPON_INDIFFERENCE", "pl": "The art of moving in silence (stoic mindset)", "p": "Emotional Immunity", "t": "Weaponized Indifference", "prem": "If their disrespect triggers your anger, they own you. Cold silence strips away their leverage.", "h": "YOUR REACTION GIVES THEM POWER", "a": "GLACIAL_ICE", "m": ["Monolithic basalt stone unmoved against crashing storm waves", "Torrential rain pouring down a marble statue without a scratch", "Glowing ember dropping on cold slate extinguishing to ash"]},
    {"id": "QUIET_EXECUTION", "pl": "The art of moving in silence (stoic mindset)", "p": "Relentless Focus", "t": "Quiet Execution", "prem": "Never broadcast what you are building. The world flatters plans but only respects finished stone.", "h": "BUILD IN COMPLETE OBSCURITY", "a": "IMPERIAL_GOLD", "m": ["Heavy blacksmith hammer striking glowing blade on dark stone anvil", "Stonemason chisel carving Roman numerals into granite bedrock", "Deep underground tree roots breaking through rock in total darkness"]},
    {"id": "SOLITUDE_ADVANTAGE", "pl": "The art of moving in silence (stoic mindset)", "p": "Relentless Focus", "t": "The Solitude Advantage", "prem": "A man who cannot sit quietly alone is an easy target for anyone promising stimulation.", "h": "LEARN TO SIT IN SILENCE", "a": "IMPERIAL_GOLD", "m": ["Single tall watchtower standing alone on a foggy mountain peak", "Lone golden eagle gliding motionless on thermal winds high above clouds", "Solitary stone lighthouse enduring darkness with a steady beam"]},
    {"id": "DEATH_OF_OPINIONS", "pl": "The art of moving in silence (stoic mindset)", "p": "Radical Acceptance", "t": "Irrelevance of Opinions", "prem": "Why value yourself over others, but value their opinion of you over your own judgment? Reclaim your inner court.", "h": "TRUST YOUR OWN JUDGMENT", "a": "IMPERIAL_GOLD", "m": ["Balance scale holding single gold bullion balancing heaps of straw", "Solid bronze compass needle pointing true North in storm winds", "Ancient judge stone bench standing empty and resolute under open skies"]},
    {"id": "FINAL_BOUNDARY", "pl": "The art of moving in silence (stoic mindset)", "p": "Radical Acceptance", "t": "The Final Boundary", "prem": "The mind is its own place. No tyrant or insult can break inside unless you leave the gate unlocked.", "h": "GUARD YOUR INNER CITADEL", "a": "GLACIAL_ICE", "m": ["Massive carved stone gateway fortified with heavy bronze bands", "Solitary fortress lantern burning steadily against pitch-black mountain fog", "Deep subterranean spring flowing cold and pure under massive granite arches"]},

    # Playlist: Mastering human nature and fake friends ancient parables
    {"id": "UNRETURNED_LOYALTY", "pl": "Mastering human nature and fake friends ancient parables", "p": "Emotional Immunity", "t": "Unreturned Loyalty", "prem": "Blind loyalty to people who only call when they need something is self-betrayal. Close the vault.", "h": "STOP BLEEDING FOR USERS", "a": "FORGE_AMBER", "m": ["Heavy iron vault door swinging shut on oiled hinges", "Cracked clay water vessel leaking water into barren sand", "Withered vine trimmed cleanly from a fruit-bearing olive branch"]},
    {"id": "GOSSIP_STARVE", "pl": "Mastering human nature and fake friends ancient parables", "p": "Emotional Immunity", "t": "Gossip Starvation", "prem": "When someone brings you gossip about others, they will talk about you tomorrow. Starve rumors with silence.", "h": "NEVER FEED SMALL MINDS", "a": "GLACIAL_ICE", "m": ["Dark iron snuffer descending over a guttering candle flame", "Dry withered brush caught in sudden rain stopping fire", "Deep stone cistern swallowing a pebble without producing an echo"]},
    {"id": "COST_LIKABLE", "pl": "Mastering human nature and fake friends ancient parables", "p": "Emotional Immunity", "t": "The Cost of Being Likable", "prem": "Trying to please everyone is not kindness; it is weakness. When everyone likes you, nobody respects you.", "h": "STOP TRYING TO BE LIKED", "a": "FORGE_AMBER", "m": ["Weathered antique theater mask cracking on wet cobblestones", "Brittle dried clay seal crumbling under thumb pressure", "Weathered glass lens fracturing under focused sunlight"]},
    {"id": "ARMOR_EPICTETUS", "pl": "Mastering human nature and fake friends ancient parables", "p": "Emotional Immunity", "t": "The Armor of Epictetus", "prem": "An insult cannot hurt you unless you agree with it. If they mock you, they reveal their own sickness.", "h": "INSULTS ONLY HURT FOOLS", "a": "GLACIAL_ICE", "m": ["Bronze arrow deflecting off a heavy Roman iron shield", "Mud hurled against a granite castle bastion washing away", "Venomous snake striking a solid bronze bell with no effect"]},
    {"id": "ENVY_DESTRUCTION", "pl": "Mastering human nature and fake friends ancient parables", "p": "Relentless Focus", "t": "The Toxicity of Comparison", "prem": "When you envy another person's victory, you declare that your own journey is worthless. Mind your own craft.", "h": "NEVER WATCH THEIR RACE", "a": "FORGE_AMBER", "m": ["Racehorse wearing blinders charging forward on dry dirt arena", "Craftsman magnifying loupe focusing strictly on fine gold engravings", "Sundial tracking the sun without regard for passing clouds"]},
    {"id": "STRIP_PEDESTAL", "pl": "Mastering human nature and fake friends ancient parables", "p": "Radical Acceptance", "t": "Stripping the Pedestal", "prem": "Never put anyone on a pedestal. They bleed, make mistakes, and age just like you.", "h": "NOBODY IS ABOVE YOU", "a": "GLACIAL_ICE", "m": ["Gilded monument showing exposed cracked limestone under worn gold leaf", "Royal purple woolen mantle turning to simple thread under inspection", "Chess board being cleared where kings and pawns go into the same box"]},

    # Playlist: Hard Truths
    {"id": "MEMENTO_MORI", "pl": "Hard Truths", "p": "Radical Acceptance", "t": "Memento Mori", "prem": "You could leave life right now. Let that determine what you do, what you say, and what you think.", "h": "YOU ARE RUNNING OUT OF TIME", "a": "FORGE_AMBER", "m": ["Fine golden sand falling steadily through an ancient hourglass neck", "Shadow lengthening across Roman stone numerals on a sundial face", "Single dried autumn leaf detaching and drifting on a brisk wind"]},
    {"id": "BURDEN_EXPECTATIONS", "pl": "Hard Truths", "p": "Mental Fortress", "t": "The Myth of Fairness", "prem": "The universe owes you nothing. Expecting life to treat you gently because you are good is self-deception.", "h": "THE WORLD OWES YOU NOTHING", "a": "GLACIAL_ICE", "m": ["Jagged granite headland taking crashing ocean waves without yielding", "Desert sandstorm sweeping across an ancient stone obelisk", "Heavy bronze coin falling indifferently on stone whether heads or tails"]},
    {"id": "DOPAMINE_BANKRUPT", "pl": "Hard Truths", "p": "Relentless Focus", "t": "Dopamine Bankruptcy", "prem": "You are not tired from hard work; you are drained from chasing worthless noise. Guard your stillness fiercely.", "h": "YOU ARE DRAINED BY NOISE", "a": "FORGE_AMBER", "m": ["Antique bronze oil lamp burning steadily down to deep amber embers", "Clear mountain spring water settling completely transparent in a vial", "Iron pendulum slowing to a complete, balanced standstill"]},
    {"id": "SUNK_COST_TRAP", "pl": "Hard Truths", "p": "Relentless Focus", "t": "The Sunk Cost Trap", "prem": "Just because you spent years making a mistake does not mean you owe it your future. Cut the cord immediately.", "h": "STOP FEEDING DEAD DREAMS", "a": "FORGE_AMBER", "m": ["Sharp pruning sickle cleanly slicing an anchor rope under high tension", "Heavy dry branch snapping off a centuries-old oak in storm winds", "Antique weighing scale dumping heavy slag to return to equilibrium"]},
    {"id": "MYTH_OF_WAITING", "pl": "Hard Truths", "p": "Relentless Focus", "t": "The Myth of Motivation", "prem": "Motivation is a fair-weather friend. Discipline is doing the work even when your emotions protest.", "h": "ACTION CURES SELF-PITY", "a": "FORGE_AMBER", "m": ["Heavy waterwheel turning relentlessly against turbulent mountain river currents", "Flint and steel striking violently to generate a bright spark", "Team of draft oxen pulling a heavy plow through frost-hardened soil"]},
    {"id": "FUTURE_RUIN", "pl": "Hard Truths", "p": "Mental Fortress", "t": "The Illusion of Future Ruin", "prem": "We suffer far more in imagination than in reality. The catastrophe keeping you awake will never arrive.", "h": "YOU SUFFER IN YOUR HEAD", "a": "IMPERIAL_GOLD", "m": ["Cold morning mist dissolving over ancient stone arches under sunlight", "Troubled pool of dark water settling into a crystal mirror as ripples fade", "Dark storm cloud dispersing harmlessly across a barren plain"]},
    {"id": "CALAMITY_TRAINING", "pl": "Hard Truths", "p": "Mental Fortress", "t": "Calamity as Training", "prem": "Do not curse the obstacle; the obstacle is your teacher. Adversity produces character comfort cannot buy.", "h": "THE STRUGGLE IS THE TEACHER", "a": "IMPERIAL_GOLD", "m": ["Roaring forge furnace turning raw scrap iron into hardened steel", "Mountain pine tree growing dense and unshakeable in freezing gale winds", "Diamond blade grinding down rough raw stone into a sharp facet"]},
    {"id": "DEATH_OF_PRIDE", "pl": "Hard Truths", "p": "Mental Fortress", "t": "The Death of Pride", "prem": "Arrogance demands an audience. Real confidence speaks quietly, works without applause, and walks without a strut.", "h": "KILL YOUR NEED FOR PRAISE", "a": "IMPERIAL_GOLD", "m": ["Deep subterranean bedrock supporting an entire city without showing itself", "Dark iron anchor resting silently at the bottom of the ocean floor", "Ancient oak tree whose strength lies in its hidden root network"]},
    {"id": "CONTROL_DESIRE", "pl": "Hard Truths", "p": "Mental Fortress", "t": "The Chains of Wanting", "prem": "Wealth does not consist in great possessions, but in few wants. He who is content cannot be enslaved.", "h": "WANT LESS TO RULE MORE", "a": "IMPERIAL_GOLD", "m": ["Heavy broken iron shackles lying in dust beside an open cell gate", "Simple earthenware cup filled with cool clear mountain well water", "Rustic wooden staff supporting a traveler over rugged mountain ridges"]},
    {"id": "ANGER_POISON", "pl": "Hard Truths", "p": "Mental Fortress", "t": "Anger Is Self-Poison", "prem": "Holding onto anger is drinking poison and expecting the other person to die. Calmness is the ultimate weapon.", "h": "ANGER IS TEMPORARY MADNESS", "a": "GLACIAL_ICE", "m": ["Boiling water in a bronze cauldron cooling down to smooth stillness", "Wild brushfire hitting a wide dirt trench and running out of fuel", "Raging wild stallion brought to stillness by a steady hand on the reins"]},
    {"id": "AMOR_FATI", "pl": "Hard Truths", "p": "Radical Acceptance", "t": "Amor Fati", "prem": "Do not demand that things happen as you wish. Accept what happens as necessary and move forward.", "h": "ACCEPT WHATEVER COMES NEXT", "a": "IMPERIAL_GOLD", "m": ["Raging river flowing around boulders without slowing its descent", "Large campfire consuming whatever fuel is thrown into its flames", "Ship sail adjusting its ropes to catch crosswinds and maintain heading"]},
    {"id": "RIVER_OF_TIME", "pl": "Hard Truths", "p": "Radical Acceptance", "t": "The River of Time", "prem": "The pain you feel right now will pass. The victory you celebrate today will fade. Ground your peace in eternity.", "h": "THIS TOO SHALL PASS", "a": "IMPERIAL_GOLD", "m": ["Fast river water rushing over polished river stones under sunlight", "Ancient Roman stone ruins standing tranquil against centuries of weather", "Constellations revolving slowly in clear dark night skies over mountains"]}
]

SETTINGS_MATRIX = [
    {"n": "The Ancient Citadel Colonnades", "d": "Within towering monolithic ancient stone colonnades and rain-slicked courtyards with bronze braziers casting dramatic shadows."},
    {"n": "The Windswept Coastal Cliffs", "d": "Atop high windswept coastal cliffs overlooking turbulent dark ocean waves crashing against jagged basalt rocks in atmospheric fog."},
    {"n": "The Secluded Stone Workshop", "d": "Inside a secluded ancient stone workshop with drafting parchment, beeswax candles, deep shadows, and glowing forge embers."},
    {"n": "The Rugged Mountain Summit", "d": "Traversing a barren rocky mountain pass under cold dramatic grey skies and swirling morning mist beside weathered stone shrines."}
]

# ---------------------------------------------------------
# 4. CADENCE & PERSISTENT DATA
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
# 6. RESILIENT VOICE SYNTHESIZER
# ---------------------------------------------------------
def synthesize_with_gemini_audio(api_key, text, audio_path, voice_name="Charon"):
    clean_k = api_key.strip().strip('"').strip("'")
    if not clean_k: return False, None
    client = genai.Client(api_key=clean_k)
    target_voice = "Charon" if "Charon" in voice_name else "Fenrir"
    for m in ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-3.7-flash-tts"]:
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
                            return True, f"Gemini 3.8 ({target_voice} Natural US Male)"
        except Exception: continue
    return False, None

async def synthesize_speech_timed(text, audio_path, primary_voice="Gemini-Charon", api_key=""):
    if api_key:
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
            return timings, "Christopher (US Male)"
    except Exception: pass
    cmd = ['ffmpeg', '-y', '-f', 'lavfi', '-i', 'anullsrc=r=24000:cl=mono', '-t', '24.5', '-c:a', 'libmp3lame', audio_path]
    subprocess.run(cmd, capture_output=True)
    return [], "Ambient Timing Bed (Upload Ready)"

def build_ass_subtitles(timed_words, script_text, ass_path, total_dur, arch_key="IMPERIAL_GOLD"):
    color = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])["ass_primary"]
    events = []
    if timed_words and len(timed_words) >= 5:
        clean_words = []
        for tw in timed_words:
            w_txt = re.sub(r"[^\w\s',.!?-]", "", tw['word']).upper().strip()
            if w_txt: clean_words.append({'word': w_txt, 'start': tw['start'], 'end': tw['end']})
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
        tokens = script_text.split()
        token_groups = [tokens[i:i + 3] for i in range(0, len(tokens), 3)]
        vocal_start = 0.35
        step = max(0.5, (total_dur - vocal_start - 0.4) / max(1, len(token_groups)))
        for idx, grp in enumerate(token_groups):
            st_t = vocal_start + (idx * step)
            en_t = min(total_dur, vocal_start + ((idx + 1) * step))
            txt = re.sub(r"[^\w\s',.!?-]", "", " ".join(grp)).upper().strip()
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
# 7. ZERO-FAIL STOIC VAULT FALLBACK WITH FLOW CINEMATOGRAPHY
# ---------------------------------------------------------
def build_curated_stoic_package(t_obj, macro_c, sett_obj, style_key="PUNCH_FLASH"):
    hook = t_obj["h"]
    premise = t_obj["prem"]
    style_meta = CINEMATOGRAPHY_MATRIX.get(style_key, CINEMATOGRAPHY_MATRIX["PUNCH_FLASH"])
    
    script = (
        f"{hook.title()}. {premise} Waiting for motivation is a quiet trap. Fleeting emotions always "
        f"abandon you the exact moment hardship strikes. True discipline asks no permission from comfortable moods; "
        f"it operates solely through relentless resolve. Stop negotiating with weakness. Stand firm, honor your duty, "
        f"and execute your labor despite inner protest. Silence your restless mind and remember that only—"
    )
    
    CHARACTER_ARCHETYPES = [
        "An authentic mature Roman centurion with a stern weathered face, short military crop, subtle facial scar, wearing polished dark iron shoulder plates over a crimson tunic. Strictly two arms only, flawless human anatomy.",
        "An ancient Eastern scholar with calm penetrating eyes, fine traditional silk robes, hair tied in a clean topknot, holding a bamboo writing brush. Strictly two arms only, flawless human anatomy.",
        "A hooded desert ascetic with sun-bronzed skin, piercing eyes, wrapped in rugged linen travel cloakes against windblown dust. Strictly two arms only, flawless human anatomy.",
        "A focused medieval blacksmith with soot-dusted cheeks, intense focused gaze, rolled leather sleeves showing muscular forearms. Strictly two arms only, flawless human anatomy.",
        "An authentic mature stoic philosopher with a weathered lined face, calm meditative eyes, messy salt-and-pepper hair and beard, draped in a dark woolen mantle. Strictly two arms only, flawless human anatomy."
    ]
    char_desc = random.choice(CHARACTER_ARCHETYPES)

    return {
        "title_concept": t_obj["t"],
        "playlist": t_obj.get("pl", "Hard Truths"),
        "hook_banner": hook,
        "subtitle_archetype": t_obj["a"],
        "director_style": style_key,
        "script": script,
        "scene1_prompt": f"[4-second vertical 9:16 cinematic video clip] Protagonist ({char_desc}) in {sett_obj['n'].lower()}. {style_meta['cam_s1']}. LENS: {style_meta['lens_s1']}. {style_meta['grade']}. Flawless anatomy, strictly two arms, photorealistic 8k.",
        "scene2_prompt": f"[4-second vertical 9:16 cinematic video clip] {macro_c}. {style_meta['cam_s2']}. LENS: {style_meta['lens_s2']}. {style_meta['grade']}. Photorealistic micro-details, extreme texture resolution.",
        "scene3_prompt": f"[4-second vertical 9:16 cinematic video clip] Protagonist ({char_desc}) traversing {sett_obj['n'].lower()}. {style_meta['cam_s3']}. LENS: {style_meta['lens_s3']}. {style_meta['grade']}. Realistic cloth physics, strictly two arms.",
        "scene4_prompt": f"[4-second vertical 9:16 cinematic video clip] Protagonist ({char_desc}) intense composure shot. {style_meta['cam_s4']}. LENS: {style_meta['lens_s4']}. {style_meta['grade']}. Piercing stoic resolve, flawless human face, cold breath mist.",
        "thumbnail_prompt": (
            f"Dramatic 9:16 vertical cinematic portrait of a mature stoic philosopher with weathered features and salt-and-pepper beard in {sett_obj['n'].lower()}, "
            f"intense steady gaze, cinematic volumetric lighting. Prominently centered in the upper-third (20% to 35% from the top margin, strictly above character's head) is massive, ultra-bold typography reading exactly: \"{hook}\". "
            f"The text is rendered in thick distressed sans-serif block lettering, high-contrast {'radiant imperial gold' if t_obj.get('a') == 'IMPERIAL_GOLD' else ('frost glacial cyan' if t_obj.get('a') == 'GLACIAL_ICE' else 'molten forge amber')} color with a dark ambient drop shadow for maximum legibility against atmospheric fog. "
            f"The typography does not obscure the character's face. Strictly NO text in the lower half of the frame. Flawless human anatomy, strictly two arms."
        ),
        "youtube_title": f"⚡ {hook.title()} 🏛️ #shorts #stoicism",
        "youtube_description": f"⚡ {hook}\n\n{premise}\n\n🤔 TODAY'S STOIC QUESTION:\nWhen facing uninvited chaos:\n1️⃣ Stand resolute in silence\n2️⃣ Defend your territory verbally\n\nDrop 1 or 2 below! 👇\n\n🏛️ Subscribe to {get_persistent_handle()} for timeless clarity.\n\n#stoicism #stoicmindset #discipline #echoesofwisdom #shorts",
        "youtube_tags": "stoicism, echoes of wisdom, stoic quotes, daily stoic, discipline, self improvement, marcus aurelius, mental strength, shorts",
        "youtube_pinned_comment": "When facing uninvited chaos: 1️⃣ Stand resolute in silence, or 2️⃣ React immediately? Drop 1 or 2 below! 👇",
        "caption_hook": hook,
        "caption_lesson": premise,
        "debate_question": "When faced with this choice:",
        "choice_1": "Stand resolute in silence",
        "choice_2": "Defend your territory verbally",
        "meta_hashtags": "#StoicMindset #EchoesOfWisdom #Discipline #Reels"
    }

def generate_video_package(raw_api_key, t_obj, macro_c, sett_obj, style_key="PUNCH_FLASH"):
    clean_key = raw_api_key.strip().strip('"').strip("'") if raw_api_key else ""
    clean_handle = get_persistent_handle()
    used_h = "\n".join([f"- {h}" for h in db.get("used_hooks", [])[-30:]]) or "None."
    style_meta = CINEMATOGRAPHY_MATRIX.get(style_key, CINEMATOGRAPHY_MATRIX["PUNCH_FLASH"])
    
    CHARACTER_ARCHETYPES = [
        "An authentic mature Roman centurion with a stern weathered face, short military crop, subtle facial scar, wearing polished dark iron shoulder plates over a crimson tunic. Strictly two arms only, flawless human anatomy.",
        "An ancient Eastern scholar with calm penetrating eyes, fine traditional silk robes, hair tied in a clean topknot, holding a bamboo writing brush. Strictly two arms only, flawless human anatomy.",
        "A hooded desert ascetic with sun-bronzed skin, piercing eyes, wrapped in rugged linen travel cloakes against windblown dust. Strictly two arms only, flawless human anatomy.",
        "A focused medieval blacksmith with soot-dusted cheeks, intense focused gaze, rolled leather sleeves showing muscular forearms. Strictly two arms only, flawless human anatomy.",
        "An authentic mature stoic philosopher with a weathered lined face, calm meditative eyes, messy salt-and-pepper hair and beard, draped in a dark woolen mantle. Strictly two arms only, flawless human anatomy."
    ]
    char_desc = random.choice(CHARACTER_ARCHETYPES)
    
    prompt = (
        f"You are Executive Creative Director for 'Echoes of Wisdom' (9:16 vertical short-form reels).\n"
        f"PLAYLIST: {t_obj.get('pl', 'Hard Truths')} | THEME: {t_obj['t']}\nPREMISE: {t_obj['prem']}\nDEFAULT HOOK: {t_obj['h']}\n"
        f"MACRO METAPHOR (SCENE 2): {macro_c}\nENVIRONMENT: {sett_obj['d']}\n"
        f"DIRECTOR CINEMATOGRAPHY MATRIX INSTRUCTIONS:\n"
        f"- Scene 1 Camera & Lens: {style_meta['cam_s1']}. Lens: {style_meta['lens_s1']}.\n"
        f"- Scene 2 Camera & Lens: {style_meta['cam_s2']}. Lens: {style_meta['lens_s2']}.\n"
        f"- Scene 3 Camera & Lens: {style_meta['cam_s3']}. Lens: {style_meta['lens_s3']}.\n"
        f"- Scene 4 Camera & Lens: {style_meta['cam_s4']}. Lens: {style_meta['lens_s4']}.\n"
        f"- Color & Atmosphere: {style_meta['grade']}\n"
        f"FORBIDDEN HOOKS (DO NOT USE):\n{used_h}\n"
        f"RULES:\n1. Exactly 65-70 words.\n2. Line 1 hook: 3-4 words direct challenge.\n3. Last line seamlessly loops back to line 1.\n"
        f"4. Google Flow Character Rules: {char_desc}\n"
        f"5. Prompt Formatting: All 4 video prompts MUST start with '[4-second vertical 9:16 cinematic video clip]' and explicitly embed the exact intra-shot progression (e.g. 0s-2s and 2s-4s), lens focal length, and lighting atmosphere.\n"
        f"6. THUMBNAIL TYPOGRAPHY MANDATE: The 'thumbnail_prompt' MUST command bold typography reading exactly: 'typography reading exactly: \"[HOOK_BANNER]\"'. Specify vertical placement strictly in the upper third (20% to 35% from top margin, above character's head), massive distressed sans-serif block lettering, high-contrast {('radiant imperial gold' if t_obj.get('a') == 'IMPERIAL_GOLD' else ('frost glacial cyan' if t_obj.get('a') == 'GLACIAL_ICE' else 'molten forge amber'))} color with subtle dark drop shadow for maximum legibility, completely clear of facial features, and strictly NO text in the bottom half.\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        "{\n"
        '  "title_concept": "Short Concept Title",\n'
        f'  "playlist": "{t_obj.get("pl", "Hard Truths")}",\n'
        '  "hook_banner": "3-4 WORDS IN CAPS",\n'
        f'  "subtitle_archetype": "{t_obj["a"]}",\n'
        f'  "director_style": "{style_key}",\n'
        '  "script": "Full 65-70 word script.",\n'
        '  "scene1_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 1 protagonist with 0s-2s and 2s-4s camera kinetics, lens and lighting",\n'
        f'  "scene2_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 2 macro ({macro_c}) with intra-shot tilt/pan, lens and lighting",\n'
        '  "scene3_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 3 protagonist action with tracking parallax, lens and lighting",\n'
        '  "scene4_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 4 protagonist extreme resolve portrait with intra-shot glance and lighting",\n'
        '  "thumbnail_prompt": "High-contrast 9:16 vertical portrait with centered upper-third distressed bold typography reading: \\"[HOOK_BANNER]\\", color with dark drop shadow, clear of face, strictly no bottom text, strictly two arms",\n'
        '  "youtube_title": "⚡ Hook Title 🏛️ #shorts #stoicism",\n'
        f'  "youtube_description": "⚡ HOOK\\n\\nLesson text...\\n\\n🤔 QUESTION:\\n1️⃣ Option 1\\n2️⃣ Option 2\\n\\n🏛️ Subscribe to {clean_handle}\\n\\n#stoicism #shorts",\n'
        '  "youtube_tags": "stoicism, echoes of wisdom, stoic philosophy, discipline, mental strength, self improvement, marcus aurelius, daily stoic, shorts",\n'
        '  "youtube_pinned_comment": "Binary debate question with 1️⃣/2️⃣ options",\n'
        '  "caption_hook": "PUNCHY 4-6 WORD HOOK",\n'
        '  "caption_lesson": "Two sentences of wisdom.",\n'
        '  "debate_question": "When faced with this choice:",\n'
        '  "choice_1": "Stoic action",\n'
        '  "choice_2": "Impulsive action",\n'
        '  "meta_hashtags": "#StoicMindset #EchoesOfWisdom #Discipline #Reels"\n'
        "}"
    )

    if clean_key:
        try:
            client = genai.Client(api_key=clean_key)
            models = ["gemini-3.8-flash", "gemini-3.8-flash-lite", "gemini-3.7-flash"]
            for m in models:
                for backoff in [1.5, 3.0]:
                    try:
                        r = client.models.generate_content(
                            model=m, 
                            contents=prompt, 
                            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.85)
                        )
                        raw = r.text.strip()
                        match = re.search(r'\{.*\}', raw, re.DOTALL)
                        clean_json = match.group(0) if match else raw
                        parsed = json.loads(clean_json)
                        if "script" in parsed: 
                            return parsed, "Gemini 3.8 AI"
                    except Exception as e:
                        if "503" in str(e) or "429" in str(e):
                            time.sleep(backoff)
                        continue
        except Exception: pass

    return build_curated_stoic_package(t_obj, macro_c, sett_obj, style_key), "Stoic Vault (Zero-Fail Mode)"

# ---------------------------------------------------------
# 8. TELEMETRY BAR & PUBLISHING SETTINGS
# ---------------------------------------------------------
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 600;">v7.2 // DYNAMIC VISUAL DIVERSITY & ANTI-REPETITION SUITE</span>
</div>
""", unsafe_allow_html=True)

recent_ids = db.get("used_theme_ids", [])[-14:]
fresh_count = len(THEMES_DATABASE) - len(set(recent_ids))
track_count = len(get_library_tracks())

st.markdown(f"""
<div style="margin-bottom: 14px;">
    <span class="badge badge-green">● ENGINE ONLINE</span>
    <span class="badge badge-purple">🛡️ {fresh_count} FRESH THEMES</span>
    <span class="badge badge-blue">🎵 {track_count} AUDIO TRACKS IN VAULT</span>
    <span class="badge badge-amber">📅 {target_d} @ {target_t} IST ({target_s})</span>
</div>
""", unsafe_allow_html=True)

if "status_banner" in st.session_state:
    st.success(st.session_state.pop("status_banner"))

with st.expander("📅 PUBLISHING CADENCE & BATCH VAULT SETTINGS"):
    st.markdown("#### ⏰ Release Cadence (Target IST Slots)")
    c1, c2 = st.columns(2)
    saved_d = datetime.strptime(db["last_scheduled_date"], "%Y-%m-%d").date() if db.get("last_scheduled_date") else datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    with c1:
        cd = st.date_input("Last Scheduled Date", value=saved_d)
        cs = st.selectbox("Last Slot", ["SLOT 1 (MORNING)", "SLOT 2 (EVENING)"], index=(0 if "SLOT 1" in str(db.get("last_scheduled_slot","")).upper() else 1))
    with c2:
        ct1 = st.time_input("Slot 1 (IST)", value=dt_time(int(db.get("slot1_time","05:00").split(":")[0]), int(db.get("slot1_time","05:00").split(":")[1])))
        ct2 = st.time_input("Slot 2 (IST)", value=dt_time(int(db.get("slot2_time","18:00").split(":")[0]), int(db.get("slot2_time","18:00").split(":")[1])))
    
    st.markdown("#### 📺 Active Channel Playlists (Locked)")
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
curr_handle = get_persistent_handle()

with st.expander("🔑 API CREDENTIALS, BRAND HANDLE & SYNC", expanded=(not bool(curr_saved_key))):
    uk = st.text_input("Gemini API Key", value=curr_saved_key, type="password", placeholder="AIzaSy...", key="user_key_input")
    if uk:
        save_persistent_api_key(uk)
        st.caption("✓ Gemini API Key active")

    st.divider()
    st.markdown("#### 🏛️ YouTube & Meta Channel Handle")
    u_h = st.text_input("Channel / Brand Handle", value=curr_handle, placeholder="@AJ-Echoes-of-Wisdom", key="user_handle_input")
    if u_h != curr_handle:
        save_persistent_handle(u_h)
        st.caption(f"✓ Channel handle set to {u_h}")

    st.divider()
    st.markdown("#### 📊 Optional: Google Sheets Webhook Sync")
    st.caption("If you converted your sheet via File ➔ Save as Google Sheets, paste the Web app URL below to auto-sync rows in real time.")
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
    # --- DRAFT VAULT AUTO-RESTORE WIDGET ---
    vault_items = load_draft_vault()
    if vault_items:
        with st.expander(f"📦 RESTORE PREVIOUS DRAFT ({len(vault_items)} SAVED IN VAULT)", expanded=False):
            st.caption("Container reset or app went idle? Select any recently generated script below to restore it instantly into Tab 2.")
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

    # --- QUICK SCRIPT RESTORE (DIRECT PASTE) ---
    with st.expander("📝 QUICK-PASTE SCRIPT RESTORE (FOR EXISTING CLIPS)", expanded=False):
        st.caption("Have clips and thumbnail ready but the active draft was wiped? Paste the script and hook here to re-synthesize audio and subtitles in 10 seconds.")
        col_qp1, col_qp2 = st.columns([2, 1])
        with col_qp1:
            qp_hook = st.text_input("Hook Banner", value="ACTION CURES SELF-PITY", placeholder="e.g. ACTION CURES SELF-PITY")
        with col_qp2:
            qp_pl = st.selectbox("Playlist", PLAYLIST_OPTIONS, index=2)
            
        qp_script = st.text_area(
            "Full Script (65-70 words)",
            value="Action cures self-pity. Waiting for motivation is a coward's quiet trap. Fleeting emotions always abandon you the exact moment hardship strikes. True discipline asks no permission from comfortable moods; it operates solely through relentless resolve. Stop negotiating with weakness. Stand firm, honor your duty, and execute your labor despite inner protest. Silence your restless mind and remember that only—",
            height=100
        )
        if st.button("⚡ Restore Script & Generate Audio Bed", type="primary"):
            k = get_persistent_api_key()
            with st.spinner("⚡ Synthesizing audio narration bed & calibrating subtitles..."):
                t_obj_match = next((t for t in THEMES_DATABASE if t["h"].upper() == qp_hook.strip().upper()), THEMES_DATABASE[16])
                s_obj = SETTINGS_MATRIX[3]
                pkg = build_curated_stoic_package(t_obj_match, "Heavy waterwheel turning against turbulent mountain river currents", s_obj, "PUNCH_FLASH")
                clean_h = qp_hook.strip().upper()
                pkg["script"] = qp_script.strip()
                pkg["hook_banner"] = clean_h
                pkg["playlist"] = qp_pl
                color_desc = "radiant imperial gold" if t_obj_match.get("a") == "IMPERIAL_GOLD" else ("frost glacial cyan" if t_obj_match.get("a") == "GLACIAL_ICE" else "molten forge amber")
                pkg["thumbnail_prompt"] = (
                    f"Dramatic 9:16 vertical cinematic portrait of a mature stoic philosopher with weathered features and salt-and-pepper beard in {s_obj['n'].lower()}, "
                    f"intense steady gaze, cinematic volumetric lighting. Prominently centered in the upper-third (20% to 35% from the top margin, strictly above character's head) is massive, ultra-bold typography reading exactly: \"{clean_h}\". "
                    f"The text is rendered in thick distressed sans-serif block lettering, high-contrast {color_desc} color with a dark ambient drop shadow for maximum legibility against the background. "
                    f"Text does not obscure the face. Strictly NO text in the lower half of the frame. Flawless human anatomy, strictly two arms."
                )
                timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k))
                
                draft_data = {
                    "pkg": pkg,
                    "t_id": t_obj_match["id"],
                    "p": t_obj_match["p"],
                    "pl": qp_pl,
                    "m": "Waterwheel",
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
                st.success("✓ Script & Audio Bed restored into active memory! Head to Tab 2 to render.")
                st.rerun()

    st.markdown("---")
    st.markdown("### 🎲 Synthesize Fresh Stoic Package")
    theme_opts = ["🎲 Smart AI Rotation (Cooldown-Protected)"] + THEMES_DATABASE
    chosen_theme = st.selectbox(
        "Stoic Core Theme",
        theme_opts,
        format_func=lambda x: "🎲 Smart AI Rotation" if isinstance(x, str) else f"{'⏳' if x['id'] in recent_ids else '✨'} {x['t']} ➔ [{x.get('pl','Hard Truths')[:22]}...]"
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

    if st.button("🚀 Synthesize Fresh Stoic Package", type="primary"):
        k = get_persistent_api_key()
        with st.spinner("⚡ Synthesizing script, prompts & intra-shot camera choreography..."):
            t_obj = random.choice([t for t in THEMES_DATABASE if t["id"] not in recent_ids] or THEMES_DATABASE) if isinstance(chosen_theme, str) else chosen_theme
            s_obj = random.choice(SETTINGS_MATRIX) if chosen_setting.startswith("🎲") else next(s for s in SETTINGS_MATRIX if s["n"] == chosen_setting)
            m_choice = random.choice(t_obj["m"])
            
            # Select cinematography style
            resolved_style = random.choice(list(CINEMATOGRAPHY_MATRIX.keys())) if chosen_style_key.startswith("🎲") else chosen_style_key
            
            pkg, engine_source = generate_video_package(k, t_obj, m_choice, s_obj, resolved_style)
            pkg["subtitle_archetype"] = chosen_arch if not chosen_arch.startswith("🤖") else t_obj["a"]
            pkg["playlist"] = t_obj.get("pl", "Hard Truths")
            pkg["director_style"] = resolved_style
            
            timings, v_name = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH, api_key=k))
            
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
                "engine_source": engine_source,
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
        st.divider()
        st.subheader(f"📜 Concept: {pkg.get('title_concept', 'Stoic Reel')}")
        st.markdown(f"**Target Playlist:** `{pkg.get('playlist', 'Hard Truths')}`")
        st.markdown(f"**Engine:** `{p_data.get('engine_source', 'Active')}` &nbsp;|&nbsp; **Palette:** {SUBTITLE_ARCHETYPES.get(pkg.get('subtitle_archetype', 'FORGE_AMBER'), SUBTITLE_ARCHETYPES['FORGE_AMBER'])['label']}")
        st.markdown(f"**Setting:** {p_data.get('s', 'Citadel Colonnades')} &nbsp;|&nbsp; **Voice Bed:** `{p_data.get('voice_used', 'Christopher')}`")
        st.markdown(f"**Cinematography Style:** `{CINEMATOGRAPHY_MATRIX.get(active_director_style, CINEMATOGRAPHY_MATRIX['PUNCH_FLASH'])['label']}`")
        st.markdown(f"**Scene 2 Metaphor:** {p_data.get('m', 'Flint and steel')}")
        st.info(f"🎯 **Hook:** `{pkg.get('hook_banner')}`\n\n🗣️ **Script:**\n\n*{pkg.get('script')}*")
        
        if os.path.exists(DRAFT_AUDIO_PATH):
            st.audio(DRAFT_AUDIO_PATH)

        custom_voice = st.file_uploader("Optional: Replace Narration with Own MP3 File", type=["mp3"])
        if custom_voice:
            with open(DRAFT_AUDIO_PATH, "wb") as f: f.write(custom_voice.read())
            p_data["timings"] = []
            st.success("Custom narration file loaded into vault!")
            st.rerun()
        
        st.markdown("### 📋 Copy Google Flow Prompts (Intra-Shot Moves & Lenses Embedded)")
        st.caption("Each prompt below explicitly programs 0s-2s and 2s-4s camera progression, lens focal length, and atmospheric lighting into Google Flow.")
        for i, (lbl, k) in enumerate([
            ("SCENE 1 (Hook - Intra-Shot Push/Tilt)", "scene1_prompt"), 
            ("SCENE 2 (Macro - Dynamic Probe/Whip)", "scene2_prompt"), 
            ("SCENE 3 (Action - Tracking Parallax Arc)", "scene3_prompt"), 
            ("SCENE 4 (Resolve - Portrait Lighting Shift)", "scene4_prompt"), 
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
        "Drop clips (scene1.mp4, scene2.mp4, ... any number of clips!)",
        type=["mp4", "mov"],
        accept_multiple_files=True
    )

    num_clips = len(uploaded_clips) if uploaded_clips else 0
    if uploaded_clips:
        uploaded_clips = sorted(uploaded_clips, key=lambda x: x.name)
        st.markdown(f'<div style="color: #34D399; font-size: 13px; font-weight: 600; margin-bottom: 8px;">📁 Files loaded: {num_clips} clips ready — {", ".join([c.name for c in uploaded_clips])}</div>', unsafe_allow_html=True)

    # ---------------------------------------------------------
    # DYNAMIC DIRECTOR FX & FLOW INTEGRATION TOGGLES
    # ---------------------------------------------------------
    st.markdown("### 🎬 2. Post-Render Polish & CutCap Transitions")
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
            help="Duration of the white shutter flash between scene cuts (0 = Hard Cut, 0.12s = Recommended CutCap Flash)."
        )

    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        apply_digital_zoom = st.checkbox(
            "🔬 Apply Digital FFmpeg Zoom",
            value=False,
            help="Uncheck if your Flow prompts already generated native 3D camera moves. Checking this adds extra digital push-in via FFmpeg."
        )
    with col_opt2:
        enable_vignette = st.checkbox("🌑 Optical Vignette", value=True, help="Darkens outer corners to frame the subject.")
    with col_opt3:
        enable_film_grain = st.checkbox("🎞️ 35mm Film Grain", value=True, help="Removes the overly smooth 'plastic AI' look.")

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

    # ---------------------------------------------------------
    # ADAPTIVE LOSSLESS THUMBNAIL CROP & SAFE ZONE ENGINE
    # ---------------------------------------------------------
    st.markdown("### 🖼️ 4. Thumbnail Safe-Zone Engine (Upper 20%-45% Placement)")
    thumb = st.file_uploader("Upload raw Google Flow thumbnail", type=["png", "jpg", "jpeg", "webp"])
    if thumb:
        try:
            im = Image.open(thumb).convert("RGB")
            w, h = im.size
            crop_mode = st.radio(
                "Watermark Removal Depth",
                ["Standard (Single Watermark - 5.5% Bottom Crop)", "Deep (Expanded/Double Watermark - 12.5% Bottom Crop)"],
                horizontal=True
            )
            pct = 0.125 if "Deep" in crop_mode else 0.055
            crop_h = h - int(h * pct)
            target_aspect = 9.0 / 16.0
            crop_w = int(crop_h * target_aspect)
            margin_x = max(0, (w - crop_w) // 2)
            
            clean_im = im.crop((margin_x, 0, margin_x + crop_w, crop_h)).resize((1080, 1920), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            clean_im.save(buf, format="PNG", quality=98)
            st.image(clean_im, caption=f"✓ Clean 9:16 Master ({crop_mode.split()[0]} Crop Applied - Text Safe Zone Upper 20%-45%)", use_container_width=True)
            
            cur_pkg = st.session_state.get("active_video_pkg", {}).get("pkg", {})
            cur_slug = re.sub(r'[^a-zA-Z0-9]+', '_', cur_pkg.get('hook_banner', 'reel')).strip('_').lower()
            thumb_save_name = f"{target_d.replace('-','')}_{cur_slug}_thumb.png"
            st.download_button(f"💾 Download Cleaned Thumbnail ({thumb_save_name})", buf.getvalue(), thumb_save_name, "image/png")
        except Exception as e: 
            st.warning(f"Could not crop thumbnail: {e}")

    if st.button("🎬 Render Master 9:16 Vertical Reel", type="primary"):
        if "active_video_pkg" not in st.session_state:
            st.error("No active draft loaded in Tab 1. Use Quick-Paste Restore or pick from Draft Vault in Tab 1!")
        elif not uploaded_clips or num_clips < 2:
            st.error(f"Please upload at least 2 video clips. (Currently loaded: {num_clips})")
        else:
            with st.spinner(f"⚡ Applying Director cuts & audio ducking across {num_clips} clips..."):
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
                dur = (float(probe.stdout.strip()) if probe.stdout.strip() else 24.0) + 0.6
                
                clip_target_dur = dur / float(num_clips)
                clip_speed = clip_target_dur / 4.0

                ass_p = os.path.join(TMP_DIR, "subtitles.ass")
                build_ass_subtitles(timings, pkg["script"], ass_p, dur, arch_key)
                clean_ass_path = ass_p.replace("'", "\\'").replace(":", "\\:")
                clean_fonts_dir = FONTS_DIR.replace("'", "\\'").replace(":", "\\:")

                banner = pkg.get("hook_banner", "ACTION CURES SELF-PITY").replace("'", "\\'").replace(":", "\\:")
                out_p = os.path.join(TMP_DIR, "master_output.mp4")
                
                active_style = chosen_director_fx
                st.session_state["rendered_director_style"] = active_style

                v_filters = []
                for i in range(num_clips):
                    filters_for_clip = [
                        f"trim=0:4",
                        f"setpts=(PTS-STARTPTS)*{clip_speed:.4f}",
                        f"scale=1120:1980:force_original_aspect_ratio=increase",
                        f"crop=1080:1920:(in_w-1080)/2-10:(in_h-1920)/2-15",
                        f"fps=25"
                    ]
                    
                    # Optional digital zoompan (only if Flow camera motion wasn't used)
                    if i == 0 and apply_digital_zoom:
                        z_step = 0.15 / max(1, (clip_target_dur * 25))
                        filters_for_clip.append(f"zoompan=z='min(zoom+{z_step:.5f},1.15)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=25")

                    # CutCap Transitions between scene cuts
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
                v_filters.append(f"[vb]drawtext=text='{banner}':fontsize=44:fontcolor={arch['banner_hex']}:box=1:boxcolor=black@0.85:boxborderw=18:x=(w-text_w)/2:y=180:enable='between(t,0,3.5)',ass='{clean_ass_path}':fontsdir='{clean_fonts_dir}'[vsub]")
                
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
                        f"[{bgm_idx}:a]aloop=loop=-1:size=2e+09,loudnorm=I={bgm_vol_level}:TP=-2.0:LRA=7,afade=t=out:st={dur-2.0:.1f}:d=2.0[bg_clean];"
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
                    st.success(f"🎉 Master Reel Rendered! Active Style: {CINEMATOGRAPHY_MATRIX.get(active_style, {}).get('label')}")

    if "rendered_video_path" in st.session_state and "active_video_pkg" in st.session_state:
        vp = st.session_state["rendered_video_path"]
        st.video(vp)
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data["pkg"]
        
        # ---------------------------------------------------------
        # GOOGLE DRIVE VAULT & SCHEDULING MECHANISM
        # ---------------------------------------------------------
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
        pl_name = pkg.get("playlist", "Hard Truths")
        pl_code = "SILENCE" if "silence" in pl_name.lower() else ("PARABLES" if "parables" in pl_name.lower() else "TRUTHS")
        slug = re.sub(r'[^a-zA-Z0-9]+', '_', pkg.get('hook_banner', 'reel')).strip('_').lower()
        
        exp_name = f"{c_d}_{slot_code}_{pl_code}_{slug}.mp4"
        folder_name = f"{c_d}_{slot_code}_{pl_code}_{slug}"

        st.info(f"Targeting: **{c_d} @ {c_t} IST ({c_s})**\n\nDrive Folder: `EchoesOfWisdom/01_READY_TO_SCHEDULE/{folder_name}`")

        with open(vp, "rb") as f: vb = f.read()
        st.download_button(f"💾 Download Master Reel ({exp_name})", vb, exp_name, "video/mp4")

        # -------------------------------------------------
        # 🔴 YOUTUBE SHORTS PUBLISHING FLOW
        # -------------------------------------------------
        st.divider()
        st.markdown("### 🔴 1. YOUTUBE SHORTS PUBLISHING FLOW")
        
        raw_hook = pkg.get("hook_banner", "DISCIPLINE OVER COMFORT").title()
        yt_t = pkg.get("youtube_title", f"⚡ {raw_hook} 🏛️ #shorts #stoicism")
        if not yt_t.startswith("⚡"): yt_t = f"⚡ {yt_t}"
        st.text_input("1. YouTube Title (100 char limit)", yt_t, key="yt_t_val")
        render_copy("yt_t", "COPY YOUTUBE TITLE", yt_t)
        
        raw_desc = pkg.get("youtube_description", "").replace("@EchoesOfWisdomOfficial", get_persistent_handle())
        st.text_area("2. YouTube Description", raw_desc, height=140, key="yt_d_val")
        render_copy("yt_d", "COPY YOUTUBE DESCRIPTION", raw_desc)
        
        st.text_input("3. Exact YouTube Playlist Name", pl_name, key="yt_pl_val")
        render_copy("yt_pl", "COPY PLAYLIST NAME", pl_name)
        
        default_tags = "stoicism, echoes of wisdom, stoic quotes, daily stoic, discipline, self improvement, marcus aurelius, mental strength, stoic philosophy, life lessons, shorts, stoic mindset"
        yt_tags = pkg.get("youtube_tags", default_tags)
        st.text_area("4. YouTube Video Tags", yt_tags, height=65, key="yt_tags_val")
        render_copy("yt_tags", "COPY YOUTUBE TAGS", yt_tags)
        
        yt_pin = pkg.get("youtube_pinned_comment", "When facing uninvited chaos: 1️⃣ Stand resolute in silence, or 2️⃣ Defend your territory verbally? Drop 1 or 2 below! 👇")
        st.text_area("5. YouTube Pinned Comment", yt_pin, height=75, key="yt_pin_val")
        render_copy("yt_p", "COPY PINNED COMMENT", yt_pin)

        # -------------------------------------------------
        # 🔵 META REELS PUBLISHING FLOW
        # -------------------------------------------------
        st.divider()
        st.markdown("### 🔵 2. FACEBOOK & INSTAGRAM REELS FLOW")

        raw_fb_hook = pkg.get("caption_hook", pkg.get("hook_banner", "DISCIPLINE OVER COMFORT"))
        fb_hook = to_unicode_bold(re.sub(r"[^\w\s-]", "", raw_fb_hook).strip().upper())
        fb_cap = (
            f"⚡ {fb_hook} 🏛️\n\n"
            f"{pkg.get('caption_lesson', pkg.get('script', ''))}\n\n"
            f"🤔 {pkg.get('debate_question', 'When faced with this choice:')}\n"
            f"1️⃣ {pkg.get('choice_1', 'Maintain silent composure')}\n"
            f"2️⃣ {pkg.get('choice_2', 'Defend your honor verbally')}\n\n"
            f"Drop 1 or 2 below. 👇\n\n"
            f"• Follow {get_persistent_handle()} for timeless clarity.\n\n"
            f"{pkg.get('meta_hashtags', '#StoicMindset #EchoesOfWisdom #Discipline #Reels')}"
        )
        st.text_area("1. Meta Reel Text", fb_cap, height=160, key="fb_cap_val")
        render_copy("fb_c", "COPY META REEL TEXT", fb_cap)

        st.text_input("2. Meta Topic Tags", "Stoicism, Philosophy, Personal Growth, Motivation", key="fb_tags_val")
        render_copy("fb_tags", "COPY META TAGS", "Stoicism, Philosophy, Personal Growth, Motivation")

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
                "metaComment": "What is your perspective on this? Drop 1 or 2 below! 👇",
                "directorFx": CINEMATOGRAPHY_MATRIX.get(director_style_resolved, {}).get("label", "Action Push & Shutter Flash"),
                "notes": "Staged in EchoesOfWisdom/01_READY_TO_SCHEDULE"
            }
            
            # 1. Update local database ledger
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
            
            # 2. Update Excel Tracker file directly on disk
            excel_updated = append_to_excel_tracker(row_payload)
            
            # 3. Optional: Sync to Google Sheets if Webhook is configured
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
tab3.markdown("### Content Tracker & Export")

if os.path.exists(EXCEL_TRACKER_PATH):
    with open(EXCEL_TRACKER_PATH, "rb") as ef:
        tab3.download_button(
            "Download Updated Content Tracker (.xlsx)",
            ef.read(),
            "Echoes_Of_Wisdom_Content_Tracker.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    tab3.caption("Contains all scheduled rows with metadata, tags, and Drive folder links.")
else:
    tab3.info("Excel tracker will initialize automatically on your first locked video.")

tab3.markdown(f"### Scheduled Queue Ledger ({len(db.get('scheduled_videos', []))})")
for item in reversed(db.get("scheduled_videos", [])):
    tab3.markdown(f"""
    <div style="background:#0A0F1D;border:1px solid rgba(56,189,248,0.2);border-radius:8px;padding:8px 12px;margin-bottom:6px;font-family:monospace;font-size:11px;">
        <span style="color:#38BDF8;font-weight:700;">{item.get('date')}</span> @ <span style="color:#FBBF24;">{item.get('time')} IST ({item.get('slot')})</span>
        <div style="color:#F8FAFC;font-weight:600;">{item.get('title')}</div>
        <div style="color:#64748B;">📁 {item.get('file')} | 📺 {item.get('playlist', 'Hard Truths')}</div>
    </div>
    """, unsafe_allow_html=True)
