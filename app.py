import os
import io
import json
import re
import random
import asyncio
import subprocess
from datetime import datetime, timedelta, timezone, time
import requests
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import streamlit as st
import streamlit.components.v1 as components
from google import genai
from google.genai import types
import edge_tts

# ---------------------------------------------------------
# 1. PAGE SETUP & DARK OBSIDIAN UI
# ---------------------------------------------------------
st.set_page_config(
    page_title="Echoes Video Studio // Terminal",
    page_icon="🎬",
    layout="centered",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    header[data-testid="stHeader"] {
        background: transparent !important;
        height: 2.5rem !important;
    }

    .stApp {
        background-color: #080B11 !important;
        background-image: radial-gradient(circle at 50% -20%, #151e33 0%, #080B11 75%) !important;
        font-family: 'Space Grotesk', -apple-system, sans-serif !important;
        color: #E2E8F0 !important;
    }
    
    .block-container {
        padding-top: 4.2rem !important;
        padding-bottom: 3.5rem !important;
        max-width: 680px !important;
    }

    div[data-testid="stExpander"] {
        background: #0E1626 !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 12px !important;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.5) !important;
        overflow: hidden !important;
        margin-bottom: 1rem !important;
    }
    
    div[data-testid="stExpander"] summary {
        background: #111B30 !important;
        color: #38BDF8 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 13px !important;
        font-weight: 700 !important;
        letter-spacing: 0.05em !important;
        padding: 12px 16px !important;
        border-bottom: 1px solid rgba(56, 189, 248, 0.15) !important;
    }

    div[data-testid="stExpander"] summary:hover {
        color: #7DD3FC !important;
    }

    label[data-testid="stWidgetLabel"] p, .stTextInput label p, .stSelectbox label p, .stDateInput label p, .stTimeInput label p {
        color: #94A3B8 !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 11px !important;
        font-weight: 700 !important;
        letter-spacing: 0.06em !important;
        text-transform: uppercase !important;
    }

    div[data-baseweb="select"] > div {
        background-color: #0A0F1D !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
    }

    .stTextInput>div>div>input, .stTextArea textarea, .stDateInput input, .stTimeInput input {
        background-color: #0A0F1D !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 8px !important;
        color: #F8FAFC !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 14px !important;
    }

    .stButton>button[kind="primary"] {
        background: linear-gradient(135deg, #0284C7 0%, #0369A1 50%, #075985 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(56, 189, 248, 0.4) !important;
        border-radius: 10px !important;
        height: 3.4rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
        box-shadow: 0 0 25px rgba(2, 132, 199, 0.35) !important;
    }

    .stButton>button:not([kind="primary"]) {
        background: #111B30 !important;
        color: #E2E8F0 !important;
        border: 1px solid rgba(56, 189, 248, 0.25) !important;
        border-radius: 8px !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 600 !important;
        font-size: 13px !important;
    }

    .stButton>button:not([kind="primary"]):hover {
        background: #172544 !important;
        color: #38BDF8 !important;
        border-color: #38BDF8 !important;
        box-shadow: 0 0 18px rgba(56, 189, 248, 0.35) !important;
    }

    .stDownloadButton>button {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: white !important;
        border: 1px solid rgba(52, 211, 153, 0.4) !important;
        border-radius: 10px !important;
        height: 3.2rem !important;
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        box-shadow: 0 0 20px rgba(5, 150, 105, 0.3) !important;
    }

    .telemetry-bar {
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 16px;
    }
    .badge {
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        font-weight: 600;
        padding: 5px 12px;
        border-radius: 6px;
        letter-spacing: 0.05em;
        display: inline-flex;
        align-items: center;
        gap: 6px;
    }
    .badge-green { background: rgba(16, 185, 129, 0.12); color: #34D399; border: 1px solid rgba(52, 211, 153, 0.25); }
    .badge-blue  { background: rgba(56, 189, 248, 0.12); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.25); }
    .badge-amber { background: rgba(245, 158, 11, 0.12); color: #FBBF24; border: 1px solid rgba(251, 191, 36, 0.25); }
    .badge-purple{ background: rgba(168, 85, 247, 0.12); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.25); }
    .dot { width: 6px; height: 6px; border-radius: 50%; background-color: #34D399; box-shadow: 0 0 8px #34D399; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. WORKSPACE, FONT FOUNDRY & HELPERS
# ---------------------------------------------------------
DATA_DIR = os.path.join(os.getcwd(), "data")
TMP_DIR = os.path.join(os.getcwd(), "tmp")
FONTS_DIR = os.path.join(os.getcwd(), "fonts")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)
os.makedirs(FONTS_DIR, exist_ok=True)

@st.cache_resource(show_spinner=False)
def ensure_dejavu_font():
    font_target = os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")
    if not os.path.exists(font_target) or os.path.getsize(font_target) < 10000:
        urls = [
            "https://raw.githubusercontent.com/dejavu-fonts/dejavu-fonts/master/ttf/DejaVuSans-Bold.ttf",
            "https://github.com/google/fonts/raw/main/apache/roboto/Roboto-Bold.ttf"
        ]
        for u in urls:
            try:
                r = requests.get(u, timeout=8)
                if r.status_code == 200 and len(r.content) > 10000:
                    with open(font_target, "wb") as f:
                        f.write(r.content)
                    break
            except Exception:
                pass
    return font_target

ensure_dejavu_font()

def to_unicode_bold(text):
    normal_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
    bold_chars   = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    trans = str.maketrans(normal_chars, bold_chars)
    return text.translate(trans)

SUBTITLE_ARCHETYPES = {
    "IMPERIAL_GOLD": {
        "label": "👑 Imperial Gold (Sovereignty & Power)",
        "ass_primary": "&H0000E5FF",
        "banner_hex": "0xFFE500"
    },
    "GLACIAL_ICE": {
        "label": "❄️ Glacial Ice (Detachment & Boundaries)",
        "ass_primary": "&H00FFF500",
        "banner_hex": "0x00F5FF"
    },
    "FORGE_AMBER": {
        "label": "🔥 Forge Amber (Discipline & Raw Truth)",
        "ass_primary": "&H000099FF",
        "banner_hex": "0xFF9900"
    }
}

# ---------------------------------------------------------
# 3. 24-THEME MATRIX ACROSS 4 STOIC PILLARS
# ---------------------------------------------------------
THEMES_DATABASE = [
    # --- PILLAR 1: EMOTIONAL IMMUNITY & BOUNDARIES ---
    {
        "id": "THEME_SILENT_EXIT",
        "pillar": "Emotional Immunity",
        "theme": "The Silent Exit (Outgrowing Disrespect)",
        "premise": "Never announce when you cut someone off. Withdrawing presence without conflict is the ultimate boundary.",
        "hook_starter": "NEVER ANNOUNCE YOUR EXIT",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "An ancient heavy bronze portal latch locking smoothly into dark weathered stone",
            "A single fraying linen cord burning through over a flame and separating silently",
            "A solitary timber skiff drifting into dense lake mist with no oars"
        ]
    },
    {
        "id": "THEME_WEAPONIZED_INDIFFERENCE",
        "pillar": "Emotional Immunity",
        "theme": "Weaponized Indifference (Controlling Your Reaction)",
        "premise": "If their disrespect triggers your anger, they own you. Cold silence instantly strips away their leverage.",
        "hook_starter": "YOUR REACTION GIVES THEM POWER",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "A monolithic dark basalt stone resting unmoved against crashing stormy sea waves",
            "Heavy rain pouring down an ancient marble statue with water rolling off without a scratch",
            "A glowing ember dropping onto cold slate stone and extinguishing into harmless ash"
        ]
    },
    {
        "id": "THEME_COST_OF_LIKABILITY",
        "pillar": "Emotional Immunity",
        "theme": "The Cost of Being Likable (People Pleasing)",
        "premise": "Trying to please everyone is not kindness; it is fear of rejection. When everyone likes you, nobody respects your boundaries.",
        "hook_starter": "STOP TRYING TO BE LIKED",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "A weathered antique theater mask cracking apart on wet cobblestones",
            "A brittle dried clay seal crumbling under slight thumb pressure",
            "A weathered glass lens fracturing under direct intense sun focus"
        ]
    },
    {
        "id": "THEME_ABSORBING_INSULTS",
        "pillar": "Emotional Immunity",
        "theme": "The Armor of Epictetus (Insults Are Irrelevant)",
        "premise": "An insult cannot hurt you unless you agree with it. If someone mocks you, they reveal their own inner sickness.",
        "hook_starter": "INSULTS ONLY HURT FOOLS",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "A sharp bronze arrow deflecting harmlessly off a heavy Roman iron shield",
            "Mud hurled against a solid granite castle bastion washing away in the rain",
            "A venomous snake striking a solid bronze bell with no effect"
        ]
    },
    {
        "id": "THEME_GOSSIP_STARVATION",
        "pillar": "Emotional Immunity",
        "theme": "Gossip Starvation (Starving Drama of Fuel)",
        "premise": "When someone brings you gossip about others, they will talk about you tomorrow. Starve rumors with complete silence.",
        "hook_starter": "NEVER FEED SMALL MINDS",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "A dark iron snuffer descending over a guttering candle flame to extinguish it",
            "Dry withered brush caught in sudden rain preventing fire from spreading",
            "A deep stone cistern swallowing a pebble without producing an echo"
        ]
    },
    {
        "id": "THEME_UNRETURNED_LOYALTY",
        "pillar": "Emotional Immunity",
        "theme": "The Trap of Unreturned Loyalty",
        "premise": "Blind loyalty to people who only call when they need something is self-betrayal. Learn to close the vault.",
        "hook_starter": "STOP BLEEDING FOR USERS",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "A heavy iron bank vault door swinging shut on oiled precision hinges",
            "A cracked clay water vessel leaking water into barren sand",
            "A withered vine trimmed cleanly from a fruit-bearing olive branch"
        ]
    },

    # --- PILLAR 2: RELENTLESS EXECUTION & FOCUS ---
    {
        "id": "THEME_DOPAMINE_BANKRUPTCY",
        "pillar": "Relentless Focus",
        "theme": "Dopamine Bankruptcy (Drained by Distraction)",
        "premise": "You are not tired from hard work; you are drained from chasing worthless noise. Guard your stillness fiercely.",
        "hook_starter": "YOU ARE DRAINED BY NOISE",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "An antique bronze oil lamp burning steadily down to deep glowing amber embers",
            "Clear mountain spring water settling completely transparent inside a glass vial",
            "An iron pendulum slowing to a complete, balanced standstill"
        ]
    },
    {
        "id": "THEME_QUIET_EXECUTION",
        "pillar": "Relentless Focus",
        "theme": "Quiet Execution (Never Brag)",
        "premise": "Never broadcast what you are building. The world flatters plans but only respects finished stone.",
        "hook_starter": "BUILD IN COMPLETE OBSCURITY",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "A heavy blacksmith iron hammer striking a glowing hot blade on a dark stone anvil",
            "A stonemason chisel carving precise Roman numerals deep into granite bedrock",
            "Deep underground tree roots breaking through rock foundations in total darkness"
        ]
    },
    {
        "id": "THEME_SUNK_COST_TRAP",
        "pillar": "Relentless Focus",
        "theme": "The Sunk Cost Trap (Walking Away from Mistakes)",
        "premise": "Just because you spent years making a mistake does not mean you owe it your future. Cut the cord immediately.",
        "hook_starter": "STOP FEEDING DEAD DREAMS",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "A sharp pruning sickle cleanly slicing an anchor rope under high tension",
            "A heavy dry branch snapping off a centuries-old oak in storm winds",
            "An antique weighing scale dumping heavy slag to return to equilibrium"
        ]
    },
    {
        "id": "THEME_THE_MYTH_OF_WAITING",
        "pillar": "Relentless Focus",
        "theme": "The Myth of Waiting for Motivation",
        "premise": "Motivation is a fair-weather friend. Discipline is doing what needs to be done even when your emotions protest.",
        "hook_starter": "ACTION CURES SELF-PITY",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "Flint and steel striking violently to generate a sudden bright spark",
            "A heavy waterwheel turning relentlessly against strong river currents",
            "A team of draft oxen pulling a heavy plow through frost-hardened soil"
        ]
    },
    {
        "id": "THEME_THE_SOLITUDE_ADVANTAGE",
        "pillar": "Relentless Focus",
        "theme": "The Solitude Advantage (Power in Being Alone)",
        "premise": "A man who cannot sit quietly in a room alone is an easy target for anyone who promises stimulation.",
        "hook_starter": "LEARN TO SIT IN SILENCE",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "A single tall watchtower standing alone on a foggy mountain peak",
            "A lone golden eagle gliding motionless on thermal winds high above clouds",
            "A solitary stone lighthouse enduring darkness with a steady beam"
        ]
    },
    {
        "id": "THEME_ENVY_DESTRUCTION",
        "pillar": "Relentless Focus",
        "theme": "The Toxicity of Comparison",
        "premise": "When you envy another person's victory, you declare that your own journey is worthless. Mind your own craft.",
        "hook_starter": "NEVER WATCH THEIR RACE",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "A racehorse wearing blinders charging forward on a dry dirt arena",
            "A craftsman magnifying loupe focusing strictly on fine gold engravings",
            "A sundial tracking the sun without regard for passing clouds"
        ]
    },

    # --- PILLAR 3: MENTAL FORTRESS & RESILIENCE ---
    {
        "id": "THEME_FUTURE_RUIN",
        "pillar": "Mental Fortress",
        "theme": "The Illusion of Future Ruin (Overthinking)",
        "premise": "We suffer far more in imagination than in reality. The catastrophe keeping you awake will almost never arrive.",
        "hook_starter": "YOU SUFFER IN YOUR HEAD",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "Cold morning mist dissolving completely over ancient stone arches under sunlight",
            "A troubled pool of dark water settling into a crystal mirror as ripples fade",
            "A dark storm cloud dispersing harmlessly across a barren plain"
        ]
    },
    {
        "id": "THEME_CALAMITY_AS_TRAINING",
        "pillar": "Mental Fortress",
        "theme": "Calamity as Training (The Obstacle Is the Way)",
        "premise": "Do not curse the obstacle; the obstacle is your teacher. Adversity produces character that comfort can never build.",
        "hook_starter": "THE STRUGGLE IS THE TEACHER",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "A roaring forge furnace turning raw scrap iron into hardened Damascus steel",
            "A mountain pine tree growing dense and unshakeable in freezing gale winds",
            "A diamond blade grinding down rough raw stone into a sharp facet"
        ]
    },
    {
        "id": "THEME_BURDEN_OF_EXPECTATIONS",
        "pillar": "Mental Fortress",
        "theme": "The Burden of Expecting Fairness",
        "premise": "The universe owes you nothing. Expecting life to treat you gently because you are good is expecting a lion not to eat you.",
        "hook_starter": "THE WORLD OWES YOU NOTHING",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "A jagged granite headland taking crashing ocean waves without yielding",
            "A desert sandstorm sweeping across an ancient stone obelisk",
            "A heavy bronze coin falling indifferently on stone whether heads or tails"
        ]
    },
    {
        "id": "THEME_DEATH_OF_EGO",
        "pillar": "Mental Fortress",
        "theme": "The Death of Pride (True Confidence Is Quiet)",
        "premise": "Arrogance demands an audience. Real confidence speaks quietly, works without applause, and walks without a strut.",
        "hook_starter": "KILL YOUR NEED FOR PRAISE",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "A deep subterranean bedrock supporting an entire city without showing itself",
            "A dark iron anchor resting silently at the bottom of the ocean floor",
            "An ancient oak tree whose strength lies in its hidden root network"
        ]
    },
    {
        "id": "THEME_CONTROLLING_DESIRE",
        "pillar": "Mental Fortress",
        "theme": "The Chains of Wanting More",
        "premise": "Wealth does not consist in having great possessions, but in having few wants. He who is content cannot be enslaved.",
        "hook_starter": "WANT LESS TO RULE MORE",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "Heavy broken iron shackles lying in dust beside an open cell gate",
            "A simple earthenware cup filled with cool clear mountain well water",
            "A rustic wooden staff supporting a traveler over rugged mountain ridges"
        ]
    },
    {
        "id": "THEME_ANGER_AS_POISON",
        "pillar": "Mental Fortress",
        "theme": "Anger Is Self-Poison (The Seneca Cure)",
        "premise": "Holding onto anger is like drinking poison and expecting the other person to die. Calmness is the ultimate weapon.",
        "hook_starter": "ANGER IS TEMPORARY MADNESS",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "Boiling water in a bronze cauldron cooling down to smooth stillness",
            "A wild brushfire hitting a wide dirt trench and running out of fuel",
            "A raging wild stallion being brought to stillness by a steady hand on the reins"
        ]
    },

    # --- PILLAR 4: RADICAL ACCEPTANCE & IMPERMANENCE ---
    {
        "id": "THEME_MEMENTO_MORI",
        "pillar": "Radical Acceptance",
        "theme": "Memento Mori (The Clock Is Ticking)",
        "premise": "You could leave life right now. Let that determine what you do, what you say, and what you think.",
        "hook_starter": "YOU ARE RUNNING OUT OF TIME",
        "archetype": "FORGE_AMBER",
        "metaphors": [
            "Fine golden sand falling steadily through an ancient glass hourglass neck",
            "A shadow lengthening across Roman stone numerals on a sundial face",
            "A single dried autumn leaf detaching and drifting on a brisk wind"
        ]
    },
    {
        "id": "THEME_AMOR_FATI",
        "pillar": "Radical Acceptance",
        "theme": "Amor Fati (Love Your Fate)",
        "premise": "Do not demand that things happen as you wish. Wish that things happen as they actually happen, and your life will flow well.",
        "hook_starter": "ACCEPT WHATEVER COMES NEXT",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "A raging river flowing around boulders without slowing its descent",
            "A large campfire consuming whatever fuel is thrown into its flames",
            "A ship sail adjusting its ropes to catch crosswinds and maintain heading"
        ]
    },
    {
        "id": "THEME_STRIPPING_THE_PEDESTAL",
        "pillar": "Radical Acceptance",
        "theme": "Stripping the Pedestal (Nobody Is a God)",
        "premise": "Never put anyone on a pedestal. They bleed, make mistakes, age, and suffer from the same weaknesses as you.",
        "hook_starter": "NOBODY IS ABOVE YOU",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "A gilded monument showing exposed cracked limestone underneath worn gold leaf",
            "A royal purple woolen mantle turning to simple thread under close inspection",
            "A chess board being cleared where kings and pawns go into the same wooden box"
        ]
    },
    {
        "id": "THEME_THE_RIVER_OF_TIME",
        "pillar": "Radical Acceptance",
        "theme": "The River of Time (Everything Passes)",
        "premise": "The pain you feel right now will pass. The victory you celebrate today will fade. Ground your peace in eternity.",
        "hook_starter": "THIS TOO SHALL PASS",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "Fast river water rushing over polished river stones under sunlight",
            "Ancient Roman stone ruins standing tranquil against centuries of weather",
            "Constellations revolving slowly in clear dark night skies over mountains"
        ]
    },
    {
        "id": "THEME_DEATH_OF_OPINIONS",
        "pillar": "Radical Acceptance",
        "theme": "The Irrelevance of Public Opinion",
        "premise": "Why do you value yourself over others, but value their opinion of you over your own judgment? Reclaim your inner court.",
        "hook_starter": "TRUST YOUR OWN JUDGMENT",
        "archetype": "IMPERIAL_GOLD",
        "metaphors": [
            "A balance scale holding a single gold bullion balancing against heaps of straw",
            "A solid bronze compass needle pointing true North regardless of storm winds",
            "An ancient judge stone bench standing empty and resolute under open skies"
        ]
    },
    {
        "id": "THEME_THE_FINAL_BOUNDARY",
        "pillar": "Radical Acceptance",
        "theme": "The Final Boundary (Sovereign Stillness)",
        "premise": "The mind is its own place. No tyrant, circumstance, or insult can break inside unless you leave the gate unlocked.",
        "hook_starter": "GUARD YOUR INNER CITADEL",
        "archetype": "GLACIAL_ICE",
        "metaphors": [
            "A massive carved stone gateway fortified with heavy bronze iron bands",
            "A solitary fortress lantern burning steadily against pitch-black mountain fog",
            "A deep subterranean spring flowing cold and pure under massive granite arches"
        ]
    }
]

SETTINGS_MATRIX = [
    {
        "setting_name": "The Ancient Citadel Colonnades",
        "setting_desc": "Within towering monolithic ancient stone colonnades and rain-slicked courtyards, flickering bronze braziers casting long dramatic shadows."
    },
    {
        "setting_name": "The Windswept Coastal Cliffs",
        "setting_desc": "Standing atop high windswept coastal cliffs overlooking turbulent dark ocean waves crashing against jagged basalt rocks in atmospheric fog."
    },
    {
        "setting_name": "The Secluded Stone Workshop",
        "setting_desc": "Inside a secluded ancient stone workshop with drafting parchment, beeswax candles, deep shadows, and glowing forge embers in the background."
    },
    {
        "setting_name": "The Rugged Mountain Summit",
        "setting_desc": "Traversing a barren rocky mountain pass under cold dramatic grey skies and swirling morning mist beside ancient weathered stone shrines."
    }
]

# ---------------------------------------------------------
# 4. CADENCE & PERSISTENT COOLDOWN DATABASE
# ---------------------------------------------------------
DB_PATH = os.path.join(DATA_DIR, "video_schedule.json")

def load_db():
    defaults = {
        "scheduled_videos": [],
        "used_hooks": [],
        "used_theme_ids": [],
        "last_scheduled_date": None,
        "last_scheduled_slot": None,
        "slot1_time": "05:00",
        "slot2_time": "20:00"
    }
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for k, v in defaults.items():
                    if k not in data:
                        data[k] = v
                return data
        except Exception:
            pass
    return defaults

def save_db(data):
    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

db = load_db()

def parse_time_str(t_str, fallback):
    try:
        parts = t_str.split(":")
        return time(int(parts[0]), int(parts[1]))
    except Exception:
        return fallback

def get_next_slot(base_date=None, base_slot=None):
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    last_d_str = base_date if base_date else db.get("last_scheduled_date")
    last_slot = base_slot if base_slot else db.get("last_scheduled_slot")
    s1_t_str = db.get("slot1_time", "05:00")
    s2_t_str = db.get("slot2_time", "20:00")

    if last_d_str and last_slot:
        try:
            last_d = datetime.strptime(str(last_d_str), "%Y-%m-%d").date()
        except ValueError:
            last_d = now_ist.date()

        if "SLOT 1" in str(last_slot).upper():
            target_d = last_d
            target_slot = "SLOT 2 (EVENING)"
            target_time = s2_t_str
        else:
            target_d = last_d + timedelta(days=1)
            target_slot = "SLOT 1 (MORNING)"
            target_time = s1_t_str
    else:
        target_d = now_ist.date()
        s1_time = parse_time_str(s1_t_str, time(5, 0))
        s2_time = parse_time_str(s2_t_str, time(20, 0))

        if now_ist.time() < s1_time:
            target_slot = "SLOT 1 (MORNING)"
            target_time = s1_t_str
        elif now_ist.time() < s2_time:
            target_slot = "SLOT 2 (EVENING)"
            target_time = s2_t_str
        else:
            target_d = now_ist.date() + timedelta(days=1)
            target_slot = "SLOT 1 (MORNING)"
            target_time = s1_t_str

    return target_d.strftime("%Y-%m-%d"), target_slot, target_time

# ---------------------------------------------------------
# 5. AUDIO SYNTHESIS & ASS SUBTITLES
# ---------------------------------------------------------
async def synthesize_speech_timed(text, audio_path):
    communicate = edge_tts.Communicate(text, voice="en-GB-RyanNeural", rate="+15%", pitch="-2Hz")
    word_timings = []
    
    with open(audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_s = chunk["offset"] / 10_000_000.0
                dur_s = chunk["duration"] / 10_000_000.0
                word_timings.append({
                    "word": chunk.get("text", ""),
                    "start": round(start_s, 3),
                    "end": round(start_s + dur_s, 3)
                })
    return word_timings

def build_ass_subtitles(timed_words, script_text, ass_path, total_duration, archetype_key="IMPERIAL_GOLD"):
    color_cfg = SUBTITLE_ARCHETYPES.get(archetype_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])
    primary_color = color_cfg["ass_primary"]
    dialogue_events = []
    
    if not timed_words or len(timed_words) < 5:
        tokens = script_text.split()
        chunk_size = 3
        token_groups = [tokens[i:i + chunk_size] for i in range(0, len(tokens), chunk_size)]
        step = max(0.5, (total_duration - 0.8) / max(1, len(token_groups)))
        
        for idx, group in enumerate(token_groups):
            st_t = idx * step
            en_t = min(total_duration, (idx + 1) * step)
            txt = re.sub(r'[^\w\s\',.!?-]', '', " ".join(group)).upper()
            dialogue_events.append((st_t, en_t, txt))
    else:
        chunk = []
        for i, tw in enumerate(timed_words):
            clean_w = re.sub(r'[^\w\s\',.!?-]', '', tw['word']).upper()
            chunk.append({'word': clean_w, 'start': tw['start'], 'end': tw['end']})
            is_punct = any(tw['word'].endswith(p) for p in ['.', '!', '?', ':', ';'])
            has_pause = (i + 1 < len(timed_words)) and (timed_words[i + 1]['start'] - tw['end'] >= 0.25)
            
            if is_punct or has_pause or len(chunk) >= 3:
                st_t = chunk[0]['start']
                en_t = min(total_duration, max(chunk[-1]['end'], st_t + 0.35))
                txt = " ".join([c['word'] for c in chunk]).strip()
                if txt:
                    dialogue_events.append((st_t, en_t, txt))
                chunk = []
                
        if chunk:
            st_t = chunk[0]['start']
            en_t = min(total_duration, max(chunk[-1]['end'], st_t + 0.35))
            txt = " ".join([c['word'] for c in chunk]).strip()
            if txt:
                dialogue_events.append((st_t, en_t, txt))

    def ass_ts(s):
        h, m, sec = int(s // 3600), int((s % 3600) // 60), s % 60
        return f"{h}:{m:02d}:{sec:05.2f}"

    ass_content = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,76,{primary_color},&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,50,50,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    for st_t, en_t, txt in dialogue_events:
        ass_content += f"Dialogue: 0,{ass_ts(st_t)},{ass_ts(en_t)},Default,,0,0,0,,{txt}\n"

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
        
    return dialogue_events

# ---------------------------------------------------------
# 6. GEMINI GENERATOR (SAFE-ZONE FRAMING & CROP PROOF)
# ---------------------------------------------------------
def generate_video_package(raw_api_key, angle_obj, macro_choice, setting_obj):
    clean_key = raw_api_key.strip().strip('"').strip("'")
    client = genai.Client(api_key=clean_key)
    
    used_hooks = db.get("used_hooks", [])
    blacklist_str = "\n".join([f"- {h}" for h in used_hooks[-40:]]) if used_hooks else "None yet."

    full_prompt = f"""
    You are the Creative Director for 'Echoes of Wisdom', producing high-retention Stoic vertical video reels (9:16).
    ACTIVE STOIC PILLAR: {angle_obj['pillar']}
    ACTIVE CORE THEME: {angle_obj['theme']}
    PREMISE: {angle_obj['premise']}
    DEFAULT HOOK: {angle_obj['hook_starter']}
    ASSIGNED MACRO SYMBOL (SCENE 2): {macro_choice}
    CINEMATIC ENVIRONMENT (SCENES 1, 3, 4): {setting_obj['setting_desc']}

    FORBIDDEN PREVIOUS HOOKS (DO NOT REPEAT):
    {blacklist_str}

    STRICT CROP-PROOF FRAMING DIRECTIVES:
    All video clips and thumbnail will undergo a 1.4x (40%) center-zoom to crop out corner watermarks.
    Therefore, you MUST format EVERY visual prompt with these camera framing constraints:
    1. Distance: 'Cinematic medium shot' or 'medium-wide shot'. NEVER specify 'extreme close-up' or 'tight face crop'.
    2. Headroom: Always specify 'Generous 25% empty headroom and safe upper margins'.
    3. Center Anchor: Always specify 'Subject strictly framed in the central 60% safe zone of the 9:16 vertical canvas, with breathing room on all sides so head and shoulders remain completely in frame after center-crop'.
    4. Focus: Always specify 'Sharp deep focus on the central subject, crisp details, 8k cinematic resolution'.
    5. Macro Metaphor (Scene 2): Always specify 'Wide-angle macro shot with ample negative space around the entire object, completely centered'.

    GENERAL RULES:
    1. Word count: Exactly 65 to 70 words total.
    2. Hook: Line 1 must challenge the viewer directly
