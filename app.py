from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from gtts import gTTS
from langdetect import detect
import uuid, re, os, json
import subprocess
from datetime import datetime
from google.cloud import texttospeech
from google.cloud import texttospeech
from google.oauth2 import service_account

app = FastAPI()

AUDIO_DIR = "audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

# ===== LOAD GOOGLE CREDENTIALS FROM ENV =====
credentials_info = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
credentials = service_account.Credentials.from_service_account_info(credentials_info)

tts_client = texttospeech.TextToSpeechClient(credentials=credentials)

# Serve static files
app.mount("/audio", StaticFiles(directory="audio"), name="audio")

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

def cgtts_convert_text_to_speech(text: str, lang: str | None, speed: float | None, gender: str | None):
    if not lang:
        lang = detect(text)

    if lang == "vi":
        language_code = "vi-VN"
        voice_name = "vi-VN-Standard-A" if gender == "female" else "vi-VN-Standard-B"
    else:
        language_code = "en-US"
        voice_name = "en-US-Standard-D"

    if not speed or speed <= 0:
        speed = 1.0

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

    response = tts_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config,
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
