from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from gtts import gTTS
from langdetect import detect
import re, os, json
import subprocess
from datetime import datetime
from google.cloud import texttospeech
from google.oauth2 import service_account

import time
import json
from logging_config import setup_logger
from langdetect.lang_detect_exception import LangDetectException

logger = setup_logger()


app = FastAPI()

# Ghi chú:
# Đây là phần khởi tạo và cấu hình ban đầu cho ứng dụng FastAPI,
# bao gồm import các thư viện cần thiết và tạo instance cho app.
AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)
# Serve static files
app.mount("/audio", StaticFiles(directory="audio"), name="audio")

# ===== LOAD GOOGLE CREDENTIALS FROM ENV =====
credentials_info = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
credentials = service_account.Credentials.from_service_account_info(credentials_info)

tts_client = texttospeech.TextToSpeechClient(credentials=credentials)


SUPPORTED_LANGS = [
    'af','ar','bn','bs','ca','cs','cy','da','de','el','en','eo','es','et','fi',
    'fr','gu','hi','hr','hu','id','is','it','ja','jw','km','kn','ko','la','lv',
    'mk','ml','mr','my','ne','nl','no','pl','pt','ro','ru','si','sk','sq','sr',
    'su','sv','sw','ta','te','th','tl','tr','uk','ur','vi','zh-CN','zh-TW'
]


# -------- FIX REQUEST MODEL --------
class TextItem(BaseModel):
    text: str
    lang: str | None = None  # có thể null → auto detect
    speed: float | None = 1.0 # tốc độ phát âm (0.5 - 2.0)


class TextItemCGTTS(BaseModel):
    text: str
    lang: str | None = None
    speed: float | None = 1.0
    gender: str | None = "female"  # male | female

class TTSRequest(BaseModel):
    texts: list[TextItem]

class TTSRequestCGTTS(BaseModel):
    texts: list[TextItemCGTTS]

# -------- FUNCTION GENERATE AUDIO PATH --------
def generate_audio_path():
    now = datetime.now()

    year = now.strftime("%Y");
    month = now.strftime("%m");
    day = now.strftime("%d");

    folder = os.path.join(
        "audio",
        year,
        month,
        day
    )

    os.makedirs(folder, exist_ok=True)

    filename = now.strftime("%Y%m%d_%H%M%S_%f") + ".mp3"
    full_path = os.path.join(folder, filename)
    audio_url = f"audio/{year}/{month}/{day}/{filename}"

    return full_path, audio_url, filename
# -------- FUNCTION TTS --------
def convert_text_to_speech(text: str, lang: str | None, speed: float | None, base_url: str):
    # Auto-detect language nếu lang = None hoặc chuỗi rỗng
    if not lang:
        try:
            lang = detect(text)
            if lang == "no" and re.fullmatch(r"[A-Za-z0-9 ,.!?']+", text):
                lang = "en"
        except:
            return {"error": "Không thể nhận diện ngôn ngữ."}

    if lang not in SUPPORTED_LANGS:
        lang = "en"

    # Validate speed
    if speed is None:
        speed = 1.0
    if speed <= 0:
        speed = 1.0

    filepath, audio_url, filename = generate_audio_path()


    # Tạo audio bằng gTTS (không có tham số speed)
    tts = gTTS(text=text, lang=lang, slow=False)
    tts.save(filepath)

    # Nếu speed != 1 thì chỉnh tốc độ
    if speed != 1.0:
        temp_output = filepath.replace(".mp3", "_tmp.mp3")

        # Chạy ffmpeg filter: atempo = tốc độ
        subprocess.run([
            "ffmpeg", "-i", filepath,
            "-filter:a", f"atempo={speed}",
            "-vn",
            temp_output,
            "-y"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Ghi đè file cũ bằng file đã chỉnh tốc độ
        os.replace(temp_output, filepath)

    return {
        "detected_language": lang,
        "audio_url": f"{audio_url}"
    }



LANGUAGE_MAP = {
    # 🇻🇳 Vietnamese
    "vi": {
        "code": "vi-VN",
        "female": "vi-VN-Standard-A",
        "male": "vi-VN-Standard-B",
    },

    # 🇺🇸 English
    "en": {
        "code": "en-US",
        "female": "en-US-Standard-C",
        "male": "en-US-Standard-D",
    },

    # 🇫🇷 French
    "fr": {
        "code": "fr-FR",
        "female": "fr-FR-Standard-A",
        "male": "fr-FR-Standard-B",
    },

    # 🇩🇪 German
    "de": {
        "code": "de-DE",
        "female": "de-DE-Standard-A",
        "male": "de-DE-Standard-B",
    },

    # 🇯🇵 Japanese
    "ja": {
        "code": "ja-JP",
        "female": "ja-JP-Standard-A",
        "male": "ja-JP-Standard-C",
    },

    # 🇰🇷 Korean
    "ko": {
        "code": "ko-KR",
        "female": "ko-KR-Standard-A",
        "male": "ko-KR-Standard-C",
    },

    # 🇨🇳 Chinese (Simplified)
    "zh-cn": {
        "code": "cmn-CN",
        "female": "cmn-CN-Standard-A",
        "male": "cmn-CN-Standard-B",
    },
    "zh": {  # langdetect trả về zh
        "code": "cmn-CN",
        "female": "cmn-CN-Standard-A",
        "male": "cmn-CN-Standard-B",
    },

    # 🇹🇼 Chinese (Traditional)
    "zh-tw": {
        "code": "cmn-TW",
        "female": "cmn-TW-Standard-A",
        "male": "cmn-TW-Standard-B",
    },

    # 🇪🇸 Spanish
    "es": {
        "code": "es-ES",
        "female": "es-ES-Standard-A",
        "male": "es-ES-Standard-B",
    },

    # 🇮🇹 Italian
    "it": {
        "code": "it-IT",
        "female": "it-IT-Standard-A",
        "male": "it-IT-Standard-B",
    },

    # 🇵🇹 Portuguese (Brazil)
    "pt": {
        "code": "pt-BR",
        "female": "pt-BR-Standard-A",
        "male": "pt-BR-Standard-B",
    },

    # 🇷🇺 Russian
    "ru": {
        "code": "ru-RU",
        "female": "ru-RU-Standard-A",
        "male": "ru-RU-Standard-B",
    },

    # 🇹🇭 Thai
    "th": {
        "code": "th-TH",
        "female": "th-TH-Standard-A",
        "male": "th-TH-Standard-B",
    },

    # 🇮🇩 Indonesian
    "id": {
        "code": "id-ID",
        "female": "id-ID-Standard-A",
        "male": "id-ID-Standard-B",
    },

    # 🇳🇱 Dutch
    "nl": {
        "code": "nl-NL",
        "female": "nl-NL-Standard-A",
        "male": "nl-NL-Standard-B",
    },

    # 🇵🇱 Polish
    "pl": {
        "code": "pl-PL",
        "female": "pl-PL-Standard-A",
        "male": "pl-PL-Standard-B",
    },

    # 🇹🇷 Turkish
    "tr": {
        "code": "tr-TR",
        "female": "tr-TR-Standard-A",
        "male": "tr-TR-Standard-B",
    },

    # 🇺🇦 Ukrainian
    "uk": {
        "code": "uk-UA",
        "female": "uk-UA-Standard-A",
        "male": "uk-UA-Standard-B",
    },

    # 🇸🇦 Arabic
    "ar": {
        "code": "ar-XA",
        "female": "ar-XA-Standard-A",
        "male": "ar-XA-Standard-B",
    },

    # 🇮🇳 Hindi
    "hi": {
        "code": "hi-IN",
        "female": "hi-IN-Standard-A",
        "male": "hi-IN-Standard-B",
    },
}

def cgtts_convert_text_to_speech(text: str, lang: str | None, speed: float | None, gender: str | None):
    if not lang:
        try:
            lang = detect(text)
        except LangDetectException:
            logger.warning(f"LANG_DETECT_FAIL | text='{text[:50]}'")
            lang = "en"

    gender = gender if gender in ("male", "female") else "female"

    cfg = LANGUAGE_MAP.get(lang, LANGUAGE_MAP["en"])

    language_code = cfg["code"]
    voice_name = cfg[gender]

    speed = speed if speed and speed > 0 else 1.0

    filepath, audio_url, filename = generate_audio_path()

    #client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=voice_name,
        ssml_gender=(
            texttospeech.SsmlVoiceGender.FEMALE
            if gender == "female"
            else texttospeech.SsmlVoiceGender.MALE
        ),
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speed,
    )


    start = time.time()

    logger.info(
        f"TTS_START | lang={language_code} | voice={voice_name} | gender={gender}"
    )

    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
    )

    elapsed = (time.time() - start) * 1000

    logger.info(
        f"TTS_DONE | voice={voice_name} | time={elapsed:.2f}ms | chars={len(text)}"
    )


    with open(filepath, "wb") as out:
        out.write(response.audio_content)

    return {
        "language": language_code,
        "voice": voice_name,
        "audio_url": audio_url
    }

# -------- ROUTE API --------
@app.post("/tts")
async def text_to_speech(req: TTSRequest, request: Request):

    if not os.path.exists("audio"):
        os.makedirs("audio")

    base_url = str(request.base_url).rstrip("/")

    results = []

    for item in req.texts:
        result = convert_text_to_speech(item.text, item.lang, item.speed, base_url)
        results.append(result)

    return {"results": results}


@app.post("/cgtts")
async def cgtts_text_to_speech(req: TTSRequestCGTTS):

    results = []
    for item in req.texts:
        result = cgtts_convert_text_to_speech(
            item.text,
            item.lang,
            item.speed,
            item.gender
        )
        results.append(result)

    return {"results": results}

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()

    # đọc body (chỉ 1 lần!)
    body = await request.body()
    body_text = body.decode("utf-8") if body else ""

    # giới hạn log body
    if len(body_text) > 1000:
        body_text = body_text[:1000] + "...(truncated)"

    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"❌ ERROR | {request.method} {request.url.path} "
            f"| {process_time:.2f}ms | body={body_text} | error={str(e)}"
        )
        raise

    process_time = (time.time() - start_time) * 1000

    logger.info(
        f"✅ {request.method} {request.url.path} "
        f"| {status_code} | {process_time:.2f}ms "
        f"| ip={request.client.host if request.client else 'unknown'} "
        f"| body={body_text}"
    )

    return response
