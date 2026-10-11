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
    .dot { width: 6px; height: 6px; border-radius: 50%; background-color: #34D399; box-shadow: 0 0 8px #34D399; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. WORKSPACE, FONT FOUNDRY & UNICODE FORMATTER
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
    """Converts regular text to true mathematical bold Unicode for Facebook feeds."""
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
# 3. DUAL-SLOT CADENCE ENGINE (PERSISTENT LOGIC)
# ---------------------------------------------------------
DB_PATH = os.path.join(DATA_DIR, "video_schedule.json")

def load_db():
    defaults = {
        "scheduled_videos": [],
        "used_hooks": [],
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
# 4. VIRAL Stoic THEMES
# ---------------------------------------------------------
VIRAL_ANGLES = [
    {
        "theme": "The Silent Exit (Outgrowing Disrespect)",
        "premise": "Never announce when you cut someone off. Withdrawing your presence without an argument is the ultimate power move.",
        "macro_symbol": "An ancient heavy bronze portal latch locking into dark textured stone",
        "hook_starter": "NEVER ANNOUNCE YOUR EXIT",
        "default_archetype": "GLACIAL_ICE"
    },
    {
        "theme": "The Cost of Being Likable (People Pleasing)",
        "premise": "Trying to please everyone is not kindness; it is weakness. When everyone likes you, nobody respects your boundaries.",
        "macro_symbol": "A weathered antique stone theater mask breaking apart on cobblestones",
        "hook_starter": "STOP TRYING TO BE LIKED",
        "default_archetype": "FORGE_AMBER"
    },
    {
        "theme": "Weaponized Indifference (Controlling Your Reaction)",
        "premise": "If their disrespect triggers your anger, you belong to them. Cold silence strips them of control instantly.",
        "macro_symbol": "A monolithic dark basalt stone resting unmoved against crashing stormy sea waves",
        "hook_starter": "YOUR REACTION GIVES THEM POWER",
        "default_archetype": "GLACIAL_ICE"
    },
    {
        "theme": "Dopamine Bankruptcy (Mental Focus)",
        "premise": "You are not tired from hard work; you are drained from chasing worthless noise. Guard your stillness fiercely.",
        "macro_symbol": "An antique bronze oil lamp burning steadily down to deep glowing amber embers",
        "hook_starter": "YOU ARE DRAINED BY NOISE",
        "default_archetype": "FORGE_AMBER"
    },
    {
        "theme": "Quiet Execution (Never Brag)",
        "premise": "Never broadcast what you are building. The world flatters plans but only respects finished stone.",
        "macro_symbol": "A heavy blacksmith iron hammer striking a glowing hot blade on a dark stone anvil",
        "hook_starter": "BUILD IN COMPLETE OBSCURITY",
        "default_archetype": "IMPERIAL_GOLD"
    },
    {
        "theme": "The Illusion of Future Ruin (Overthinking)",
        "premise": "We suffer ten times more in our thoughts than in reality. The catastrophe keeping you awake will never arrive.",
        "macro_symbol": "Cold morning mist dissolving completely over ancient stone arches under sunlight",
        "hook_starter": "YOU SUFFER IN YOUR HEAD",
        "default_archetype": "IMPERIAL_GOLD"
    }
]

# ---------------------------------------------------------
# 5. AUDIO SYNTHESIS & SUBTITLES
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
# 6. GEMINI 3.8 FLASH GENERATOR (MULTI-PLATFORM COPY)
# ---------------------------------------------------------
def generate_video_package(raw_api_key, angle):
    clean_key = raw_api_key.strip().strip('"').strip("'")
    client = genai.Client(api_key=clean_key)
    
    used_hooks = db.get("used_hooks", [])
    blacklist_str = "\n".join([f"- {h}" for h in used_hooks[-40:]]) if used_hooks else "None yet."

    full_prompt = f"""
    You are the Creative Director for 'Echoes of Wisdom', producing high-retention Stoic vertical video reels (9:16).
    ACTIVE CORE THEME: {angle['theme']}
    PREMISE: {angle['premise']}
    DEFAULT HOOK: {angle['hook_starter']}
    MACRO SYMBOL: {angle['macro_symbol']}

    FORBIDDEN PREVIOUS HOOKS (DO NOT REPEAT):
    {blacklist_str}

    STRICT RULES:
    1. Word count: Exactly 65 to 70 words total.
    2. Hook: Line 1 must challenge the viewer directly within 4 words.
    3. Seamless Loop: The last sentence must connect cleanly back into the opening hook.
    4. Subtitle Archetype Selection:
       - 'GLACIAL_ICE' for cold silence, indifference, setting boundaries, or walking away.
       - 'FORGE_AMBER' for discipline, hard work, focus, dopamine detox, or overcoming overthinking.
       - 'IMPERIAL_GOLD' for inner sovereignty, regal composure, high-status stillness, or wisdom.
    5. Facebook & Instagram Copy:
       - caption_hook: 4-6 explosive words (e.g. NEVER ANNOUNCE YOUR EXIT).
       - caption_lesson: 2 punchy psychological sentences explaining the deeper truth.
       - debate_question: 1 binary dilemma (e.g. When someone disrespects you:).
       - choice_1: The stoic silent reaction.
       - choice_2: The impulsive reaction.
    6. Google Flow Compliance:
       - Character MUST always be described as: 'An original fictional mature man with a weathered lined face, calm focused eyes, messy salt-and-pepper hair, thick beard, draped in an authentic dark woolen ancient mantle.'
       - Never use names like Marcus, Seneca, Epictetus in visual prompts.
       - Natural silence: 'Dignified silent composure, serene stoic expression, calm and steady gaze.'
       - Format: Every prompt must begin with '[4-second vertical 9:16 cinematic video clip]'.

    Output STRICT JSON matching this schema:
    {{
      "title_concept": "Short Concept Title",
      "hook_banner": "3-4 WORDS IN ALL CAPS",
      "subtitle_archetype": "GLACIAL_ICE or FORGE_AMBER or IMPERIAL_GOLD",
      "script": "Full 65-70 word script with seamless loop.",
      "scene1_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 1 prompt",
      "scene2_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 2 prompt ({angle['macro_symbol']})",
      "scene3_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 3 prompt",
      "scene4_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 4 prompt",
      "thumbnail_prompt": "High-contrast 9:16 vertical portrait prompt with bold hook text suggestion",
      "youtube_title": "High CTR Title #shorts #stoicism",
      "youtube_description": "Full YouTube description with handles and hashtags",
      "youtube_tags": "stoicism, stoic mindset, power of silence, boundaries, discipline, echoes of wisdom",
      "youtube_pinned_comment": "Binary debate question with 1️⃣ and 2️⃣ choices",
      "facebook_title": "High CTR Facebook Title",
      "caption_hook": "PUNCHY 4-6 WORD HOOK",
      "caption_lesson": "Two sentences of high-value wisdom.",
      "debate_question": "When someone disrespects you:",
      "choice_1": "Walk away in cold silence",
      "choice_2": "Confront them directly",
      "facebook_hashtags": "#StoicMindset #EchoesOfWisdom #PowerOfSilence #Reels #Stoicism"
    }}
    """

    for mod in ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]:
        try:
            resp = client.models.generate_content(
                model=mod,
                contents=full_prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.85
                )
            )
            parsed = json.loads(resp.text)
            if "script" in parsed:
                return parsed, None
        except Exception as e:
            continue
            
    return None, "API error generating concept. Please verify your Gemini API key."

# ---------------------------------------------------------
# 7. TELEMETRY BAR & CADENCE MANAGER (ACCORDION)
# ---------------------------------------------------------
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 500;">v2.0 // CADENCE SUITE</span>
</div>
""", unsafe_allow_html=True)

target_date, target_slot, target_time = get_next_slot()

st.markdown(f"""
<div class="telemetry-bar">
    <div class="badge badge-green"><span class="dot"></span> ENGINE: ONLINE</div>
    <div class="badge badge-blue">⚡ GEMINI 3.8 + EDGE-TTS</div>
    <div class="badge badge-amber">📅 NEXT DROP: {target_date} @ {target_time} IST ({target_slot})</div>
</div>
""", unsafe_allow_html=True)

if "status_banner" in st.session_state:
    st.markdown(f"""
    <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #34D399;">
        {st.session_state['status_banner']}
    </div>
    """, unsafe_allow_html=True)
    del st.session_state["status_banner"]

# Cadence Manager Accordion
with st.expander("📅 PUBLISHING CADENCE & TIME MANAGER", expanded=False):
    col_c1, col_c2 = st.columns(2)
    saved_last_d_str = db.get("last_scheduled_date")
    saved_last_d = None
    if saved_last_d_str:
        try:
            saved_last_d = datetime.strptime(saved_last_d_str, "%Y-%m-%d").date()
        except Exception:
            pass
            
    with col_c1:
        custom_last_d = st.date_input(
            "Last Scheduled Date",
            value=saved_last_d if saved_last_d else datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
        )
        slot_choices = ["SLOT 1 (MORNING)", "SLOT 2 (EVENING)"]
        current_saved_slot = db.get("last_scheduled_slot", "SLOT 2 (EVENING)")
        slot_idx = 0 if "SLOT 1" in str(current_saved_slot).upper() else 1
        custom_last_slot = st.selectbox("Last Completed Slot", slot_choices, index=slot_idx)

    with col_c2:
        t1_val = parse_time_str(db.get("slot1_time", "05:00"), time(5, 0))
        t2_val = parse_time_str(db.get("slot2_time", "20:00"), time(20, 0))
        custom_t1 = st.time_input("Slot 1 Morning Time (IST)", value=t1_val)
        custom_t2 = st.time_input("Slot 2 Evening Time (IST)", value=t2_val)

    if st.button("💾 Save Schedule Cadence Preference"):
        db["last_scheduled_date"] = custom_last_d.strftime("%Y-%m-%d")
        db["last_scheduled_slot"] = custom_last_slot
        db["slot1_time"] = custom_t1.strftime("%H:%M")
        db["slot2_time"] = custom_t2.strftime("%H:%M")
        save_db(db)
        calc_d, calc_s, calc_t = get_next_slot(db["last_scheduled_date"], db["last_scheduled_slot"])
        st.session_state["status_banner"] = f"✓ CADENCE PREFERENCE SAVED! Next queue locked to: {calc_d} @ {calc_t} IST ({calc_s})"
        st.rerun()

# API Key Resolution
if "api_key" not in st.session_state:
    st.session_state["api_key"] = ""

if "GEMINI_API_KEY" in st.secrets:
    st.session_state["api_key"] = str(st.secrets["GEMINI_API_KEY"]).strip().strip('"').strip("'")
elif os.getenv("GEMINI_API_KEY"):
    st.session_state["api_key"] = str(os.getenv("GEMINI_API_KEY")).strip().strip('"').strip("'")

with st.expander("🔑 API CREDENTIALS", expanded=(not bool(st.session_state["api_key"]))):
    user_key = st.text_input("Gemini API Key", value=st.session_state["api_key"], type="password", placeholder="AIzaSy...")
    if user_key:
        st.session_state["api_key"] = user_key.strip().strip('"').strip("'")

# ---------------------------------------------------------
# 8. COPY BUTTON COMPONENT (FLASHES SOLID GREEN)
# ---------------------------------------------------------
def render_copy_deck(btn_id, label, text_content):
    escaped_json = json.dumps(text_content)
    components.html(f"""
    <div style="margin: 0; padding: 0;">
        <button id="btn_{btn_id}" onclick="copyText_{btn_id}()" style="width: 100%; height: 2.6rem; background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 8px; font-weight: 700; font-family: monospace; font-size: 12px; cursor: pointer; letter-spacing: 0.04em; transition: all 0.2s;">
            📋 {label}
        </button>
    </div>
    <script>
        function copyText_{btn_id}() {{
            var str = {escaped_json};
            function setSuccess() {{
                var btn = document.getElementById("btn_{btn_id}");
                btn.innerText = "✓ COPIED TO CLIPBOARD!";
                btn.style.background = "#059669";
                btn.style.color = "#FFFFFF";
                btn.style.borderColor = "#34D399";
                setTimeout(function() {{
                    btn.innerText = "📋 {label}";
                    btn.style.background = "rgba(56, 189, 248, 0.15)";
                    btn.style.color = "#38BDF8";
                    btn.style.borderColor = "rgba(56, 189, 248, 0.4)";
                }}, 2500);
            }}

            if (navigator.clipboard && navigator.clipboard.writeText) {{
                navigator.clipboard.writeText(str).then(setSuccess).catch(function() {{
                    fallback(str);
                }});
            }} else {{
                fallback(str);
            }}

            function fallback(t) {{
                var el = document.createElement('textarea');
                el.value = t;
                el.setAttribute('readonly', '');
                el.style.position = 'absolute';
                el.style.left = '-9999px';
                document.body.appendChild(el);
                el.select();
                try {{
                    document.execCommand('copy');
                    setSuccess();
                }} catch(err) {{}}
                document.body.removeChild(el);
            }}
        }}
    </script>
    """, height=48)

# ---------------------------------------------------------
# 9. TABS NAVIGATION
# ---------------------------------------------------------
tab_synth, tab_render, tab_queue = st.tabs(["⚡ 1. SCRIPT & PROMPTS", "🎬 2. RENDER MASTER REEL", "📋 3. QUEUE LEDGER"])

# --- TAB 1: SCRIPT & ALL 5 PROMPTS ---
with tab_synth:
    col_t1, col_t2 = st.columns([3, 2])
    with col_t1:
        theme_options = ["🎲 Random / AI Choice"] + [a["theme"] for a in VIRAL_ANGLES]
        chosen_theme_name = st.selectbox("Stoic Psychological Angle", theme_options)
    with col_t2:
        arch_options = ["🤖 AI Recommended"] + list(SUBTITLE_ARCHETYPES.keys())
        chosen_arch_override = st.selectbox(
            "Subtitle Color Style",
            arch_options,
            format_func=lambda x: "🤖 AI Recommended" if x.startswith("🤖") else SUBTITLE_ARCHETYPES[x]["label"]
        )
    
    if st.button("🚀 Generate Video Package & Spoken Audio", type="primary"):
        active_key = st.session_state.get("api_key", "").strip()
        if not active_key:
            st.error("Please enter your Gemini API Key in the '🔑 API CREDENTIALS' panel above.")
        else:
            with st.spinner("⚡ Synthesizing script, setting color archetype & generating voiceover..."):
                if chosen_theme_name.startswith("🎲"):
                    angle_data = random.choice(VIRAL_ANGLES)
                else:
                    angle_data = next((a for a in VIRAL_ANGLES if a["theme"] == chosen_theme_name), VIRAL_ANGLES[0])

                package, err = generate_video_package(active_key, angle_data)
                if err or not package:
                    st.error(f"⚠️ Synthesis Failed: {err}")
                else:
                    if chosen_arch_override and not chosen_arch_override.startswith("🤖"):
                        final_arch = chosen_arch_override
                    else:
                        final_arch = package.get("subtitle_archetype", angle_data.get("default_archetype", "IMPERIAL_GOLD"))
                        if final_arch not in SUBTITLE_ARCHETYPES:
                            final_arch = "IMPERIAL_GOLD"
                    
                    package["subtitle_archetype"] = final_arch

                    audio_path = os.path.join(TMP_DIR, "audio.mp3")
                    word_timings = asyncio.run(synthesize_speech_timed(package["script"], audio_path))
                    
                    st.session_state["active_video_pkg"] = {
                        "package": package,
                        "audio_path": audio_path,
                        "timings": word_timings,
                        "target_date": target_date,
                        "target_slot": target_slot,
                        "target_time": target_time
                    }
                    st.success(f"✅ Script ready! Palette: {SUBTITLE_ARCHETYPES[final_arch]['label']}")

    if "active_video_pkg" in st.session_state:
        pkg = st.session_state["active_video_pkg"]["package"]
        current_arch = pkg.get("subtitle_archetype", "IMPERIAL_GOLD")
        arch_meta = SUBTITLE_ARCHETYPES.get(current_arch, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])

        st.divider()
        st.subheader(f"📜 Concept: {pkg.get('title_concept', 'Stoic Reel')}")
        st.markdown(f"**🎨 Subtitle Palette:** `{arch_meta['label']}`")
        st.info(f"🎯 **Hook Banner:** `{pkg.get('hook_banner', 'MOVE IN SILENCE')}`\n\n🗣️ **Script ({len(pkg['script'].split())} words):**\n\n*{pkg['script']}*")
        
        st.audio(st.session_state["active_video_pkg"]["audio_path"])
        
        st.markdown("### 📋 Copy Google Flow Prompts")
        prompt_cards = [
            ("1. SCENE 1 PROMPT (4S)", "scene1_prompt"),
            ("2. SCENE 2 PROMPT (MACRO 4S)", "scene2_prompt"),
            ("3. SCENE 3 PROMPT (4S)", "scene3_prompt"),
            ("4. SCENE 4 PROMPT (4S)", "scene4_prompt"),
            ("5. THUMBNAIL PROMPT (9:16 HIGH-CTR)", "thumbnail_prompt")
        ]
        for idx, (label, key) in enumerate(prompt_cards):
            p_text = pkg.get(key, "")
            st.text_area(label, p_text, height=75)
            render_copy_deck(f"p_{idx}", f"COPY {label}", p_text)

# --- TAB 2: COMPOSE & RENDER REEL ---
with tab_render:
    st.markdown("### 📥 1. Upload Your 4 Google Flow Video Clips")
    uploaded_clips = st.file_uploader(
        "Select the 4 vertical video clips from your phone gallery",
        type=["mp4", "mov"],
        accept_multiple_files=True
    )
    
    st.markdown("### 🖼️ 2. Optional: Thumbnail Cleaner (Auto-Patch Watermark)")
    uploaded_thumb = st.file_uploader("Upload raw Google Flow thumbnail (clean_thumbnail.png)", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_thumb:
        try:
            raw_thumb = Image.open(uploaded_thumb).convert("RGB")
            tw, th = raw_thumb.size
            tdraw = ImageDraw.Draw(raw_thumb)
            bg_col = raw_thumb.getpixel((int(tw * 0.90), int(th * 0.97)))
            tdraw.rectangle([int(tw * 0.92), int(th * 0.955), tw, th], fill=bg_col)
            
            t_buf = io.BytesIO()
            raw_thumb.save(t_buf, format="PNG", quality=98)
            st.download_button(
                label="💾 Download Watermark-Cleaned Thumbnail",
                data=t_buf.getvalue(),
                file_name=f"{target_date.replace('-', '')}_clean_thumbnail.png",
                mime="image/png"
            )
        except Exception as e:
            st.warning(f"Could not patch thumbnail: {e}")

    st.markdown("### 🎵 3. Optional: Background Music")
    uploaded_music = st.file_uploader("Select MP3 track (or leave empty for clean narration)", type=["mp3"])
    
    if st.button("🎬 Render Master 9:16 Vertical Reel", type="primary"):
        if "active_video_pkg" not in st.session_state:
            st.error("Please generate a script package in Tab 1 first.")
        elif not uploaded_clips or len(uploaded_clips) < 4:
            st.error(f"Please upload all 4 clips from Google Flow. (Uploaded: {len(uploaded_clips) if uploaded_clips else 0}/4)")
        else:
            with st.spinner("⚡ Assembling video, burning adaptive subtitles & balancing audio..."):
                pkg_data = st.session_state["active_video_pkg"]["package"]
                timings = st.session_state["active_video_pkg"].get("timings", [])
                audio_path = st.session_state["active_video_pkg"]["audio_path"]
                script_txt = pkg_data.get("script", "")
                
                arch_key = pkg_data.get("subtitle_archetype", "IMPERIAL_GOLD")
                arch_meta = SUBTITLE_ARCHETYPES.get(arch_key, SUBTITLE_ARCHETYPES["IMPERIAL_GOLD"])
                banner_color = arch_meta["banner_hex"]
                
                clip_paths = []
                for i, clip in enumerate(uploaded_clips[:4]):
                    c_path = os.path.join(TMP_DIR, f"clip_{i}.mp4")
                    with open(c_path, "wb") as f:
                        f.write(clip.read())
                    clip_paths.append(c_path)
                    
                probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
                res = subprocess.run(probe_cmd, capture_output=True, text=True)
                vo_dur = float(res.stdout.strip()) if res.stdout.strip() else 28.0
                target_dur = vo_dur + 0.6
                per_clip_dur = target_dur / 4.0
                speed_factor = per_clip_dur / 4.0

                ass_path = os.path.join(TMP_DIR, "subtitles.ass")
                cues = build_ass_subtitles(timings, script_txt, ass_path, target_dur, archetype_key=arch_key)

                clean_ass_path = ass_path.replace("'", "\\'").replace(":", "\\:")
                clean_fonts_dir = FONTS_DIR.replace("'", "\\'").replace(":", "\\:")
                
                logo_file = "logo.png" if os.path.exists("logo.png") else None
                banner_text = pkg_data.get("hook_banner", "MOVE IN SILENCE").replace("'", "\\'").replace(":", "\\:")
                out_video_path = os.path.join(TMP_DIR, "output_master.mp4")

                filter_chains = [
                    f"[0:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v0];"
                    f"[1:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v1];"
                    f"[2:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v2];"
                    f"[3:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v3];"
                    f"[v0][v1][v2][v3]concat=n=4:v=1:a=0[vbase];"
                    f"[vbase]drawtext=text='{banner_text}':fontsize=44:fontcolor={banner_color}:"
                    f"box=1:boxcolor=black@0.85:boxborderw=18:x=(w-text_w)/2:y=180:enable='between(t,0,3.5)',"
                    f"ass='{clean_ass_path}':fontsdir='{clean_fonts_dir}'[v_sub]"
                ]

                inputs = ['-i', clip_paths[0], '-i', clip_paths[1], '-i', clip_paths[2], '-i', clip_paths[3], '-i', audio_path]

                if logo_file:
                    inputs.extend(['-i', logo_file])
                    filter_chains.append(";[5:v]scale=120:-1,format=rgba[logo_s];[v_sub][logo_s]overlay=W-w-50:150[vout]")
                else:
                    filter_chains.append(";[v_sub]copy[vout]")

                if uploaded_music:
                    m_path = os.path.join(TMP_DIR, "user_music.mp3")
                    with open(m_path, "wb") as f:
                        f.write(uploaded_music.read())
                    inputs.extend(['-i', m_path])
                    m_idx = 6 if logo_file else 5
                    filter_chains.append(
                        f";[4:a]volume=1.0[vo];"
                        f"[{m_idx}:a]aloop=loop=-1:size=2e+09,volume=0.15,afade=t=out:st={target_dur-2.0:.1f}:d=2.0[bg];"
                        f"[vo][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
                    )
                else:
                    filter_chains.append(";[4:a]volume=1.0[aout]")

                render_cmd = [
                    'ffmpeg', '-y', *inputs,
                    '-filter_complex', "".join(filter_chains),
                    '-map', '[vout]', '-map', '[aout]',
                    '-t', str(target_dur),
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                    '-c:a', 'aac', '-b:a', '192k',
                    '-pix_fmt', 'yuv420p',
                    out_video_path
                ]

                proc = subprocess.run(render_cmd, capture_output=True, text=True)
                if proc.returncode != 0:
                    st.error(f"FFmpeg Compilation Error: {proc.stderr[:400]}")
                else:
                    st.session_state["rendered_video_path"] = out_video_path
                    st.success(f"🎉 Master Reel Rendered! Subtitle Palette: {arch_meta['label']}")

    if "rendered_video_path" in st.session_state:
        v_path = st.session_state["rendered_video_path"]
        st.video(v_path)
        
        active_sess = st.session_state["active_video_pkg"]
        pkg = active_sess["package"]
        curr_date = active_sess.get("target_date", target_date)
        curr_slot = active_sess.get("target_slot", target_slot)
        curr_time = active_sess.get("target_time", target_time)

        # Exact Colab naming convention: YYYYMMDD_<slug>.mp4
        raw_slug = re.sub(r'[^a-zA-Z0-9]+', '_', pkg.get('hook_banner', 'stoic_reel')).strip('_').lower()
        export_name = f"{curr_date.replace('-', '')}_{raw_slug}.mp4"

        with open(v_path, "rb") as f:
            v_bytes = f.read()

        st.download_button(
            label=f"💾 Download Master Reel ({export_name})",
            data=v_bytes,
            file_name=export_name,
            mime="video/mp4"
        )

        st.divider()
        st.markdown(f"### 🎯 QUEUE: {curr_date} @ {curr_time} IST ({curr_slot})")

        # --- YOUTUBE SHORTS METADATA SUITE ---
        st.markdown("#### 🔴 YOUTUBE SHORTS SUITE")
        yt_t = pkg.get("youtube_title", f"{pkg.get('hook_banner', 'Stoic Reel').title()} #shorts #stoicism")
        st.text_input("YouTube Title", yt_t, key="yt_title_field")
        render_copy_deck("yt_t", "COPY YOUTUBE TITLE", yt_t)

        yt_desc = pkg.get("youtube_description", (
            f"{pkg['script']}\n\n"
            "Subscribe to @EchoesOfWisdomOfficial for daily ancient Stoic philosophy:\n"
            "https://www.youtube.com/@EchoesOfWisdomOfficial\n\n"
            "#stoicism #stoicmindset #powerofsilence #boundaries #shorts"
        ))
        st.text_area("YouTube Description", yt_desc, height=130, key="yt_desc_field")
        render_copy_deck("yt_d", "COPY YOUTUBE DESCRIPTION", yt_desc)

        yt_pin = pkg.get("youtube_pinned_comment", "When someone disrespects you: 1. Walk away in cold silence, or 2. Confront them directly? Drop 1 or 2 below. 👇")
        st.text_area("YouTube Pinned Debate Comment", yt_pin, height=75, key="yt_pin_field")
        render_copy_deck("yt_p", "COPY PINNED COMMENT", yt_pin)

        # --- FACEBOOK & INSTAGRAM REELS SUITE ---
        st.markdown("#### 🔵 FACEBOOK & INSTAGRAM REELS SUITE")
        fb_t = pkg.get("facebook_title", f"{pkg.get('hook_banner', 'Stoic Reel').title()} | Stoic Wisdom")
        st.text_input("Facebook Reel Title", fb_t, key="fb_title_field")
        render_copy_deck("fb_t", "COPY FACEBOOK TITLE", fb_t)

        # Dynamic high-converting Unicode Bold Caption
        raw_fb_hook = pkg.get("caption_hook", pkg.get("hook_banner", "NEVER ANNOUNCE YOUR EXIT"))
        bold_fb_hook = to_unicode_bold(re.sub(r'[^\w\s]', '', raw_fb_hook).strip().upper())
        fb_caption = (
            f"⚡ {bold_fb_hook} 🏛️\n\n"
            f"{pkg.get('caption_lesson', pkg['script'])}\n\n"
            f"🤔 {pkg.get('debate_question', 'When conflict strikes your peace:')}\n"
            f"1️⃣ {pkg.get('choice_1', 'Walk away in cold silence')}\n"
            f"2️⃣ {pkg.get('choice_2', 'Confront them directly')}\n\n"
            f"Drop 1 or 2 below. 👇\n\n"
            f"• Follow @EchoesOfWisdomOfficial for daily timeless clarity.\n\n"
            f"{pkg.get('facebook_hashtags', '#StoicMindset #EchoesOfWisdom #PowerOfSilence #Reels')}"
        )
        st.text_area("Facebook Reel Caption (with Unicode Bold)", fb_caption, height=200, key="fb_cap_field")
        render_copy_deck("fb_c", "COPY FACEBOOK CAPTION", fb_caption)

        st.markdown("""
        <div style="margin: 12px 0 16px 0;">
            <a href="https://business.facebook.com/latest/composer" target="_blank" style="text-decoration: none;">
                <button style="width: 100%; height: 3rem; background: #1877F2; color: white; border: none; border-radius: 8px; font-weight: 700; font-family: 'JetBrains Mono', monospace; font-size: 13px; cursor: pointer; box-shadow: 0 4px 15px rgba(24, 119, 242, 0.3);">
                    🌐 OPEN META BUSINESS SUITE SCHEDULER
                </button>
            </a>
        </div>
        """, unsafe_allow_html=True)

        if st.button("✅ Lock & Advance Slot", type="primary"):
            db["scheduled_videos"].append({
                "date": curr_date,
                "slot": curr_slot,
                "time": curr_time,
                "title": yt_t,
                "file": export_name
            })
            if pkg.get("hook_banner") not in db.get("used_hooks", []):
                db["used_hooks"].append(pkg.get("hook_banner"))
            db["last_scheduled_date"] = curr_date
            db["last_scheduled_slot"] = curr_slot
            save_db(db)
            
            # Compute new target for telemetry notification
            next_d, next_s, next_t = get_next_slot(curr_date, curr_slot)
            st.session_state["status_banner"] = f"✓ LOCKED: {export_name} scheduled for {curr_date} @ {curr_time} IST ({curr_slot}). Next slot advanced to: {next_d} @ {next_t} IST ({next_s})"
            del st.session_state["rendered_video_path"]
            del st.session_state["active_video_pkg"]
            st.rerun()

# --- TAB 3: QUEUE LEDGER ---
with tab_queue:
    st.markdown(f"### 📋 Scheduled Queue ({len(db.get('scheduled_videos', []))})")
    if not db.get("scheduled_videos"):
        st.info("No videos scheduled yet.")
    else:
        for item in reversed(db["scheduled_videos"]):
            st.markdown(f"""
            <div style="background: #0A0F1D; border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 8px; padding: 10px 14px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; font-family: 'JetBrains Mono', monospace; font-size: 12px;">
                <div>
                    <span style="color: #38BDF8; font-weight: 700;">{item.get('date')}</span>
                    <span style="color: #64748B;"> @ </span>
                    <span style="color: #FBBF24;">{item.get('time')} IST ({item.get('slot')})</span>
                    <div style="color: #F8FAFC; font-weight: 600; margin-top: 2px;">{item.get('title')}</div>
                    <div style="color: #64748B; font-size: 11px; margin-top: 1px;">📁 {item.get('file')}</div>
                </div>
                <div style="color: #34D399; font-weight: 700; font-size: 11px;">● SCHEDULED</div>
            </div>
            """, unsafe_allow_html=True)
