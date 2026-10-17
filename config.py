import os, sys
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_DIR = os.path.join(BASE_DIR, "input")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

for d in [INPUT_DIR, OUTPUT_DIR, TEMP_DIR, ASSETS_DIR]:
    os.makedirs(d, exist_ok=True)

LANGUAGE = "French"
LANGUAGE_CODE = "fr"
CHANNEL_NAME = "EXECUTIVE FRENCH DIALOGUES"
TAGLINE = "Workplace Fluency, Diplomacy & Career Conversations"
DEFAULT_IMAGE_PATH = os.path.join(ASSETS_DIR, "business_studio.png")
LOGO_PATH = os.path.join(ASSETS_DIR, "executive_logo.png")

VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
VIDEO_FPS = 30

IS_SOLO = False

SUBTITLE_CENTER_X = 960
SUBTITLE_Y = 320
MAX_SUBTITLE_WIDTH = 620
SUBTITLE_FONT_SIZE = 44

VIS_CENTER_X = 960
VIS_BASE_Y = 540
VIS_NUM_BARS = 16
VIS_BAR_WIDTH = 12
VIS_BAR_SPACING = 12
VIS_MIN_HEIGHT = 4
VIS_MAX_HEIGHT = 56
VIS_COLOR = (255, 215, 0, 240)

VOICE_HOST1 = "fr-FR-DeniseNeural"
VOICE_HOST2 = "fr-FR-HenriNeural"
HOST1_NAME = "Camille"
HOST2_NAME = "Julien"
HOST1_SPEAKER = "female"
HOST2_SPEAKER = "male"
HOST1_PITCH = "+0Hz"
HOST2_PITCH = "+0Hz"
TTS_RATE = "-5%" if IS_SOLO else "+0%"
PAUSE_BETWEEN_TURNS = 0.50

MAX_WORDS_PER_LINE = 3
MAX_CHARS_PER_LINE = 22

POLLINATIONS_API_KEY = os.environ.get("POLLINATIONS_API_KEY", "")
POLLINATIONS_ENDPOINT = "https://gen.pollinations.ai/v1/chat/completions"
POLLINATIONS_MODEL = "gemini-fast"
NICHE_PROMPT = "professional, executive dialogue roleplaying workplace diplomacy, high-stakes negotiations, and career fluency in French"
SYSTEM_LANGUAGE_INSTRUCTION = "Generate all dialogue turns entirely in natural, elegant French suitable for native immersion."

FONT_CANDIDATES = [
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "C:\\Windows\\Fonts\\segoeuib.ttf",
    "C:\\Windows\\Fonts\\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
]
FONT_PATH = next((p for p in FONT_CANDIDATES if os.path.exists(p)), "arial.ttf")
FALLBACK_FONT_PATH = FONT_PATH
