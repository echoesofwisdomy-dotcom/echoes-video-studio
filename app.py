import os, io, json, re, random, asyncio, subprocess, requests, base64
from datetime import datetime, timedelta, timezone, time
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
import edge_tts

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
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important; 
        color: #E2E8F0 !important; 
        -webkit-font-smoothing: antialiased !important;
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
        letter-spacing: 0.02em !important;
    }
    
    label[data-testid="stWidgetLabel"] p { 
        color: #94A3B8 !important; 
        font-size: 12px !important; 
        font-weight: 700 !important; 
        text-transform: uppercase !important; 
        letter-spacing: 0.04em !important;
    }
    
    .stTextInput>div>div>input, .stTextArea textarea { 
        background-color: #0A0F1D !important; 
        border: 1px solid rgba(56, 189, 248, 0.25) !important; 
        color: #F8FAFC !important; 
        border-radius: 8px !important; 
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 14px !important;
        line-height: 1.6 !important;
    }
    
    .stButton>button[kind="primary"] { 
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 100%) !important; 
        color: #FFF !important; 
        border-radius: 10px !important; 
        height: 3.4rem !important; 
        font-weight: 700 !important; 
        font-size: 14px !important; 
        letter-spacing: 0.02em !important;
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
        gap: 6px; 
        margin: 2px; 
    }
    .badge-green { background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(52, 211, 153, 0.25); }
    .badge-blue  { background: rgba(56, 189, 248, 0.12); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.25); }
    .badge-amber { background: rgba(245, 158, 11, 0.12); color: #FBBF24; border: 1px solid rgba(251, 191, 36, 0.25); }
    .badge-purple{ background: rgba(168, 85, 247, 0.12); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.25); }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. FILE PATHWAYS & PERSISTENCE ANCHORS
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
API_KEY_FILE = os.path.join(DATA_DIR, "gemini_key.txt")

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
    return st.session_state.get("api_key", "").strip()

def save_persistent_api_key(key_val):
    clean = key_val.strip().strip('"').strip("'")
    st.session_state["api_key"] = clean
    try:
        with open(API_KEY_FILE, "w", encoding="utf-8") as f:
            f.write(clean)
    except Exception: pass

SUBTITLE_ARCHETYPES = {
    "IMPERIAL_GOLD": {"label": "👑 Imperial Gold", "ass_primary": "&H0000E5FF", "banner_hex": "0xFFE500", "prefix": "gold_"},
    "GLACIAL_ICE":   {"label": "❄️ Glacial Ice",   "ass_primary": "&H00FFF500", "banner_hex": "0x00F5FF", "prefix": "ice_"},
    "FORGE_AMBER":   {"label": "🔥 Forge Amber",   "ass_primary": "&H000099FF", "banner_hex": "0xFF9900", "prefix": "amber_"}
}

def get_library_tracks():
    """Scans the music/ folder for MP3 audio tracks."""
    if not os.path.exists(MUSIC_DIR):
        return []
    return sorted([f for f in os.listdir(MUSIC_DIR) if f.lower().endswith((".mp3", ".wav", ".m4a"))])

def resolve_background_track(choice_key, archetype_key):
    """Dynamically matches audio files from the music/ folder based on archetype prefix."""
    if choice_key == "NONE":
        return None, "None"
    all_tracks = get_library_tracks()
    if not all_tracks:
        return None, "None"
    
    if choice_key == "AUTO":
        target_prefix = SUBTITLE_ARCHETYPES.get(archetype_key, {}).get("prefix", "gold_")
        matched = [f for f in all_tracks if f.lower().startswith(target_prefix)]
        pool = matched if matched else all_tracks
        chosen_file = random.choice(pool)
        return os.path.join(MUSIC_DIR, chosen_file), chosen_file
    
    if choice_key in all_tracks:
        return os.path.join(MUSIC_DIR, choice_key), choice_key
    return None, "None"

def to_unicode_bold(text):
    """Converts text to mathematical sans-serif bold characters without spacing anomalies."""
    res = []
    for char in text:
        if 'A' <= char <= 'Z':
            res.append(chr(0x1D5D4 + ord(char) - ord('A')))
        elif 'a' <= char <= 'z':
            res.append(chr(0x1D5EE + ord(char) - ord('a')))
        elif '0' <= char <= '9':
            res.append(chr(0x1D7EC + ord(char) - ord('0')))
        else:
            res.append(char)
    return ''.join(res)

# ---------------------------------------------------------
# 3. 24 THEMES & ROTATING METAPHORS MATRIX
# ---------------------------------------------------------
THEMES_DATABASE = [
    # Pillar I: Emotional Immunity
    {"id": "SILENT_EXIT", "p": "Emotional Immunity", "t": "The Silent Exit", "prem": "Never announce when you cut someone off. Withdrawing presence without conflict is sovereign power.", "h": "NEVER ANNOUNCE YOUR EXIT", "a": "GLACIAL_ICE", "m": ["Heavy bronze portal latch locking into dark stone", "Single fraying linen cord burning through over a flame", "Solitary timber skiff drifting into dense lake mist"]},
    {"id": "WEAPON_INDIFFERENCE", "p": "Emotional Immunity", "t": "Weaponized Indifference", "prem": "If their disrespect triggers your anger, they own you. Cold silence strips away their leverage.", "h": "YOUR REACTION GIVES THEM POWER", "a": "GLACIAL_ICE", "m": ["Monolithic basalt stone unmoved against crashing storm waves", "Torrential rain pouring down a marble statue without a scratch", "Glowing ember dropping on cold slate extinguishing to ash"]},
    {"id": "COST_LIKABLE", "p": "Emotional Immunity", "t": "The Cost of Being Likable", "prem": "Trying to please everyone is not kindness; it is weakness. When everyone likes you, nobody respects you.", "h": "STOP TRYING TO BE LIKED", "a": "FORGE_AMBER", "m": ["Weathered antique theater mask cracking on wet cobblestones", "Brittle dried clay seal crumbling under thumb pressure", "Weathered glass lens fracturing under focused sunlight"]},
    {"id": "ARMOR_EPICTETUS", "p": "Emotional Immunity", "t": "The Armor of Epictetus", "prem": "An insult cannot hurt you unless you agree with it. If they mock you, they reveal their own sickness.", "h": "INSULTS ONLY HURT FOOLS", "a": "GLACIAL_ICE", "m": ["Bronze arrow deflecting off a heavy Roman iron shield", "Mud hurled against a granite castle bastion washing away", "Venomous snake striking a solid bronze bell with no effect"]},
    {"id": "GOSSIP_STARVE", "p": "Emotional Immunity", "t": "Gossip Starvation", "prem": "When someone brings you gossip about others, they will talk about you tomorrow. Starve rumors with silence.", "h": "NEVER FEED SMALL MINDS", "a": "GLACIAL_ICE", "m": ["Dark iron snuffer descending over a guttering candle flame", "Dry withered brush caught in sudden rain stopping fire", "Deep stone cistern swallowing a pebble without producing an echo"]},
    {"id": "UNRETURNED_LOYALTY", "p": "Emotional Immunity", "t": "Unreturned Loyalty", "prem": "Blind loyalty to people who only call when they need something is self-betrayal. Close the vault.", "h": "STOP BLEEDING FOR USERS", "a": "FORGE_AMBER", "m": ["Heavy iron vault door swinging shut on oiled hinges", "Cracked clay water vessel leaking water into barren sand", "Withered vine trimmed cleanly from a fruit-bearing olive branch"]},

    # Pillar II: Relentless Focus
    {"id": "DOPAMINE_BANKRUPT", "p": "Relentless Focus", "t": "Dopamine Bankruptcy", "prem": "You are not tired from hard work; you are drained from chasing worthless noise. Guard your stillness fiercely.", "h": "YOU ARE DRAINED BY NOISE", "a": "FORGE_AMBER", "m": ["Antique bronze oil lamp burning steadily down to deep amber embers", "Clear mountain spring water settling completely transparent in a vial", "Iron pendulum slowing to a complete, balanced standstill"]},
    {"id": "QUIET_EXECUTION", "p": "Relentless Focus", "t": "Quiet Execution", "prem": "Never broadcast what you are building. The world flatters plans but only respects finished stone.", "h": "BUILD IN COMPLETE OBSCURITY", "a": "IMPERIAL_GOLD", "m": ["Heavy blacksmith hammer striking glowing blade on dark stone anvil", "Stonemason chisel carving Roman numerals into granite bedrock", "Deep underground tree roots breaking through rock in total darkness"]},
    {"id": "SUNK_COST_TRAP", "p": "Relentless Focus", "t": "The Sunk Cost Trap", "prem": "Just because you spent years making a mistake does not mean you owe it your future. Cut the cord immediately.", "h": "STOP FEEDING DEAD DREAMS", "a": "FORGE_AMBER", "m": ["Sharp pruning sickle cleanly slicing an anchor rope under high tension", "Heavy dry branch snapping off a centuries-old oak in storm winds", "Antique weighing scale dumping heavy slag to return to equilibrium"]},
    {"id": "MYTH_OF_WAITING", "p": "Relentless Focus", "t": "The Myth of Motivation", "prem": "Motivation is a fair-weather friend. Discipline is doing the work even when your emotions protest.", "h": "ACTION CURES SELF-PITY", "a": "FORGE_AMBER", "m": ["Flint and steel striking violently to generate a bright spark", "Heavy waterwheel turning relentlessly against strong river currents", "Team of draft oxen pulling a heavy plow through frost-hardened soil"]},
    {"id": "SOLITUDE_ADVANTAGE", "p": "Relentless Focus", "t": "The Solitude Advantage", "prem": "A man who cannot sit quietly alone is an easy target for anyone promising stimulation.", "h": "LEARN TO SIT IN SILENCE", "a": "IMPERIAL_GOLD", "m": ["Single tall watchtower standing alone on a foggy mountain peak", "Lone golden eagle gliding motionless on thermal winds high above clouds", "Solitary stone lighthouse enduring darkness with a steady beam"]},
    {"id": "ENVY_DESTRUCTION", "p": "Relentless Focus", "t": "The Toxicity of Comparison", "prem": "When you envy another person's victory, you declare that your own journey is worthless. Mind your own craft.", "h": "NEVER WATCH THEIR RACE", "a": "FORGE_AMBER", "m": ["Racehorse wearing blinders charging forward on dry dirt arena", "Craftsman magnifying loupe focusing strictly on fine gold engravings", "Sundial tracking the sun without regard for passing clouds"]},

    # Pillar III: Mental Fortress
    {"id": "FUTURE_RUIN", "p": "Mental Fortress", "t": "The Illusion of Future Ruin", "prem": "We suffer far more in imagination than in reality. The catastrophe keeping you awake will never arrive.", "h": "YOU SUFFER IN YOUR HEAD", "a": "IMPERIAL_GOLD", "m": ["Cold morning mist dissolving over ancient stone arches under sunlight", "Troubled pool of dark water settling into a crystal mirror as ripples fade", "Dark storm cloud dispersing harmlessly across a barren plain"]},
    {"id": "CALAMITY_TRAINING", "p": "Mental Fortress", "t": "Calamity as Training", "prem": "Do not curse the obstacle; the obstacle is your teacher. Adversity produces character comfort cannot buy.", "h": "THE STRUGGLE IS THE TEACHER", "a": "IMPERIAL_GOLD", "m": ["Roaring forge furnace turning raw scrap iron into hardened steel", "Mountain pine tree growing dense and unshakeable in freezing gale winds", "Diamond blade grinding down rough raw stone into a sharp facet"]},
    {"id": "BURDEN_EXPECTATIONS", "p": "Mental Fortress", "t": "The Myth of Fairness", "prem": "The universe owes you nothing. Expecting life to treat you gently because you are good is self- deception.", "h": "THE WORLD OWES YOU NOTHING", "a": "GLACIAL_ICE", "m": ["Jagged granite headland taking crashing ocean waves without yielding", "Desert sandstorm sweeping across an ancient stone obelisk", "Heavy bronze coin falling indifferently on stone whether heads or tails"]},
    {"id": "DEATH_OF_PRIDE", "p": "Mental Fortress", "t": "The Death of Pride", "prem": "Arrogance demands an audience. Real confidence speaks quietly, works without applause, and walks without a strut.", "h": "KILL YOUR NEED FOR PRAISE", "a": "IMPERIAL_GOLD", "m": ["Deep subterranean bedrock supporting an entire city without showing itself", "Dark iron anchor resting silently at the bottom of the ocean floor", "Ancient oak tree whose strength lies in its hidden root network"]},
    {"id": "CONTROL_DESIRE", "p": "Mental Fortress", "t": "The Chains of Wanting", "prem": "Wealth does not consist in great possessions, but in few wants. He who is content cannot be enslaved.", "h": "WANT LESS TO RULE MORE", "a": "IMPERIAL_GOLD", "m": ["Heavy broken iron shackles lying in dust beside an open cell gate", "Simple earthenware cup filled with cool clear mountain well water", "Rustic wooden staff supporting a traveler over rugged mountain ridges"]},
    {"id": "ANGER_POISON", "p": "Mental Fortress", "t": "Anger Is Self-Poison", "prem": "Holding onto anger is drinking poison and expecting the other person to die. Calmness is the ultimate weapon.", "h": "ANGER IS TEMPORARY MADNESS", "a": "GLACIAL_ICE", "m": ["Boiling water in a bronze cauldron cooling down to smooth stillness", "Wild brushfire hitting a wide dirt trench and running out of fuel", "Raging wild stallion brought to stillness by a steady hand on the reins"]},

    # Pillar IV: Radical Acceptance
    {"id": "MEMENTO_MORI", "p": "Radical Acceptance", "t": "Memento Mori", "prem": "You could leave life right now. Let that determine what you do, what you say, and what you think.", "h": "YOU ARE RUNNING OUT OF TIME", "a": "FORGE_AMBER", "m": ["Fine golden sand falling steadily through an ancient hourglass neck", "Shadow lengthening across Roman stone numerals on a sundial face", "Single dried autumn leaf detaching and drifting on a brisk wind"]},
    {"id": "AMOR_FATI", "p": "Radical Acceptance", "t": "Amor Fati", "prem": "Do not demand that things happen as you wish. Accept what happens as necessary and move forward.", "h": "ACCEPT WHATEVER COMES NEXT", "a": "IMPERIAL_GOLD", "m": ["Raging river flowing around boulders without slowing its descent", "Large campfire consuming whatever fuel is thrown into its flames", "Ship sail adjusting its ropes to catch crosswinds and maintain heading"]},
    {"id": "STRIP_PEDESTAL", "p": "Radical Acceptance", "t": "Stripping the Pedestal", "prem": "Never put anyone on a pedestal. They bleed, make mistakes, and age just like you.", "h": "NOBODY IS ABOVE YOU", "a": "GLACIAL_ICE", "m": ["Gilded monument showing exposed cracked limestone under worn gold leaf", "Royal purple woolen mantle turning to simple thread under inspection", "Chess board being cleared where kings and pawns go into the same box"]},
    {"id": "RIVER_OF_TIME", "p": "Radical Acceptance", "t": "The River of Time", "prem": "The pain you feel right now will pass. The victory you celebrate today will fade. Ground your peace in eternity.", "h": "THIS TOO SHALL PASS", "a": "IMPERIAL_GOLD", "m": ["Fast river water rushing over polished river stones under sunlight", "Ancient Roman stone ruins standing tranquil against centuries of weather", "Constellations revolving slowly in clear dark night skies over mountains"]},
    {"id": "DEATH_OF_OPINIONS", "p": "Radical Acceptance", "t": "Irrelevance of Opinions", "prem": "Why value yourself over others, but value their opinion of you over your own judgment? Reclaim your inner court.", "h": "TRUST YOUR OWN JUDGMENT", "a": "IMPERIAL_GOLD", "m": ["Balance scale holding single gold bullion balancing heaps of straw", "Solid bronze compass needle pointing true North in storm winds", "Ancient judge stone bench standing empty and resolute under open skies"]},
    {"id": "FINAL_BOUNDARY", "p": "Radical Acceptance", "t": "The Final Boundary", "prem": "The mind is its own place. No tyrant or insult can break inside unless you leave the gate unlocked.", "h": "GUARD YOUR INNER CITADEL", "a": "GLACIAL_ICE", "m": ["Massive carved stone gateway fortified with heavy bronze bands", "Solitary fortress lantern burning steadily against pitch-black mountain fog", "Deep subterranean spring flowing cold and pure under massive granite arches"]}
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
    d = {"scheduled_videos": [], "used_hooks": [], "used_theme_ids": [], "last_scheduled_date": None, "last_scheduled_slot": None, "slot1_time": "05:00", "slot2_time": "20:00"}
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
    s1_t, s2_t = db.get("slot1_time", "05:00"), db.get("slot2_time", "20:00")
    if ld_str and ls:
        try: ld = datetime.strptime(str(ld_str), "%Y-%m-%d").date()
        except Exception: ld = now_ist.date()
        if "SLOT 1" in str(ls).upper():
            return ld.strftime("%Y-%m-%d"), "SLOT 2 (EVENING)", s2_t
        else:
            return (ld + timedelta(days=1)).strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t
    else:
        td = now_ist.date()
        t1 = time(int(s1_t.split(":")[0]), int(s1_t.split(":")[1]))
        t2 = time(int(s2_t.split(":")[0]), int(s2_t.split(":")[1]))
        if now_ist.time() < t1: return td.strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t
        elif now_ist.time() < t2: return td.strftime("%Y-%m-%d"), "SLOT 2 (EVENING)", s2_t
        else: return (td + timedelta(days=1)).strftime("%Y-%m-%d"), "SLOT 1 (MORNING)", s1_t

target_d, target_s, target_t = get_next_slot()

# ---------------------------------------------------------
# 5. SUBTITLE SYNCHRONIZER (WITH RETRY & FALLBACK)
# ---------------------------------------------------------
async def synthesize_speech_timed(text, audio_path):
    """Synthesizes speech with acoustic word boundaries and automatic retry on handshake drop."""
    max_retries = 3
    last_exception = None
    
    for attempt in range(1, max_retries + 1):
        try:
            comm = edge_tts.Communicate(text, voice="en-GB-RyanNeural", rate="+15%", pitch="-2Hz")
            timings = []
            
            with open(audio_path, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio": 
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        st_s = chunk["offset"] / 10_000_000.0
                        dur_s = chunk["duration"] / 10_000_000.0
                        timings.append({
                            "word": chunk.get("text", ""), 
                            "start": round(st_s, 3), 
                            "end": round(st_s + dur_s, 3)
                        })
            
            if os.path.exists(audio_path) and os.path.getsize(audio_path) > 5000:
                return timings
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                await asyncio.sleep(2.0 * attempt)
            continue
            
    raise RuntimeError(f"Edge-TTS Handshake failed after {max_retries} attempts: {last_exception}")

def build_ass_subtitles(timed_words, script_text, ass_path, total_dur, arch_key="IMPERIAL_GOLD"):
    color = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])["ass_primary"]
    events = []
    
    if timed_words and len(timed_words) >= 5:
        clean_words = []
        for tw in timed_words:
            w_txt = re.sub(r'[^\w\s\',.!?-]', '', tw['word']).upper().strip()
            if w_txt:
                clean_words.append({'word': w_txt, 'start': tw['start'], 'end': tw['end']})

        chunk = []
        for i, tw in enumerate(clean_words):
            chunk.append(tw)
            is_punct = any(tw['word'].endswith(p) for p in ['.', '!', '?', ':', ';'])
            has_pause = (i + 1 < len(clean_words)) and (clean_words[i + 1]['start'] - tw['end'] >= 0.25)
            
            if is_punct or has_pause or len(chunk) >= 3:
                st_t = chunk[0]['start']
                if i + 1 < len(clean_words):
                    en_t = clean_words[i + 1]['start']
                else:
                    en_t = min(total_dur, chunk[-1]['end'] + 0.3)
                
                txt = " ".join([c['word'] for c in chunk]).strip()
                if txt:
                    events.append((st_t, en_t, txt))
                chunk = []
                
        if chunk:
            st_t = chunk[0]['start']
            en_t = min(total_dur, chunk[-1]['end'] + 0.3)
            txt = " ".join([c['word'] for c in chunk]).strip()
            if txt:
                events.append((st_t, en_t, txt))
    else:
        tokens = script_text.split()
        token_groups = [tokens[i:i + 3] for i in range(0, len(tokens), 3)]
        vocal_start = 0.35
        step = max(0.5, (total_dur - vocal_start - 0.4) / max(1, len(token_groups)))
        
        for idx, grp in enumerate(token_groups):
            st_t = vocal_start + (idx * step)
            en_t = min(total_dur, vocal_start + ((idx + 1) * step))
            txt = re.sub(r'[^\w\s\',.!?-]', '', " ".join(grp)).upper().strip()
            if txt:
                events.append((st_t, en_t, txt))

    def fmt(s): return f"{int(s//3600)}:{int((s%3600)//60):02d}:{s%60:05.2f}"
    
    ass_doc = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,76,{color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,50,50,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    for st_t, en_t, txt in events: 
        ass_doc += f"Dialogue: 0,{fmt(st_t)},{fmt(en_t)},Default,,0,0,0,,{txt}\n"
    
    with open(ass_path, "w", encoding="utf-8") as f: 
        f.write(ass_doc)
    return events

# Draft vault loader
if "active_video_pkg" not in st.session_state and os.path.exists(DRAFT_JSON_PATH):
    try:
        with open(DRAFT_JSON_PATH, "r", encoding="utf-8") as f:
            d_data = json.load(f)
        if not os.path.exists(DRAFT_AUDIO_PATH) or os.path.getsize(DRAFT_AUDIO_PATH) < 5000:
            timings = asyncio.run(synthesize_speech_timed(d_data["pkg"]["script"], DRAFT_AUDIO_PATH))
            d_data["timings"] = timings
        d_data["audio"] = DRAFT_AUDIO_PATH
        st.session_state["active_video_pkg"] = d_data
    except Exception: pass

# ---------------------------------------------------------
# 6. GEMINI GENERATOR (ANATOMICAL CONSTRAINTS ENFORCED)
# ---------------------------------------------------------
def generate_video_package(raw_api_key, t_obj, macro_c, sett_obj):
    clean_key = raw_api_key.strip().strip('"').strip("'")
    if not clean_key:
        return None, "API Key is empty. Please enter your Gemini API key in 'API CREDENTIALS'."
    
    try:
        client = genai.Client(api_key=clean_key)
    except Exception as e:
        return None, f"Could not initialize Gemini Client: {str(e)}"
        
    used_h = "\n".join([f"- {h}" for h in db.get("used_hooks", [])[-30:]]) or "None."
    
    prompt = (
        f"You are Creative Director for 'Echoes of Wisdom' (9:16 reels).\n"
        f"PILLAR: {t_obj['p']} | THEME: {t_obj['t']}\nPREMISE: {t_obj['prem']}\nDEFAULT HOOK: {t_obj['h']}\n"
        f"MACRO METAPHOR (SCENE 2): {macro_c}\nENVIRONMENT: {sett_obj['d']}\nFORBIDDEN HOOKS:\n{used_h}\n"
        f"RULES:\n1. Exactly 65-70 words.\n2. Line 1 hook: 3-4 words direct challenge.\n3. Last line seamlessly loops to line 1.\n"
        f"4. Google Flow Character Rules (STRICT ANATOMICAL ENFORCEMENT):\n"
        f"   - Character description MUST be: 'An original fictional mature man with a weathered lined face, calm focused eyes, messy salt-and-pepper hair, thick beard, draped in an authentic dark woolen ancient mantle.'\n"
        f"   - ANATOMY CONSTRAINTS: Strictly two arms and two hands only. Hands resting calmly inside the deep woolen mantle folds or clasped at waist level. Flawless human anatomy, no phantom limbs, no extra hands or fingers emerging from fabric folds.\n"
        f"   - Composure: Dignified silent composure, serene stoic expression, calm steady gaze.\n"
        f"5. Prompt Formatting: All video prompts must start with '[4-second vertical 9:16 cinematic video clip]'.\n"
        f"OUTPUT STRICT JSON ONLY:\n"
        "{\n"
        '  "title_concept": "Short Concept Title",\n'
        '  "hook_banner": "3-4 WORDS IN CAPS",\n'
        f'  "subtitle_archetype": "{t_obj["a"]}",\n'
        '  "script": "Full 65-70 word script.",\n'
        '  "scene1_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 1 protagonist in setting, hands resting inside woolen mantle, flawless anatomy, strictly two arms",\n'
        f'  "scene2_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 2 macro ({macro_c})",\n'
        '  "scene3_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 3 protagonist action, natural posture, no phantom limbs",\n'
        '  "scene4_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 4 protagonist close up, serene resolve",\n'
        '  "thumbnail_prompt": "High-contrast 9:16 portrait in setting with bold hook text suggestion, anatomically correct",\n'
        '  "youtube_title": "High CTR Title #shorts #stoicism",\n'
        '  "youtube_description": "Description with handles and hashtags",\n'
        '  "youtube_pinned_comment": "Binary debate question with 1️⃣/2️⃣ options",\n'
        '  "facebook_title": "Facebook Title",\n'
        '  "caption_hook": "PUNCHY 4-6 WORD HOOK",\n'
        '  "caption_lesson": "Two sentences of wisdom.",\n'
        '  "debate_question": "When faced with this choice:",\n'
        '  "choice_1": "Stoic action",\n'
        '  "choice_2": "Impulsive action",\n'
        '  "facebook_hashtags": "#StoicMindset #EchoesOfWisdom #Discipline #Reels"\n'
        "}"
    )

    models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]
    last_err = ""
    for m in models_to_try:
        try:
            r = client.models.generate_content(
                model=m, 
                contents=prompt, 
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.85)
            )
            parsed = json.loads(r.text)
            if "script" in parsed: 
                return parsed, None
        except Exception as err:
            last_err = str(err)
            continue
            
    return None, f"Gemini Error ({last_err[:120]}...). Please verify your API Key."

# ---------------------------------------------------------
# 7. TELEMETRY BAR & CADENCE MANAGER
# ---------------------------------------------------------
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 600;">v4.0 // PRODUCTION REEL ENGINE</span>
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

with st.expander("📅 PUBLISHING CADENCE & SETTINGS"):
    c1, c2 = st.columns(2)
    saved_d = datetime.strptime(db["last_scheduled_date"], "%Y-%m-%d").date() if db.get("last_scheduled_date") else datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    with c1:
        cd = st.date_input("Last Scheduled Date", value=saved_d)
        cs = st.selectbox("Last Slot", ["SLOT 1 (MORNING)", "SLOT 2 (EVENING)"], index=(0 if "SLOT 1" in str(db.get("last_scheduled_slot","")).upper() else 1))
    with c2:
        ct1 = st.time_input("Slot 1 (IST)", value=time(int(db.get("slot1_time","05:00").split(":")[0]), int(db.get("slot1_time","05:00").split(":")[1])))
        ct2 = st.time_input("Slot 2 (IST)", value=time(int(db.get("slot2_time","20:00").split(":")[0]), int(db.get("slot2_time","20:00").split(":")[1])))
    if st.button("💾 Save Cadence"):
        db.update({"last_scheduled_date": cd.strftime("%Y-%m-%d"), "last_scheduled_slot": cs, "slot1_time": ct1.strftime("%H:%M"), "slot2_time": ct2.strftime("%H:%M")})
        save_db(db)
        nd, ns, nt = get_next_slot(db["last_scheduled_date"], db["last_scheduled_slot"])
        st.session_state["status_banner"] = f"Cadence locked! Next: {nd} @ {nt} IST ({ns})"
        st.rerun()

curr_saved_key = get_persistent_api_key()
with st.expander("🔑 API CREDENTIALS", expanded=(not bool(curr_saved_key))):
    uk = st.text_input("Gemini API Key", value=curr_saved_key, type="password", placeholder="AIzaSy...")
    if uk and uk != curr_saved_key:
        save_persistent_api_key(uk)
        st.success("API key stored securely in vault!")

def render_copy(bid, label, text):
    b64_val = base64.b64encode(text.encode('utf-8')).decode('utf-8')
    components.html(f"""
    <div style="margin: 0; padding: 0;">
        <button id="b_{bid}" onclick="copyFromB64('{bid}', '{b64_val}', '{label}')" style="width:100%;height:2.6rem;background:rgba(56,189,248,0.12);color:#38BDF8;border:1px solid rgba(56,189,248,0.35);border-radius:8px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-weight:700;font-size:12px;cursor:pointer;letter-spacing:0.02em;transition:all 0.2s;">
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
# 8. WORKSPACE TABS
# ---------------------------------------------------------
tab1, tab2, tab3 = st.tabs(["⚡ 1. SCRIPT & PROMPTS", "🎬 2. RENDER MASTER REEL", "📋 3. QUEUE LEDGER"])

# --- TAB 1: SCRIPT & GOOGLE FLOW PROMPTS ---
with tab1:
    theme_opts = ["🎲 Smart AI Rotation (Cooldown-Protected)"] + THEMES_DATABASE
    chosen_theme = st.selectbox("Stoic Core Theme", theme_opts, format_func=lambda x: "🎲 Smart AI Rotation" if isinstance(x, str) else f"{'⏳' if x['id'] in recent_ids else '✨'} {x['t']} ({x['p']})")
    col_s1, col_s2 = st.columns(2)
    with col_s1: chosen_setting = st.selectbox("Cinematic Setting", ["🎲 Random Environment"] + [s["n"] for s in SETTINGS_MATRIX])
    with col_s2: chosen_arch = st.selectbox("Subtitle Color", ["🤖 Match Theme Archetype"] + list(SUBTITLE_ARCHETYPES.keys()), format_func=lambda x: "🤖 Match Archetype" if x.startswith("🤖") else SUBTITLE_ARCHETYPES[x]["label"])

    if st.button("🚀 Synthesize Fresh Stoic Package", type="primary"):
        k = get_persistent_api_key()
        if not k: 
            st.error("Please enter your Gemini API Key in the '🔑 API CREDENTIALS' accordion above.")
        else:
            with st.spinner("⚡ Synthesizing script & timed narration..."):
                t_obj = random.choice([t for t in THEMES_DATABASE if t["id"] not in recent_ids] or THEMES_DATABASE) if isinstance(chosen_theme, str) else chosen_theme
                s_obj = random.choice(SETTINGS_MATRIX) if chosen_setting.startswith("🎲") else next(s for s in SETTINGS_MATRIX if s["n"] == chosen_setting)
                m_choice = random.choice(t_obj["m"])
                pkg, err = generate_video_package(k, t_obj, m_choice, s_obj)
                if err or not pkg: 
                    st.error(f"Synthesis Failed: {err}")
                else:
                    pkg["subtitle_archetype"] = chosen_arch if not chosen_arch.startswith("🤖") else t_obj["a"]
                    
                    try:
                        timings = asyncio.run(synthesize_speech_timed(pkg["script"], DRAFT_AUDIO_PATH))
                    except Exception as tts_err:
                        st.error(f"Voiceover Synthesis Warning: {tts_err}. Please click 'Synthesize Fresh Stoic Package' once more to retry the connection.")
                        st.stop()
                    
                    draft_data = {
                        "pkg": pkg,
                        "t_id": t_obj["id"],
                        "p": t_obj["p"],
                        "m": m_choice,
                        "s": s_obj["n"],
                        "audio": DRAFT_AUDIO_PATH,
                        "timings": timings,
                        "date": target_d,
                        "slot": target_s,
                        "time": target_t
                    }
                    with open(DRAFT_JSON_PATH, "w", encoding="utf-8") as f:
                        json.dump(draft_data, f, indent=2)
                    st.session_state["active_video_pkg"] = draft_data
                    st.session_state.pop("rendered_video_path", None)
                    st.success(f"Locked to Cloud Draft Vault! {t_obj['t']} | {s_obj['n']}")

    if "active_video_pkg" in st.session_state:
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data.get("pkg", {})
        st.divider()
        st.subheader(f"📜 Concept: {pkg.get('title_concept', 'Stoic Reel')}")
        st.markdown(f"**Pillar:** {p_data.get('p', 'Relentless Focus')} &nbsp;|&nbsp; **Palette:** {SUBTITLE_ARCHETYPES.get(pkg.get('subtitle_archetype', 'FORGE_AMBER'), SUBTITLE_ARCHETYPES['FORGE_AMBER'])['label']}")
        st.markdown(f"**Setting:** {p_data.get('s', 'Citadel Colonnades')}")
        st.markdown(f"**Scene 2 Metaphor:** {p_data.get('m', 'Flint and steel')}")
        st.info(f"🎯 **Hook:** {pkg.get('hook_banner')}\n\n🗣️ **Script:**\n\n*{pkg.get('script')}*")
        
        if os.path.exists(DRAFT_AUDIO_PATH):
            st.audio(DRAFT_AUDIO_PATH)
        
        st.markdown("### 📋 Copy Google Flow Prompts")
        for i, (lbl, k) in enumerate([("SCENE 1 (Hook)", "scene1_prompt"), ("SCENE 2 (Macro)", "scene2_prompt"), ("SCENE 3 (Action)", "scene3_prompt"), ("SCENE 4 (Resolve)", "scene4_prompt"), ("THUMBNAIL (9:16)", "thumbnail_prompt")]):
            st.text_area(lbl, pkg.get(k, ""), height=70)
            render_copy(f"pr_{i}", f"COPY {lbl}", pkg.get(k, ""))

        if st.button("🗑️ Discard Draft & Start Fresh"):
            if os.path.exists(DRAFT_JSON_PATH): os.remove(DRAFT_JSON_PATH)
            if os.path.exists(DRAFT_AUDIO_PATH): os.remove(DRAFT_AUDIO_PATH)
            st.session_state.pop("active_video_pkg", None)
            st.session_state.pop("rendered_video_path", None)
            st.rerun()

# --- TAB 2: COMPOSE & RENDER MASTER REEL ---
with tab2:
    st.markdown("### 📥 1. Upload Your 4 Google Flow Clips")
    uploaded_clips = st.file_uploader(
        "Drop all 4 clips (scene1.mp4 to scene4.mp4)",
        type=["mp4", "mov"],
        accept_multiple_files=True
    )

    if uploaded_clips:
        uploaded_clips = sorted(uploaded_clips, key=lambda x: x.name)
        st.markdown(f'<div style="color: {"#34D399" if len(uploaded_clips) == 4 else "#FBBF24"}; font-family: -apple-system, sans-serif; font-size: 13px; font-weight: 600; margin-bottom: 8px;">📁 Files loaded: {len(uploaded_clips)}/4 — {", ".join([c.name for c in uploaded_clips])}</div>', unsafe_allow_html=True)

    st.markdown("### 🎵 2. Dynamic Background Audio (EBU R128 + Auto-Ducking)")
    current_arch_key = st.session_state.get("active_video_pkg", {}).get("pkg", {}).get("subtitle_archetype", "FORGE_AMBER")
    
    avail_tracks = get_library_tracks()
    bgm_options = {
        "AUTO": f"🤖 Auto-Match Theme ({SUBTITLE_ARCHETYPES.get(current_arch_key, {})['label']})",
        "NONE": "🔇 Narration Only (Silent background)",
        "UPLOAD": "📁 Upload New MP3 File"
    }
    for t in avail_tracks:
        bgm_options[t] = f"🎵 {t}"

    col_bg1, col_bg2 = st.columns([3, 2])
    with col_bg1:
        chosen_bgm_mode = st.selectbox("Background Music Source", list(bgm_options.keys()), format_func=lambda x: bgm_options[x])
    with col_bg2:
        bgm_vol_level = st.slider("Music Bed Loudness", min_value=-36, max_value=-22, value=-28, step=1, help="-28 LUFS is broadcast standard. Sidechain auto-ducks during speech.")

    custom_music_file = None
    if chosen_bgm_mode == "UPLOAD" or len(avail_tracks) == 0:
        custom_music_file = st.file_uploader("Upload / Direct-Add MP3 Track to Vault", type=["mp3"])
        if custom_music_file:
            save_dest = os.path.join(MUSIC_DIR, custom_music_file.name)
            with open(save_dest, "wb") as f:
                f.write(custom_music_file.read())
            st.success(f"✓ Saved '{custom_music_file.name}' to music library!")
            st.rerun()

    # Track readiness indicator
    res_path, res_name = resolve_background_track(chosen_bgm_mode, current_arch_key)
    if res_path and os.path.exists(res_path):
        st.markdown(f'<div style="color: #34D399; font-family: -apple-system, sans-serif; font-size: 12px; font-weight: 600; margin-top: -6px; margin-bottom: 8px;">✓ Active Background Track: {res_name}</div>', unsafe_allow_html=True)
    elif chosen_bgm_mode != "NONE":
        st.markdown(f'<div style="color: #FBBF24; font-family: -apple-system, sans-serif; font-size: 12px; font-weight: 600; margin-top: -6px; margin-bottom: 8px;">ℹ️ Library empty ({len(avail_tracks)} tracks). Upload an MP3 above or commit tracks to GitHub.</div>', unsafe_allow_html=True)

    st.markdown("### 🖼️ 3. Thumbnail Watermark Elimination (Lossless Aspect-Ratio Crop)")
    thumb = st.file_uploader("Upload raw Google Flow thumbnail", type=["png", "jpg", "jpeg", "webp"])
    if thumb:
        try:
            im = Image.open(thumb).convert("RGB")
            w, h = im.size
            crop_h = h - int(h * 0.055)
            target_aspect = 9.0 / 16.0
            crop_w = int(crop_h * target_aspect)
            margin_x = (w - crop_w) // 2
            
            clean_im = im.crop((margin_x, 0, margin_x + crop_w, crop_h)).resize((1080, 1920), Image.Resampling.LANCZOS)
            
            buf = io.BytesIO()
            clean_im.save(buf, format="PNG", quality=98)
            st.download_button("💾 Download Cleaned Master Thumbnail", buf.getvalue(), f"{target_d.replace('-','')}_clean_thumbnail.png", "image/png")
            st.caption("✓ Bottom watermark cleanly cropped out; true 9:16 vertical framing preserved with zero patch boxes.")
        except Exception as e: 
            st.warning(f"Could not crop thumbnail: {e}")

    if st.button("🎬 Render Master 9:16 Vertical Reel", type="primary"):
        if "active_video_pkg" not in st.session_state:
            st.error("No active draft loaded in Tab 1.")
        elif not uploaded_clips or len(uploaded_clips) < 4:
            st.error(f"Please upload all 4 clips above. (Currently loaded: {len(uploaded_clips) if uploaded_clips else 0}/4)")
        else:
            with st.spinner("⚡ Normalizing audio loudness, syncing subtitles & rendering 1080x1920 reel..."):
                p_data = st.session_state["active_video_pkg"]
                pkg = p_data["pkg"]
                a_path = DRAFT_AUDIO_PATH
                arch_key = pkg.get("subtitle_archetype", "FORGE_AMBER")
                arch = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["FORGE_AMBER"])
                
                timings = p_data.get("timings", [])
                if not timings or len(timings) < 5:
                    try:
                        timings = asyncio.run(synthesize_speech_timed(pkg["script"], a_path))
                        p_data["timings"] = timings
                    except Exception as e:
                        pass

                c_paths = []
                for idx, c in enumerate(uploaded_clips[:4]):
                    cp = os.path.join(TMP_DIR, f"clip_{idx}.mp4")
                    with open(cp, "wb") as f: f.write(c.read())
                    c_paths.append(cp)

                probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', a_path], capture_output=True, text=True)
                dur = (float(probe.stdout.strip()) if probe.stdout.strip() else 24.0) + 0.6
                speed = (dur / 4.0) / 4.0

                ass_p = os.path.join(TMP_DIR, "subtitles.ass")
                build_ass_subtitles(timings, pkg["script"], ass_p, dur, arch_key)
                clean_ass_path = ass_p.replace("'", "\\'").replace(":", "\\:")
                clean_fonts_dir = FONTS_DIR.replace("'", "\\'").replace(":", "\\:")

                banner = pkg.get("hook_banner", "ACTION CURES SELF-PITY").replace("'", "\\'").replace(":", "\\:")
                out_p = os.path.join(TMP_DIR, "master_output.mp4")
                
                v_filters = [
                    f"[0:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v0];",
                    f"[1:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v1];",
                    f"[2:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v2];",
                    f"[3:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v3];",
                    f"[v0][v1][v2][v3]concat=n=4:v=1:a=0[vb];",
                    f"[vb]drawtext=text='{banner}':fontsize=44:fontcolor={arch['banner_hex']}:box=1:boxcolor=black@0.85:boxborderw=18:x=(w-text_w)/2:y=180:enable='between(t,0,3.5)',ass='{clean_ass_path}':fontsdir='{clean_fonts_dir}'[vsub]"
                ]
                
                inputs = ['-i', c_paths[0], '-i', c_paths[1], '-i', c_paths[2], '-i', c_paths[3], '-i', a_path]
                
                logo = "logo.png" if os.path.exists("logo.png") else None
                if logo:
                    inputs.extend(['-i', logo])
                    v_filters.append(";[5:v]scale=120:-1,format=rgba[ls];[vsub][ls]overlay=W-w-50:150[vout]")
                else: 
                    v_filters.append(";[vsub]copy[vout]")

                active_bgm_path = None
                if chosen_bgm_mode == "UPLOAD" and custom_music_file:
                    active_bgm_path = os.path.join(MUSIC_DIR, custom_music_file.name)
                else:
                    active_bgm_path, _ = resolve_background_track(chosen_bgm_mode, arch_key)

                # Voiceover split: maintains audio presence and triggers music ducking
                if active_bgm_path and os.path.exists(active_bgm_path):
                    inputs.extend(['-i', active_bgm_path])
                    midx = 6 if logo else 5
                    v_filters.append(
                        f";[4:a]loudnorm=I=-14:TP=-1.0:LRA=7,asplit=2[vo_out][vo_sc];"
                        f"[{midx}:a]aloop=loop=-1:size=2e+09,loudnorm=I={bgm_vol_level}:TP=-2.0:LRA=7,afade=t=out:st={dur-2.0:.1f}:d=2.0[bg_clean];"
                        f"[bg_clean][vo_sc]sidechaincompress=threshold=0.08:ratio=4:attack=50:release=350[bg_ducked];"
                        f"[vo_out][bg_ducked]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
                    )
                else: 
                    v_filters.append(";[4:a]loudnorm=I=-14:TP=-1.0:LRA=7[aout]")

                res = subprocess.run([
                    'ffmpeg', '-y', *inputs, 
                    '-filter_complex', "".join(v_filters), 
                    '-map', '[vout]', '-map', '[aout]', 
                    '-t', str(dur), 
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', 
                    '-c:a', 'aac', '-b:a', '192k', 
                    '-pix_fmt', 'yuv420p', out_p
                ], capture_output=True, text=True)
                
                if res.returncode != 0: 
                    st.error(f"FFmpeg Compilation Error: {res.stderr[:300]}")
                else:
                    st.session_state["rendered_video_path"] = out_p
                    st.success(f"🎉 Master Reel Rendered! Subtitles: {arch['label']} (Dynamic Audio Leveled)")

    if "rendered_video_path" in st.session_state and "active_video_pkg" in st.session_state:
        vp = st.session_state["rendered_video_path"]
        st.video(vp)
        p_data = st.session_state["active_video_pkg"]
        pkg = p_data["pkg"]
        c_d = p_data.get("date", target_d)
        c_s = p_data.get("slot", target_s)
        c_t = p_data.get("time", target_t)
        active_pillar = p_data.get("p", "Relentless Focus")
        
        PLAYLIST_MAP = {
            "Emotional Immunity": "Echoes of Wisdom | Emotional Immunity & Boundaries",
            "Relentless Focus": "Echoes of Wisdom | Relentless Focus & Execution",
            "Mental Fortress": "Echoes of Wisdom | Mental Fortress & Resilience",
            "Radical Acceptance": "Echoes of Wisdom | Radical Acceptance & Amor Fati"
        }
        yt_playlist = PLAYLIST_MAP.get(active_pillar, "Echoes of Wisdom | Timeless Stoicism")

        slug = re.sub(r'[^a-zA-Z0-9]+', '_', pkg.get('hook_banner', 'reel')).strip('_').lower()
        exp_name = f"{c_d.replace('-','')}_{slug}.mp4"

        with open(vp, "rb") as f: vb = f.read()
        st.download_button(f"💾 Download Master Reel ({exp_name})", vb, exp_name, "video/mp4")

        st.divider()
        st.markdown(f"### 🎯 QUEUE: {c_d} @ {c_t} IST ({c_s})")
        
        # -------------------------------------------------
        # YOUTUBE SHORTS SUITE (WITH PLAYLIST & PINNED COMMENT)
        # -------------------------------------------------
        st.markdown("#### 🔴 YOUTUBE SHORTS SUITE")
        
        st.text_input("YouTube Playlist", yt_playlist, key="yt_pl_val")
        render_copy("yt_pl", "COPY PLAYLIST NAME", yt_playlist)

        yt_t = pkg.get("youtube_title", f"{pkg.get('hook_banner', 'Stoic Wisdom').title()} #shorts #stoicism")
        st.text_input("YouTube Title", yt_t, key="yt_t_val")
        render_copy("yt_t", "COPY YOUTUBE TITLE", yt_t)
        
        yt_d = pkg.get("youtube_description", f"{pkg.get('script', '')}\n\nSubscribe to @EchoesOfWisdomOfficial\n#stoicism #shorts")
        st.text_area("YouTube Description", yt_d, height=110, key="yt_d_val")
        render_copy("yt_d", "COPY YOUTUBE DESCRIPTION", yt_d)
        
        yt_pin = pkg.get("youtube_pinned_comment", "When facing this moment: 1️⃣ Stand resolute in silence, or 2️⃣ React immediately? Drop 1 or 2 below. 👇")
        st.text_area("YouTube Pinned Debate Comment", yt_pin, height=75, key="yt_pin_val")
        render_copy("yt_p", "COPY PINNED COMMENT", yt_pin)

        # -------------------------------------------------
        # FACEBOOK & INSTAGRAM REELS SUITE
        # -------------------------------------------------
        st.markdown("#### 🔵 FACEBOOK & INSTAGRAM REELS SUITE")
        
        fb_t = pkg.get("facebook_title", f"{pkg.get('hook_banner', 'Stoic Reel').title()} | Stoic Wisdom")
        st.text_input("Facebook Reel Title", fb_t, key="fb_t_val")
        render_copy("fb_t", "COPY FACEBOOK TITLE", fb_t)

        raw_fb_hook = pkg.get("caption_hook", pkg.get("hook_banner", "DISCIPLINE OVER COMFORT"))
        fb_hook = to_unicode_bold(re.sub(r'[^\w\s-]', '', raw_fb_hook).strip().upper())
        fb_cap = (
            f"⚡ {fb_hook} 🏛️\n\n"
            f"{pkg.get('caption_lesson', pkg.get('script', ''))}\n\n"
            f"🤔 {pkg.get('debate_question', 'When faced with this choice:')}\n"
            f"1️⃣ {pkg.get('choice_1', 'Maintain silent composure')}\n"
            f"2️⃣ {pkg.get('choice_2', 'Defend your honor verbally')}\n\n"
            f"Drop 1 or 2 below. 👇\n\n"
            f"• Follow @EchoesOfWisdomOfficial for timeless clarity.\n\n"
            f"{pkg.get('facebook_hashtags', '#StoicMindset #EchoesOfWisdom #Discipline #Reels')}"
        )
        st.text_area("Facebook Reel Caption (Unicode Bold)", fb_cap, height=160, key="fb_cap_val")
        render_copy("fb_c", "COPY FACEBOOK CAPTION", fb_cap)

        st.markdown('''
        <div style="margin: 12px 0 16px 0;">
            <a href="https://business.facebook.com/latest/reels_composer" target="_blank" style="text-decoration: none;">
                <button style="width: 100%; height: 3.2rem; background: #1877F2; color: white; border: none; border-radius: 8px; font-weight: 700; font-family: -apple-system, sans-serif; font-size: 13px; cursor: pointer; box-shadow: 0 4px 15px rgba(24, 119, 242, 0.35);">
                    🌐 OPEN META REELS COMPOSER (9:16 NATIVE)
                </button>
            </a>
        </div>
        ''', unsafe_allow_html=True)

        if st.button("✅ Lock & Advance Slot", type="primary"):
            db["scheduled_videos"].append({"date": c_d, "slot": c_s, "time": c_t, "theme_id": p_data.get("t_id", "THEME_CUSTOM"), "title": yt_t, "file": exp_name})
            if p_data.get("t_id") and p_data["t_id"] not in db.get("used_theme_ids", []): db.setdefault("used_theme_ids", []).append(p_data["t_id"])
            if pkg.get("hook_banner") not in db.get("used_hooks", []): db.setdefault("used_hooks", []).append(pkg.get("hook_banner"))
            db["last_scheduled_date"], db["last_scheduled_slot"] = c_d, c_s
            save_db(db)
            
            if os.path.exists(DRAFT_JSON_PATH): os.remove(DRAFT_JSON_PATH)
            if os.path.exists(DRAFT_AUDIO_PATH): os.remove(DRAFT_AUDIO_PATH)
            
            nd, ns, nt = get_next_slot(c_d, c_s)
            st.session_state["status_banner"] = f"✓ LOCKED: {exp_name} scheduled! Next slot: {nd} @ {nt} IST ({ns})"
            st.session_state.pop("rendered_video_path", None)
            st.session_state.pop("active_video_pkg", None)
            st.rerun()

# --- TAB 3: QUEUE LEDGER ---
with tab3:
    st.markdown(f"### 📋 Scheduled Queue ({len(db.get('scheduled_videos', []))})")
    for item in reversed(db.get("scheduled_videos", [])):
        st.markdown(f"""
        <div style="background:#0A0F1D;border:1px solid rgba(56,189,248,0.2);border-radius:8px;padding:8px 12px;margin-bottom:6px;font-family:monospace;font-size:11px;">
            <span style="color:#38BDF8;font-weight:700;">{item.get('date')}</span> @ <span style="color:#FBBF24;">{item.get('time')} IST ({item.get('slot')})</span>
            <div style="color:#F8FAFC;font-weight:600;">{item.get('title')}</div>
            <div style="color:#64748B;">📁 {item.get('file')} | 🏷️ {item.get('theme_id')}</div>
        </div>
        """, unsafe_allow_html=True)
