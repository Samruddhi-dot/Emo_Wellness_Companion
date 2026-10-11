import base64
import html
import os
import tempfile
import threading

import pyttsx3
import speech_recognition as sr
import streamlit as st
from openai import OpenAI
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

WALLPAPER_PATH = os.path.join(os.path.dirname(__file__), "Emo_New.png")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
GROQ_TTS_MODEL = "canopylabs/orpheus-v1-english"
GROQ_TTS_VOICE = os.getenv("GROQ_TTS_VOICE", "autumn")
TTS_VOICE_OPTIONS = {
    "Local voice (pyttsx3)": "local",
    "Orpheus - Autumn": "autumn",
    "Orpheus - Diana": "diana",
    "Orpheus - Hannah": "hannah",
    "Orpheus - Austin": "austin",
    "Orpheus - Daniel": "daniel",
    "Orpheus - Troy": "troy",
}
HANDBOOK_RULES = """
You are Emo, a warm and calm educational mental-wellness companion.
Follow this handbook strictly:
- Listen, understand, validate, clarify, support, then offer one practical next step.
- Reflect feelings without assuming them; ask gentle questions.
- Never diagnose, prescribe, or claim to be a therapist, doctor, or emergency service.
- Do not encourage dependency, secrecy, retaliation, manipulation, or isolation.
- Offer suggestions as options, not commands. Do not force positivity.
- If there is immediate danger or self-harm intent, urge local emergency/crisis help and a trusted person.
- Keep replies conversational: write 60-100 words in 3-5 short sentences.
- Give one useful reflection, one practical option, and at most one gentle question.
- Do not write an essay, repeat the user's message, or exceed 100 words.
"""
GREETING = "Hey there, {name}! It is so wonderful to meet you! I am absolutely thrilled to have you here as a friend for this session."
END_PHRASES = ("end the call", "goodbye", "bye emo", "that's all", "that is all")


def speak_async(text):
    def run_speech():
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 165)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception:
            pass
    threading.Thread(target=run_speech, daemon=True).start()


def listen_to_user():
    recognizer = sr.Recognizer()
    recognizer.pause_threshold = 1.4
    recognizer.non_speaking_duration = 0.6
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.25)
        try:
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=60)
            return recognizer.recognize_google(audio)
        except sr.WaitTimeoutError:
            return "Error: Timeout waiting for voice input."
        except sr.UnknownValueError:
            return "Error: Could not understand the audio clearly."
        except sr.RequestError as error:
            return f"Error: Speech recognition service unavailable: {error}"
        except Exception as error:
            return f"Error: {error}"


def make_tts_audio(text, selected_voice):
    groq_key = os.getenv("GROQ_API_KEY")
    st.session_state.tts_error = None
    if selected_voice != "local" and groq_key and groq_key != "your_groq_api_key_here":
        try:
            output_path = os.path.join(tempfile.gettempdir(), "emo_reply.wav")
            client = Groq(api_key=groq_key)
            response = client.audio.speech.create(
                model=GROQ_TTS_MODEL,
                voice=selected_voice,
                input=text,
                response_format="wav",
            )
            response.write_to_file(output_path)
            with open(output_path, "rb") as audio_file:
                audio_bytes = audio_file.read()
            try:
                os.remove(output_path)
            except OSError:
                pass
            return audio_bytes
        except Exception as error:
            st.session_state.tts_error = (
                f"Groq voice '{selected_voice}' failed; using the local voice instead: {error}"
            )
    elif selected_voice != "local":
        st.session_state.tts_error = (
            "Groq API key is missing or still a placeholder; using the local voice instead."
        )

    temp_path = os.path.join(tempfile.gettempdir(), "emo_reply.wav")
    engine = pyttsx3.init()
    engine.setProperty("rate", 165)
    engine.save_to_file(text, temp_path)
    engine.runAndWait()
    engine.stop()
    with open(temp_path, "rb") as audio_file:
        audio_bytes = audio_file.read()
    try:
        os.remove(temp_path)
    except OSError:
        pass
    return audio_bytes


def generate_reply(messages):
    client = OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")
    response = client.chat.completions.create(
        model=OLLAMA_MODEL,
        messages=messages,
        temperature=0.5,
        max_tokens=140,
        extra_body={"keep_alive": "10m"},
    )
    return (response.choices[0].message.content or "").strip()


def add_history(role, text):
    st.session_state.history.append({"role": role, "text": text})


def reset_state():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


st.set_page_config(page_title="Emo wellness companion", page_icon=":material/self_improvement:", layout="wide")
if "history" not in st.session_state:
    st.session_state.history = []
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": HANDBOOK_RULES}]
for key, value in {"name": "", "connected": False, "ended": False, "muted": False, "last_audio": None, "current_user_text": "", "current_emo_text": "", "tts_voice": GROQ_TTS_VOICE if GROQ_TTS_VOICE in TTS_VOICE_OPTIONS.values() else "local", "tts_error": None, "error": None}.items():
    if key not in st.session_state:
        st.session_state[key] = value

if os.path.exists(WALLPAPER_PATH):
    with open(WALLPAPER_PATH, "rb") as wallpaper:
        wallpaper_data = base64.b64encode(wallpaper.read()).decode()
    st.markdown(f"""<style>
    .stApp {{ background-image: url(data:image/png;base64,{wallpaper_data}); background-size: cover; background-attachment: fixed; }}
    [data-testid="stAppViewContainer"] > .main {{ background: rgba(10,18,28,.78); }}
    [data-testid="stCaptionContainer"] {{ background: transparent !important; border: 0 !important; box-shadow: none !important; }}
    .subtitle {{ color: rgba(255,255,255,.72); margin: -10px 0 18px; }}
    .exchange-copy {{ box-sizing: border-box; width: 100%; max-width: 720px; height: 120px; margin: 10px auto 0 0; padding: 12px 14px; overflow-x: hidden; overflow-y: auto; text-align: left; overflow-wrap: anywhere; }}
    .turn-text {{ margin: 0 0 12px; text-align: left; overflow-wrap: anywhere; }}
    .footer {{ color: rgba(255,255,255,.62); font-size: .78rem; text-align: center; margin-top: .5rem; padding-bottom: 1rem; }}
    .emo-card {{ background: rgba(14,24,36,.9); border: 1px solid rgba(255,255,255,.16); border-radius: 18px; padding: 1.25rem; }}
    .waveform {{ display: flex; align-items: center; justify-content: center; gap: 6px; width: 50%; height: 70px; margin: 8px auto 55px; transform: translateX(252px); }}
    .waveform span {{ width: 3px; height: 9px; border-radius: 5px; background: #63d8b0; animation: wave 1s ease-in-out infinite; }}
    @keyframes wave {{ 0%, 100% {{ height: 8px; opacity: .55; }} 50% {{ height: 34px; opacity: 1; }} }}
    </style>""", unsafe_allow_html=True)

st.write("Hey there!")
st.title("I'm Emo")
st.markdown("<div class='subtitle'>Your Wellness AI Companion✨</div>", unsafe_allow_html=True)
with st.sidebar:
    st.header("Your session")
    if st.session_state.name:
        st.success(f"Emo remembers: {st.session_state.name}")
    st.toggle("Mute Emo", key="muted")
    voice_labels = list(TTS_VOICE_OPTIONS)
    selected_voice_label = st.selectbox(
        "Emo voice",
        voice_labels,
        index=next(
            (index for index, label in enumerate(voice_labels) if TTS_VOICE_OPTIONS[label] == st.session_state.tts_voice),
            0,
        ),
        help="Choose an Orpheus voice or use the local pyttsx3 voice.",
    )
    st.session_state.tts_voice = TTS_VOICE_OPTIONS[selected_voice_label]
    if st.session_state.ended:
        st.subheader("Conversation history")
        for turn in st.session_state.history:
            st.markdown(f"**{'You' if turn['role'] == 'user' else 'Emo'}**")
            st.write(turn["text"])
        if st.button("Start a new session"):
            reset_state()

if not st.session_state.connected and not st.session_state.ended:
    st.subheader("Meet Emo")
    st.write("Hi, what should I call you?")
    name = st.text_input("Name Emo should use", placeholder="Your name")
    if st.button("Start with Emo", type="primary", icon=":material/phone_in_talk:"):
        st.session_state.name = name.strip() or "friend"
        greeting = GREETING.format(name=st.session_state.name)
        st.session_state.messages.extend([
            {"role": "user", "content": f"The user's name is {st.session_state.name}."},
            {"role": "assistant", "content": greeting},
        ])
        add_history("assistant", greeting)
        st.session_state.current_emo_text = greeting
        if not st.session_state.muted:
            st.session_state.last_audio = make_tts_audio(greeting, st.session_state.tts_voice)
        st.session_state.connected = True
        st.rerun()
    st.stop()

exchange_lines = []
if st.session_state.current_user_text:
    exchange_lines.append(
        f"<div class='turn-text'><strong>You:</strong> {html.escape(st.session_state.current_user_text)}</div>"
    )
if st.session_state.current_emo_text:
    exchange_lines.append(
        f"<div class='turn-text'><strong>Emo:</strong> {html.escape(st.session_state.current_emo_text)}</div>"
    )
st.markdown(
    f"<div class='exchange-copy'>{''.join(exchange_lines)}</div>",
    unsafe_allow_html=True,
)
if st.session_state.last_audio and not st.session_state.muted:
    waveform_bars = "".join(
        f"<span style='animation-delay: {((index % 14) - 7) * 0.07:.2f}s'></span>"
        for index in range(35)
    )
    st.markdown(f"<div class='waveform' aria-label='Speech waveform'>{waveform_bars}</div>", unsafe_allow_html=True)
    st.audio(st.session_state.last_audio, format="audio/wav", autoplay=True)
if st.session_state.tts_error:
    st.warning(st.session_state.tts_error)
    st.session_state.tts_error = None
if st.session_state.error:
    st.warning(st.session_state.error)
    st.session_state.error = None

if not st.session_state.ended:
    st.caption("Click Start speaking, then pause for about two seconds. The pause submits your turn automatically.")
    if st.button("Start speaking", type="primary", icon=":material/mic:"):
        with st.spinner("Listening... speak naturally, then pause."):
            transcript = listen_to_user()
        if transcript.startswith("Error:"):
            st.session_state.error = transcript
        else:
            st.session_state.current_user_text = transcript
            st.session_state.messages.append({"role": "user", "content": transcript})
            add_history("user", transcript)
            try:
                reply = generate_reply(st.session_state.messages)
                st.session_state.current_emo_text = reply
                st.session_state.messages.append({"role": "assistant", "content": reply})
                add_history("assistant", reply)
                if not st.session_state.muted:
                    st.session_state.last_audio = make_tts_audio(reply, st.session_state.tts_voice)
            except Exception as error:
                st.session_state.error = f"Emo could not respond. Is Ollama running with {OLLAMA_MODEL}? {error}"
        if any(phrase in transcript.lower() for phrase in END_PHRASES):
            st.session_state.ended = True
        st.rerun()
    if st.button("End call", icon=":material/call_end:"):
        st.session_state.ended = True
        st.rerun()
else:
    st.success("Call ended. Your complete history is available in the sidebar.")

st.markdown(
    "<div class='footer'>Made with ❤️ by Samruddhi</div>",
    unsafe_allow_html=True,
)
