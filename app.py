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
# 2. WORKSPACE & CADENCE PERSISTENCE
# ---------------------------------------------------------
DATA_DIR = os.path.join(os.getcwd(), "data")
TMP_DIR = os.path.join(os.getcwd(), "tmp")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TMP_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "video_schedule.json")

def load_db():
    defaults = {
        "scheduled_videos": [],
        "used_hooks": [],
        "last_scheduled_date": None,
        "last_scheduled_slot": None
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

def get_next_slot():
    now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    last_d_str = db.get("last_scheduled_date")
    last_slot = db.get("last_scheduled_slot")

    if last_d_str and last_slot:
        last_d = datetime.strptime(last_d_str, "%Y-%m-%d").date()
        if last_slot == "SLOT 1":
            target_d = last_d
            target_slot = "SLOT 2"
            target_time = "20:00"
            display_slot = "Slot 2 (Evening)"
        else:
            target_d = last_d + timedelta(days=1)
            target_slot = "SLOT 1"
            target_time = "05:00"
            display_slot = "Slot 1 (Morning)"
    else:
        target_d = now_ist.date()
        if now_ist.hour < 5:
            target_slot = "SLOT 1"
            target_time = "05:00"
            display_slot = "Slot 1 (Morning)"
        elif now_ist.hour < 20:
            target_slot = "SLOT 2"
            target_time = "20:00"
            display_slot = "Slot 2 (Evening)"
        else:
            target_d = now_ist.date() + timedelta(days=1)
            target_slot = "SLOT 1"
            target_time = "05:00"
            display_slot = "Slot 1 (Morning)"

    return target_d.strftime("%Y-%m-%d"), target_slot, target_time, display_slot

# ---------------------------------------------------------
# 3. HIGH-RETENTION VIRAL THEMES MATRIX
# ---------------------------------------------------------
VIRAL_ANGLES = [
    {
        "theme": "The Silent Exit (Outgrowing Disrespect)",
        "premise": "Never announce when you cut someone off. Withdrawing your presence without an argument is the ultimate power move.",
        "macro_symbol": "An ancient heavy bronze portal latch locking into dark textured stone",
        "hook_starter": "NEVER ANNOUNCE YOUR EXIT"
    },
    {
        "theme": "The Cost of Being Likable (People Pleasing)",
        "premise": "Trying to please everyone is not kindness; it is weakness. When everyone likes you, nobody respects your boundaries.",
        "macro_symbol": "A weathered antique stone theater mask breaking apart on cobblestones",
        "hook_starter": "STOP TRYING TO BE LIKED"
    },
    {
        "theme": "Weaponized Indifference (Controlling Your Reaction)",
        "premise": "If their disrespect triggers your anger, you belong to them. Cold silence strips them of control instantly.",
        "macro_symbol": "A monolithic dark basalt stone resting unmoved against crashing stormy sea waves",
        "hook_starter": "YOUR REACTION GIVES THEM POWER"
    },
    {
        "theme": "Dopamine Bankruptcy (Mental Focus)",
        "premise": "You are not tired from hard work; you are drained from chasing worthless noise. Guard your stillness fiercely.",
        "macro_symbol": "An antique bronze oil lamp burning steadily down to deep glowing amber embers",
        "hook_starter": "YOU ARE DRAINED BY NOISE"
    },
    {
        "theme": "Quiet Execution (Never Brag)",
        "premise": "Never broadcast what you are building. The world flatters plans but only respects finished stone.",
        "macro_symbol": "A heavy blacksmith iron hammer striking a glowing hot blade on a dark stone anvil",
        "hook_starter": "BUILD IN COMPLETE OBSCURITY"
    },
    {
        "theme": "The Illusion of Future Ruin (Overthinking)",
        "premise": "We suffer ten times more in our thoughts than in reality. The catastrophe keeping you awake will never arrive.",
        "macro_symbol": "Cold morning mist dissolving completely over ancient stone arches under sunlight",
        "hook_starter": "YOU SUFFER IN YOUR HEAD"
    }
]

# ---------------------------------------------------------
# 4. EDGE-TTS WORD-LEVEL TIMESTAMPS ENGINE (NO WHISPER)
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
                    "word": chunk["text"],
                    "start": start_s,
                    "end": start_s + dur_s
                })
    return word_timings

def build_ass_subtitles(timed_words, ass_path, max_duration):
    dialogue_events = []
    chunk = []
    
    for i, tw in enumerate(timed_words):
        clean_w = re.sub(r'[^\w\s\',.!?-]', '', tw['word']).upper()
        chunk.append({'word': clean_w, 'start': tw['start'], 'end': tw['end']})
        is_punct = any(tw['word'].endswith(p) for p in ['.', '!', '?', ':', ';'])
        has_pause = (i + 1 < len(timed_words)) and (timed_words[i + 1]['start'] - tw['end'] >= 0.28)
        
        if is_punct or has_pause or len(chunk) >= 3:
            st_t = chunk[0]['start']
            en_t = min(max_duration, max(chunk[-1]['end'], st_t + 0.35))
            txt = " ".join([c['word'] for c in chunk]).strip()
            dialogue_events.append((st_t, en_t, txt))
            chunk = []
            
    if chunk:
        st_t = chunk[0]['start']
        en_t = min(max_duration, max(chunk[-1]['end'], st_t + 0.35))
        txt = " ".join([c['word'] for c in chunk]).strip()
        dialogue_events.append((st_t, en_t, txt))

    def ass_ts(s):
        h, m, sec = int(s // 3600), int((s % 3600) // 60), s % 60
        return f"{h}:{m:02d}:{sec:05.2f}"

    ass_content = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,76,&H0000E5FF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,6,3,2,50,50,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    for st_t, en_t, txt in dialogue_events:
        ass_content += f"Dialogue: 0,{ass_ts(st_t)},{ass_ts(en_t)},Default,,0,0,0,,{txt}\n"

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

# ---------------------------------------------------------
# 5. GEMINI SCRIPT & PROMPT GENERATOR (EXPLICIT INSTRUCTION)
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
    4. Google Flow Compliance:
       - Character MUST always be described as: 'An original fictional mature man with a weathered lined face, calm focused eyes, messy salt-and-pepper hair, thick beard, draped in an authentic dark woolen ancient mantle.'
       - Never use names like Marcus, Seneca, Epictetus in visual prompts.
       - Natural silence: 'Dignified silent composure, serene stoic expression, calm and steady gaze.'
       - Format: Every prompt must begin with '[4-second vertical 9:16 cinematic video clip]'.

    Output STRICT JSON matching this schema:
    {{
      "title_concept": "Short Concept Title",
      "hook_banner": "3-4 WORDS IN ALL CAPS",
      "script": "Full 65-70 word script with seamless loop.",
      "scene1_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 1 prompt",
      "scene2_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 2 prompt ({angle['macro_symbol']})",
      "scene3_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 3 prompt",
      "scene4_prompt": "[4-second vertical 9:16 cinematic video clip] Scene 4 prompt",
      "thumbnail_prompt": "High-contrast 9:16 vertical portrait prompt with bold hook text suggestion",
      "youtube_title": "High CTR Title #shorts #stoicism",
      "youtube_description": "Full description with handles and hashtags",
      "youtube_pinned_comment": "Debate question with 1️⃣/2️⃣ options"
    }}
    """

    err_list = []
    for mod in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
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
            err_list.append(f"{mod}: {e}")
            continue
            
    return None, " | ".join(err_list)

# ---------------------------------------------------------
# 6. HEADER & TELEMETRY DASHBOARD
# ---------------------------------------------------------
st.markdown("""
<div style="font-size: 24px; font-weight: 800; letter-spacing: -0.02em; color: #F8FAFC; margin-bottom: 8px;">
    🎬 ECHOES VIDEO STUDIO <span style="font-size: 13px; color: #38BDF8; font-family: 'JetBrains Mono', monospace; font-weight: 500;">v1.2 // PRODUCTION</span>
</div>
""", unsafe_allow_html=True)

target_date, target_slot, target_time, display_slot = get_next_slot()

st.markdown(f"""
<div class="telemetry-bar">
    <div class="badge badge-green"><span class="dot"></span> ENGINE: ONLINE</div>
    <div class="badge badge-blue">⚡ GEMINI + EDGE-TTS</div>
    <div class="badge badge-amber">📅 NEXT DROP: {target_date} @ {target_time} IST ({display_slot})</div>
</div>
""", unsafe_allow_html=True)

if "status_banner" in st.session_state:
    st.markdown(f"""
    <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10B981; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #34D399;">
        {st.session_state['status_banner']}
    </div>
    """, unsafe_allow_html=True)
    del st.session_state["status_banner"]

# Session-Safe API Key Resolution
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
# 7. TAB NAVIGATION (SYNTHESIZE -> RENDER -> AUDIT)
# ---------------------------------------------------------
tab_synth, tab_render, tab_queue = st.tabs(["⚡ 1. SCRIPT & PROMPTS", "🎬 2. RENDER MASTER REEL", "📋 3. QUEUE LEDGER"])

# --- TAB 1: SCRIPT & ALL 5 GOOGLE FLOW PROMPTS ---
with tab_synth:
    theme_options = ["🎲 Random / AI Choice"] + [a["theme"] for a in VIRAL_ANGLES]
    chosen_theme_name = st.selectbox("Stoic Psychological Angle", theme_options)
    
    if st.button("🚀 Generate Video Package & Spoken Audio", type="primary"):
        active_key = st.session_state.get("api_key", "").strip()
        if not active_key:
            st.error("Please enter your Gemini API Key in the '🔑 API CREDENTIALS' panel above.")
        else:
            with st.spinner("⚡ Synthesizing script & generating timed voiceover..."):
                if chosen_theme_name.startswith("🎲"):
                    angle_data = random.choice(VIRAL_ANGLES)
                else:
                    angle_data = next((a for a in VIRAL_ANGLES if a["theme"] == chosen_theme_name), VIRAL_ANGLES[0])

                package, err = generate_video_package(active_key, angle_data)
                if err or not package:
                    st.error(f"⚠️ Synthesis Failed: {err}")
                else:
                    audio_path = os.path.join(TMP_DIR, "audio.mp3")
                    word_timings = asyncio.run(synthesize_speech_timed(package["script"], audio_path))
                    
                    st.session_state["active_video_pkg"] = {
                        "package": package,
                        "audio_path": audio_path,
                        "timings": word_timings
                    }
                    st.success("✅ Script generated & voiceover synthesized with millisecond word sync!")

    if "active_video_pkg" in st.session_state:
        pkg = st.session_state["active_video_pkg"]["package"]
        st.divider()
        st.subheader(f"📜 Concept: {pkg.get('title_concept', 'Stoic Reel')}")
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
            prompt_text = pkg.get(key, "")
            st.text_area(label, prompt_text, height=75)
            escaped_prompt = json.dumps(prompt_text)
            components.html(f"""
            <button id="pbtn_{idx}" onclick="copyPrompt({idx})" style="width: 100%; height: 2.2rem; background: rgba(56, 189, 248, 0.15); color: #38BDF8; border: 1px solid rgba(56, 189, 248, 0.4); border-radius: 6px; font-weight: 700; font-family: monospace; font-size: 11px; cursor: pointer;">
                📋 COPY {label}
            </button>
            <script>
            function copyPrompt(i) {{
                var t = {escaped_prompt};
                navigator.clipboard.writeText(t).then(function() {{
                    var b = document.getElementById("pbtn_" + i);
                    b.innerText = "✓ COPIED!";
                    b.style.background = "#059669";
                    b.style.color = "#FFFFFF";
                    setTimeout(function() {{
                        b.innerText = "📋 COPY {label}";
                        b.style.background = "rgba(56, 189, 248, 0.15)";
                        b.style.color = "#38BDF8";
                    }}, 2000);
                }});
            }}
            </script>
            """, height=42)

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
    uploaded_music = st.file_uploader("Select MP3 track (or leave empty for voice only)", type=["mp3"])
    
    if st.button("🎬 Render Master 9:16 Vertical Reel", type="primary"):
        if "active_video_pkg" not in st.session_state:
            st.error("Please generate a script package in Tab 1 first.")
        elif not uploaded_clips or len(uploaded_clips) < 4:
            st.error(f"Please upload all 4 clips from Google Flow. (Uploaded: {len(uploaded_clips) if uploaded_clips else 0}/4)")
        else:
            with st.spinner("⚡ Assembling video, burning kinetic subtitles & balancing audio..."):
                pkg_data = st.session_state["active_video_pkg"]["package"]
                timings = st.session_state["active_video_pkg"]["timings"]
                audio_path = st.session_state["active_video_pkg"]["audio_path"]
                
                clip_paths = []
                for i, clip in enumerate(uploaded_clips[:4]):
                    c_path = os.path.join(TMP_DIR, f"clip_{i}.mp4")
                    with open(c_path, "wb") as f:
                        f.write(clip.read())
                    clip_paths.append(c_path)
                    
                probe_cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', audio_path]
                res = subprocess.run(probe_cmd, capture_output=True, text=True)
                vo_dur = float(res.stdout.strip()) if res.stdout.strip() else 24.0
                target_dur = vo_dur + 0.6
                per_clip_dur = target_dur / 4.0
                speed_factor = per_clip_dur / 4.0

                ass_path = os.path.join(TMP_DIR, "subtitles.ass")
                build_ass_subtitles(timings, ass_path, target_dur)

                logo_file = "logo.png" if os.path.exists("logo.png") else None
                banner_text = pkg_data.get("hook_banner", "MOVE IN SILENCE").replace("'", "\\'").replace(":", "\\:")
                out_video_path = os.path.join(TMP_DIR, "output_master.mp4")

                filter_chains = [
                    f"[0:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v0];"
                    f"[1:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v1];"
                    f"[2:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v2];"
                    f"[3:v]trim=0:4,setpts=(PTS-STARTPTS)*{speed_factor:.4f},scale=1512:2688:force_original_aspect_ratio=increase,crop=1080:1920:(in_w-1080)/2:(in_h-1920)/2[v3];"
                    f"[v0][v1][v2][v3]concat=n=4:v=1:a=0[vbase];"
                    f"[vbase]drawtext=text='{banner_text}':fontsize=44:fontcolor=0xFFE500:"
                    f"box=1:boxcolor=black@0.85:boxborderw=18:x=(w-text_w)/2:y=180:enable='between(t,0,3.5)',"
                    f"ass={ass_path}[v_sub]"
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
                    st.success("🎉 Master Reel Rendered Successfully!")

    if "rendered_video_path" in st.session_state:
        v_path = st.session_state["rendered_video_path"]
        st.video(v_path)
        
        pkg = st.session_state["active_video_pkg"]["package"]
        file_slug = re.sub(r'[^a-zA-Z0-9]', '_', pkg.get('hook_banner', 'stoic_reel')).lower()
        export_name = f"{target_date.replace('-', '')}_{file_slug}.mp4"

        with open(v_path, "rb") as f:
            v_bytes = f.read()

        st.download_button(
            label="💾 Download Master Reel (1080x1920 MP4)",
            data=v_bytes,
            file_name=export_name,
            mime="video/mp4"
        )

        st.markdown("### 📋 Formatted Metadata")
        st.text_input("YouTube Title", pkg.get("youtube_title", ""))
        st.text_area("YouTube Description", pkg.get("youtube_description", ""), height=120)
        st.text_area("Pinned Debate Comment", pkg.get("youtube_pinned_comment", ""), height=70)

        if st.button("✅ Lock & Advance Slot", type="primary"):
            db["scheduled_videos"].append({
                "date": target_date,
                "slot": target_slot,
                "time": target_time,
                "title": pkg.get("youtube_title", "Stoic Reel"),
                "file": export_name
            })
            if pkg.get("hook_banner") not in db.get("used_hooks", []):
                db["used_hooks"].append(pkg.get("hook_banner"))
            db["last_scheduled_date"] = target_date
            db["last_scheduled_slot"] = target_slot
            save_db(db)
            st.session_state["status_banner"] = f"✓ LOCKED: {export_name} scheduled for {target_date} @ {target_time} IST ({target_slot}). Slot advanced!"
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
                </div>
                <div style="color: #34D399; font-weight: 700; font-size: 11px;">● SCHEDULED</div>
            </div>
            """, unsafe_allow_html=True)
