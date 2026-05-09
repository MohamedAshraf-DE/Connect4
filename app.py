import base64
import mimetypes
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

import solver

APP_DIR = Path(__file__).resolve().parent

ASSETS = {
    "human_image": "Eisa Elwazaan.png",
    "referee_image": "sebaei.png",
    "ai_image": "khamis_kaka.png",
    "invalid_audio": "khamis.mp3",
    "ai_turn_audio": "thabet.mp3",
    "start_audio": "start.mp3",
    "lose_audio": "lose.mp4"
}

ALGORITHMS = {
    "Minimax without Alpha-Beta": "minimax",
    "Minimax with Alpha-Beta Pruning": "alpha-beta",
    "Expected Minimax": "expected-minimax",
}

st.set_page_config(
    page_title="Connect 4: Eissa vs Khamis",
    page_icon="🎮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

@st.cache_data(show_spinner=False)
def file_to_data_uri(filename: str) -> str | None:
    path = APP_DIR / filename
    if not path.exists():
        return None

    mime_type, _ = mimetypes.guess_type(path.name)
    if mime_type is None:
        mime_type = "application/octet-stream"

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"

def play_audio(filename: str, timeout: int = 0) -> None:
    uri = file_to_data_uri(filename)
    if uri is None:
        return
        
    mime = mimetypes.guess_type(filename)[0] or "audio/mp3"
    timeout_script = f"setTimeout(() => media.pause(), {timeout * 1000});" if timeout > 0 else ""

    components.html(
        f"""
        <script>
            var mime = "{mime}";
            var media = mime.startsWith("video") ? document.createElement("video") : new Audio();
            media.src = "{uri}";
            media.play().then(() => {{
                {timeout_script}
            }}).catch(e => console.log("Audio play blocked:", e));
        </script>
        """,
        height=0, width=0,
    )

def versus_banner_html(human_name: str, human_img: str, human_score: int, human_active: bool, comp_name: str, comp_img: str, comp_score: int, comp_active: bool, ref_img: str) -> str:
    h_uri = file_to_data_uri(human_img) or ""
    c_uri = file_to_data_uri(comp_img) or ""
    r_uri = file_to_data_uri(ref_img) or ""
    
    h_class = " active" if human_active else ""
    c_class = " active" if comp_active else ""

    h_markup = f'<img src="{h_uri}">' if h_uri else f'<div class="avatar-fallback">{"".join(p[0] for p in human_name.split()[:2])}</div>'
    c_markup = f'<img src="{c_uri}">' if c_uri else f'<div class="avatar-fallback">{"".join(p[0] for p in comp_name.split()[:2])}</div>'
    r_markup = f'<img src="{r_uri}">' if r_uri else f'<div class="avatar-fallback" style="font-size:1.5rem;">SB</div>'

    return f"""
    <div class="versus-arena">
        <div class="player-col{{h_class}}" style="--accent:#eab308;">
            <div class="avatar-ring">{{h_markup}}</div>
            <div class="player-info">
                <div class="role">Human</div>
                <div class="name">{{human_name}}</div>
                <div class="score-badge">{{human_score}}</div>
            </div>
        </div>
        
        <div class="referee-col">
            <div class="ref-avatar-wrapper">{{r_markup}}</div>
            <div class="vs-text">VS</div>
        </div>
        
        <div class="player-col{{c_class}}" style="--accent:#ef4444;">
            <div class="avatar-ring">{{c_markup}}</div>
            <div class="player-info">
                <div class="role">AI</div>
                <div class="name">{{comp_name}}</div>
                <div class="score-badge">{{comp_score}}</div>
            </div>
        </div>
    </div>
    """

def board_html(board: solver.Board) -> str:
    cells = []
    for row in board:
        for cell in row:
            if cell == solver.HUMAN:
                cls = "disc human-disc"
            elif cell == solver.COMPUTER:
                cls = "disc ai-disc"
            else:
                cls = "disc empty-disc"
            cells.append(f'<div class="{cls}"></div>')

    return f"""
    <div class="board-shell">
        <div class="board-grid">
            {''.join(cells)}
        </div>
    </div>
    """

def reset_game() -> None:
    st.session_state.board = solver.create_board()
    st.session_state.game_over = False
    st.session_state.move_log = []
    st.session_state.last_result = None
    st.session_state.last_trace = ""
    st.session_state.status = "Eissa Elwazaan's Turn"
    st.session_state.turn_label = "Eissa Elwazaan"
    st.session_state.heuristic_val = 0
    st.session_state.audio_to_play = None
    st.session_state.show_loss_screen = False

def ensure_state() -> None:
    if "board" not in st.session_state:
        reset_game()

def selected_algorithm() -> str:
    return ALGORITHMS[st.session_state.algorithm_label]

def is_expected_mode() -> bool:
    return selected_algorithm() == "expected-minimax"

def finish_if_full(note: str = "") -> bool:
    if not solver.is_board_full(st.session_state.board):
        return False

    st.session_state.game_over = True
    st.session_state.turn_label = "Game Over"
    summary = solver.winner_summary(st.session_state.board)
    st.session_state.status = f"{note} {summary}".strip()
    
    comp_score, human_score = solver.current_scores(st.session_state.board)
    if comp_score > human_score:
        st.session_state.show_loss_screen = True
        
    return True

def handle_human_move(col: int) -> None:
    board = st.session_state.board

    if st.session_state.game_over:
        st.session_state.status = "Game is over. Start a new game."
        st.session_state.audio_to_play = ASSETS["invalid_audio"]
        return

    if not solver.is_valid_column(board, col):
        st.session_state.status = f"Invalid move! Column {col} is full."
        st.session_state.audio_to_play = ASSETS["invalid_audio"]
        return

    actual_human_col = solver.apply_game_move(
        board,
        col,
        solver.HUMAN,
        stochastic=is_expected_mode(),
    )
    st.session_state.move_log.append(
        {
            "player": "Eissa Elwazaan",
            "intended": col,
            "actual": actual_human_col,
        }
    )

    human_note = f"Eissa dropped in column {actual_human_col}."
    if finish_if_full(human_note):
        return

    st.session_state.turn_label = "Khamis Kaka"
    st.session_state.status = f"{human_note} Khamis is thinking..."
    st.session_state.audio_to_play = ASSETS["start_audio"]

def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;800;900&display=swap');
        
        .stApp {
            background: #0f172a;
            color: #f8fafc;
            font-family: 'Outfit', sans-serif;
        }

        .block-container {
            padding-top: 2rem;
            max-width: 1300px;
        }

        .title-panel {
            text-align: center;
            margin-bottom: 2rem;
        }

        .title-panel h1 {{
            margin: 0;
            font-size: clamp(2rem, 6vw, 3.5rem);
            font-weight: 900;
            background: linear-gradient(to right, #3b82f6, #a855f7, #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .title-panel p {{
            margin: 0.5rem 0 0;
            font-size: clamp(1rem, 3vw, 1.2rem);
            color: #94a3b8;
            font-weight: 600;
        }}

        .versus-arena {{
            display: flex;
            align-items: stretch;
            justify-content: center;
            background: #1e293b;
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: 1px solid #334155;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            gap: 1rem;
        }}

        .player-col {{
            flex: 1;
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1rem;
            border-radius: 16px;
            background: rgba(15, 23, 42, 0.5);
            border: 2px solid transparent;
            transition: all 0.3s ease;
        }}

        .player-col.active {{
            border-color: var(--accent);
            background: rgba(255, 255, 255, 0.05);
            box-shadow: 0 0 20px rgba(0,0,0,0.3);
            transform: translateY(-3px);
        }}

        .player-col .avatar-ring {{
            width: clamp(50px, 12vw, 80px);
            height: clamp(50px, 12vw, 80px);
            border-radius: 50%;
            border: 3px solid var(--accent);
            flex-shrink: 0;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.4);
            background: #334155;
        }}
        
        .player-col .avatar-ring img {{
            width: 100%; height: 100%; object-fit: cover;
        }}

        .player-col:last-child {{
            flex-direction: row-reverse;
            text-align: right;
        }}

        .player-info {{
            display: flex;
            flex-direction: column;
            justify-content: center;
        }}

        .player-info .role {{
            font-size: clamp(0.7rem, 2vw, 0.8rem);
            color: #94a3b8;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .player-info .name {{
            font-size: clamp(0.9rem, 2.5vw, 1.4rem);
            color: #f8fafc;
            font-weight: 900;
            margin-bottom: 0.3rem;
            line-height: 1.2;
        }}

        .score-badge {{
            display: inline-block;
            background: #0f172a;
            padding: 0.2rem 0.8rem;
            border-radius: 8px;
            font-size: clamp(1rem, 2.5vw, 1.2rem);
            font-weight: 900;
            color: var(--accent);
            border: 1px solid #334155;
            width: fit-content;
        }}
        
        .player-col:last-child .score-badge {{
            margin-left: auto;
        }}

        .referee-col {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.5rem;
            padding: 0 0.5rem;
        }}

        .ref-avatar-wrapper {{
            width: clamp(40px, 8vw, 60px);
            height: clamp(40px, 8vw, 60px);
            border-radius: 50%;
            border: 2px solid #94a3b8;
            overflow: hidden;
            background: #334155;
            display: grid;
            place-items: center;
        }}
        
        .ref-avatar-wrapper img {{
            width: 100%; height: 100%; object-fit: cover;
        }}

        .vs-text {{
            font-size: clamp(1rem, 3vw, 1.5rem);
            font-weight: 900;
            color: #94a3b8;
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
            font-style: italic;
        }}

        @media (max-width: 768px) {{
            .versus-arena {{
                flex-direction: column;
                align-items: center;
                gap: 1rem;
                padding: 1rem;
            }}
            .player-col {{
                width: 100%;
                justify-content: flex-start;
                text-align: left;
                padding: 0.75rem;
            }}
            .player-col:last-child {{
                flex-direction: row;
                text-align: left;
            }}
            .player-col:last-child .score-badge {{
                margin-left: 0;
            }}
            .referee-col {{
                flex-direction: row;
            }}
        }}

        .board-shell {
            background: #2563eb;
            border-radius: 16px;
            padding: 1.5rem;
            box-shadow: 0 20px 40px rgba(0,0,0,0.4), inset 0 4px 0 rgba(255,255,255,0.2);
            border: 4px solid #1e40af;
            width: fit-content;
            margin: 0 auto;
        }

        .board-grid {{
            display: grid;
            grid-template-columns: repeat(7, 1fr);
            grid-template-rows: repeat(6, 1fr);
            gap: clamp(4px, 2vw, 12px);
        }}

        /* Force 7-column Streamlit row to never stack vertically */
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) {{
            flex-wrap: nowrap !important;
            gap: clamp(2px, 1.5vw, 12px) !important;
        }}
        div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) > div[data-testid="column"] {{
            min-width: 0 !important;
            width: calc(100% / 7) !important;
            flex: 1 1 0% !important;
        }}
        .stButton button {{
            padding-left: 0 !important;
            padding-right: 0 !important;
        }}

        .disc {
            width: clamp(35px, 5vw, 65px);
            height: clamp(35px, 5vw, 65px);
            border-radius: 50%;
            box-shadow: inset 0 8px 10px rgba(0,0,0,0.3);
            border: 2px solid #1e40af;
            background: #0f172a;
        }

        .human-disc {
            background: radial-gradient(circle at 35% 25%, #fde047, #eab308 50%, #854d0e 100%);
            box-shadow: 0 4px 8px rgba(0,0,0,0.4), inset 0 -4px 8px rgba(0,0,0,0.3);
            border: none;
        }

        .ai-disc {
            background: radial-gradient(circle at 35% 25%, #fca5a5, #ef4444 50%, #991b1b 100%);
            box-shadow: 0 4px 8px rgba(0,0,0,0.4), inset 0 -4px 8px rgba(0,0,0,0.3);
            border: none;
        }

        .status-panel {
            background: #1e293b;
            border-radius: 12px;
            padding: 1rem 1.5rem;
            margin: 1.5rem auto;
            text-align: center;
            border: 1px solid #334155;
            max-width: 800px;
        }

        .status-panel h2 {
            margin: 0 0 0.5rem 0;
            color: #f8fafc;
            font-size: 1.3rem;
            font-weight: 800;
        }

        .status-panel p {
            margin: 0;
            color: #94a3b8;
            font-size: 1rem;
        }

        .settings-strip {
            background: #1e293b;
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 2rem;
            border: 1px solid #334155;
            box-shadow: 0 10px 25px rgba(0,0,0,0.3);
        }
        
        .stButton button {
            background: #3b82f6 !important;
            color: white !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 800 !important;
            transition: all 0.2s !important;
            height: 40px !important;
        }
        
        .stButton button:hover {
            background: #2563eb !important;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(59, 130, 246, 0.4);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

ensure_state()
inject_styles()

st.markdown(
    """
    <div class="title-panel">
        <h1>Connect 4 Championship</h1>
        <p>The Ultimate Showdown: Eissa Elwazaan vs Khamis Kaka</p>
    </div>
    """,
    unsafe_allow_html=True,
)

game_started = len(st.session_state.move_log) > 0

# Settings
st.markdown('<div class="settings-strip">', unsafe_allow_html=True)
controls = st.columns([2, 1, 1])

with controls[0]:
    st.selectbox(
        "Select AI Algorithm",
        list(ALGORITHMS.keys()),
        key="algorithm_label",
        disabled=game_started and not st.session_state.game_over,
    )

with controls[1]:
    st.number_input(
        "Cutoff Depth (K)",
        min_value=1,
        max_value=8,
        value=3,
        step=1,
        key="k_depth",
        disabled=game_started and not st.session_state.game_over,
    )

with controls[2]:
    st.write("")
    st.write("")
    if st.button("🔄 Start New Game", use_container_width=True):
        reset_game()
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

computer_score, human_score = solver.current_scores(st.session_state.board)
heuristic_value = st.session_state.heuristic_val

st.markdown(
    versus_banner_html(
        human_name="Eissa Elwazaan",
        human_img=ASSETS["human_image"],
        human_score=human_score,
        human_active=(st.session_state.turn_label == "Eissa Elwazaan"),
        comp_name="Khamis Kaka",
        comp_img=ASSETS["ai_image"],
        comp_score=computer_score,
        comp_active=(st.session_state.turn_label == "Khamis Kaka"),
        ref_img=ASSETS["referee_image"]
    ),
    unsafe_allow_html=True
)

# Board drop buttons
st.markdown('<div style="width: fit-content; margin: 0 auto; margin-bottom: 0.5rem;">', unsafe_allow_html=True)
drop_cols = st.columns(solver.COLS)
clicked_column = None
for col, d_col in enumerate(drop_cols):
    with d_col:
        is_disabled = st.session_state.game_over or st.session_state.turn_label != "Eissa Elwazaan"
        if st.button("⬇️", key=f"drop_{col}", use_container_width=True, disabled=is_disabled):
            clicked_column = col
st.markdown('</div>', unsafe_allow_html=True)

# Render board
st.markdown(board_html(st.session_state.board), unsafe_allow_html=True)

# Status Panel
st.markdown(
    f"""
    <div class="status-panel">
        <h2>{st.session_state.status}</h2>
        <p>Last Heuristic Value evaluated: <strong>{heuristic_value}</strong></p>
    </div>
    """,
    unsafe_allow_html=True,
)

if clicked_column is not None:
    handle_human_move(clicked_column)
    st.rerun()

# Play audio logic
audio_played = None
if st.session_state.get("audio_to_play"):
    if st.session_state.audio_to_play == ASSETS["ai_turn_audio"]:
        play_audio(st.session_state.audio_to_play, timeout=3)
    else:
        play_audio(st.session_state.audio_to_play)
        
    audio_played = st.session_state.audio_to_play
    st.session_state.audio_to_play = None

if st.session_state.get("show_loss_screen"):
    video_uri = file_to_data_uri(ASSETS["lose_audio"])
    st.markdown(
        f"""
        <style>
            .loss-overlay {{
                position: fixed;
                top: 0; left: 0; width: 100vw; height: 100vh;
                background: rgba(15, 23, 42, 0.95);
                z-index: 999999;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                color: white;
                animation: fadeIn 1s ease-in-out;
            }}
            .loss-overlay h1 {{
                font-size: clamp(2.5rem, 6vw, 4rem);
                color: #ef4444;
                margin: 0 0 1rem 0;
                text-transform: uppercase;
                font-weight: 900;
                text-shadow: 0 0 20px rgba(239, 68, 68, 0.8);
                animation: shake 0.5s infinite;
                text-align: center;
            }}
            .loss-video-container {{
                width: 90%;
                max-width: 700px;
                max-height: 60vh;
                border: 4px solid #ef4444;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 0 40px rgba(239, 68, 68, 0.5);
                background: black;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .loss-video-container video {{
                width: 100%;
                max-height: 60vh;
                object-fit: contain;
                display: block;
            }}
            .close-loss-screen {{
                margin-top: 1.5rem;
                padding: 1rem 2rem;
                background: #ef4444;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 1.2rem;
                font-weight: bold;
                cursor: pointer;
                transition: background 0.2s;
            }}
            .close-loss-screen:hover {{
                background: #dc2626;
            }}
            @keyframes fadeIn {{
                from {{ opacity: 0; }}
                to {{ opacity: 1; }}
            }}
            @keyframes shake {{
                0% {{ transform: translate(1px, 1px) rotate(0deg); }}
                10% {{ transform: translate(-1px, -2px) rotate(-1deg); }}
                20% {{ transform: translate(-3px, 0px) rotate(1deg); }}
                30% {{ transform: translate(3px, 2px) rotate(0deg); }}
                40% {{ transform: translate(1px, -1px) rotate(1deg); }}
                50% {{ transform: translate(-1px, 2px) rotate(-1deg); }}
                60% {{ transform: translate(-3px, 1px) rotate(0deg); }}
                70% {{ transform: translate(3px, 1px) rotate(-1deg); }}
                80% {{ transform: translate(-1px, -1px) rotate(1deg); }}
                90% {{ transform: translate(1px, 2px) rotate(0deg); }}
                100% {{ transform: translate(1px, -2px) rotate(-1deg); }}
            }}
        </style>
        <div class="loss-overlay" id="loss-screen">
            <h1>EISSA ELWAZAAN LOST!</h1>
            <div class="loss-video-container">
                <video src="{video_uri}" autoplay playsinline controls></video>
            </div>
            <button class="close-loss-screen" onclick="document.getElementById('loss-screen').style.display='none'">Close</button>
        </div>
        """,
        unsafe_allow_html=True
    )

# AI logic execution separated to allow frontend to render Eissa's move first
if st.session_state.turn_label == "Khamis Kaka" and not st.session_state.game_over:
    if audio_played == ASSETS["start_audio"]:
        # Delay to give the browser time to play Eissa's audio before the spinner freezes the GIL
        time.sleep(2.8)
        
    with st.spinner("Khamis Kaka is calculating his next move..."):
        result = solver.choose_ai_move(
            st.session_state.board,
            algorithm=selected_algorithm(),
            k=int(st.session_state.k_depth),
            trace=True,
            max_trace_depth=min(int(st.session_state.k_depth), 3),
        )
        
    st.session_state.last_result = result
    st.session_state.last_trace = "\n".join(result.tree_trace)
    st.session_state.heuristic_val = result.value

    if result.best_column is None:
        finish_if_full("Khamis has no available moves.")
        st.rerun()

    actual_ai_col = solver.apply_game_move(
        st.session_state.board,
        result.best_column,
        solver.COMPUTER,
        stochastic=is_expected_mode(),
    )
    st.session_state.move_log.append(
        {
            "player": "Khamis Kaka",
            "intended": result.best_column,
            "actual": actual_ai_col,
            "value": result.value,
            "nodes": result.nodes_expanded,
            "time": result.running_time,
        }
    )

    ai_note = f"Khamis dropped in column {actual_ai_col}."
    
    if finish_if_full(ai_note):
        st.rerun()

    st.session_state.turn_label = "Eissa Elwazaan"
    st.session_state.status = ai_note
    st.session_state.audio_to_play = ASSETS["ai_turn_audio"]
    st.rerun()

st.divider()

# Expanders for Move log and AI tree trace
bot_left, bot_right = st.columns(2)

with bot_left:
    with st.expander("📝 Game Move Log", expanded=False):
        if not st.session_state.move_log:
            st.info("No moves have been made yet.")
        else:
            for move in st.session_state.move_log[::-1]:
                if move['player'] == "Eissa Elwazaan":
                    st.write(f"🧑 **Eissa Elwazaan** dropped disc in column {move['actual']}")
                else:
                    st.write(f"🤖 **Khamis Kaka** dropped disc in column {move['actual']} (Evaluated value: {move.get('value', 'N/A')})")

with bot_right:
    with st.expander("🌳 AI Tree Trace", expanded=False):
        if st.session_state.last_trace:
            st.code(st.session_state.last_trace, language="text")
        else:
            st.info("The minimax tree trace will appear here after the AI makes a move.")
