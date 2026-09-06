import pjsua2 as pj
import threading
import queue
import requests
import time
import re
import os
import logging
import io
import wave
import speech_recognition as sr
from flask import Flask, jsonify

SIP_USER = os.environ.get('SIP_USER', 'sp4')
SIP_PASSWORD = os.environ.get('SIP_PASSWORD', 'sp4sp4')
SIP_DOMAIN = os.environ.get('SIP_DOMAIN', 'sip.linphone.org')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '8530962776:AAEN_0Qdtxtuhyd3sFtbkaleAZ6aNXePrkE')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID', '-1003593316438')
SAMPLE_RATE = 16000
LANGUAGE = 'en-US'
CHUNK_DURATION = 0.5

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
audio_queue = queue.Queue()
current_call = None
recording_thread = None
rec_file_path = None
last_read_frame = 0
processed_codes = set()
endpoint = None

def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': text}, timeout=10)
        if r.status_code == 200:
            logger.info(f"✅ Sent: {text}")
            return True
        return False
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False

def word_to_digit(text):
    mapping = {
        "zero":"0","one":"1","two":"2","three":"3","four":"4","five":"5","six":"6","seven":"7","eight":"8","nine":"9",
        "صفر":"0","واحد":"1","اثنان":"2","اثنين":"2","ثلاثة":"3","ثلاثه":"3","اربعة":"4","أربعة":"4","خمسة":"5","خمسه":"5",
        "ستة":"6","سته":"6","سبعة":"7","سبعه":"7","ثمانية":"8","ثمانيه":"8","تسعة":"9","تسعه":"9"
    }
    return mapping.get(text.lower(), None)

def extract_single_digit(text):
    m = re.search(r'(?:press|اضغط)\s+(?:on\s+)?(\d)', text, re.IGNORECASE)
    if m: return m.group(1)
    m = re.search(r'(?:press|اضغط)\s+(?:on\s+)?([a-zA-Z]+|[\u0600-\u06FF]+)', text, re.IGNORECASE)
    if m:
        d = word_to_digit(m.group(1))
        if d: return d
    return None

def extract_verification_code(text):
    patterns = [
        r'(?:رمز تحقيقك هو|your verification code is|رمز التحقق|verification code|code is)\s*[:\-]?\s*(\d{6})',
        r'(?:رمز تحقيقك هو|your verification code is|رمز التحقق|verification code|code is)\s*[:\-]?\s*(\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d[\s\-]?\d)',
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            code = re.sub(r'\D','',m.group(1))
            if len(code)==6: return code
    m = re.search(r'\b\d{6}\b', text)
    if m: return m.group(0)
    m = re.search(r'\b(\d[\s\-]?){6}\b', text)
    if m:
        code = re.sub(r'\D','',m.group(0))
        if len(code)==6: return code
    return None

def process_recognized_text(text):
    text = text.lower().strip()
    if not text: return
    logger.info(f"Recognized: {text}")
    digit = extract_single_digit(text)
    if digit:
        logger.info(f"Sending DTMF {digit}")
        send_dtmf_digit(digit)
    code = extract_verification_code(text)
    if code and code not in processed_codes:
        processed_codes.add(code)
        send_telegram(f"✅ كود تحقق واتساب: {code}")

def send_dtmf_digit(digit):
    global current_call
    if current_call:
        try:
            current_call.dialDtmf(digit)
            logger.info(f"DTMF sent: {digit}")
        except Exception as e:
            logger.error(f"DTMF error: {e}")

def audio_processing_loop():
    recognizer = sr.Recognizer()
    recognizer.energy_threshold = 300
    recognizer.dynamic_energy_threshold = True
    recognizer.pause_threshold = 0.5
    while True:
        try:
            pcm = audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue
        buf = io.BytesIO()
        with wave.open(buf,'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SAMPLE_RATE)
            wf.writeframes(pcm)
        buf.seek(0)
        try:
            with sr.AudioFile(buf) as source:
                audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=LANGUAGE)
            if text:
                process_recognized_text(text)
        except sr.UnknownValueError:
            pass
        except Exception as e:
            logger.error(f"STT error: {e}")

def capture_audio(call):
    global rec_file_path, last_read_frame, current_call
    rec_file_path = f"call_{int(time.time())}.wav"
    recorder = pj.CallRecorder(rec_file_path)
    try:
        call.startRecording(recorder)
        logger.info("Recording started")
    except Exception as e:
        logger.error(f"Rec start error: {e}")
        return
    last_read_frame = 0
    while current_call and current_call.is_valid():
        try:
            if os.path.exists(rec_file_path):
                with wave.open(rec_file_path,'rb') as wf:
                    wf.setpos(last_read_frame)
                    data = wf.readframes(int(SAMPLE_RATE*CHUNK_DURATION))
                    last_read_frame = wf.tell()
                    if data: audio_queue.put(data)
        except: pass
        time.sleep(CHUNK_DURATION)
    try:
        call.stopRecording(recorder)
    except: pass
    try:
        if os.path.exists(rec_file_path): os.remove(rec_file_path)
    except: pass

class MyAccount(pj.Account):
    def on_incoming_call(self, prm):
        global current_call
        try:
            call = MyCall(self, prm.callId)
            call_prm = pj.CallOpParam()
            call_prm.statusCode = 200
            call.answer(call_prm)
            current_call = call
            logger.info("Answered incoming call")
        except Exception as e:
            logger.error(f"Failed to answer: {e}")

class MyCall(pj.Call):
    def __init__(self, acc, call_id):
        pj.Call.__init__(self, acc, call_id)
    def on_call_state(self, prm):
        global current_call
        if self.info().state == pj.PJSIP_INV_STATE_DISCONNECTED:
            logger.info("Call disconnected")
            current_call = None
    def on_call_media_state(self, prm):
        global current_call, recording_thread
        if self.info().mediaState == pj.PJSUA_CALL_MEDIA_ACTIVE:
            current_call = self
            logger.info("Media active, starting capture")
            recording_thread = threading.Thread(target=capture_audio, args=(self,))
            recording_thread.daemon = True
            recording_thread.start()

def create_account():
    acc_cfg = pj.AccountConfig()
    acc_cfg.idUri = f"sip:{SIP_USER}@{SIP_DOMAIN}"
    acc_cfg.regConfig.registrarUri = f"sip:{SIP_DOMAIN}"
    cred = pj.AuthCredInfo("digest", "*", SIP_USER, 0, SIP_PASSWORD)
    acc_cfg.sipConfig.authCreds.append(cred)
    acc = MyAccount()
    acc.create(acc_cfg)
    logger.info(f"Account registered: {SIP_USER}")

def sip_main():
    global endpoint
    ep_cfg = pj.EpConfig()
    endpoint = pj.Endpoint()
    endpoint.libCreate()
    endpoint.libInit(ep_cfg)
    # إنشاء نقل UDP بشكل صريح قبل إضافة الحساب
    udp_cfg = pj.TransportConfig()
    udp_cfg.port = 0  # أي منفذ متاح
    endpoint.transportCreate(pj.PJSIP_TRANSPORT_TCP, udp_cfg)
    logger.info("UDP transport created")
    endpoint.libStart()
    create_account()
    threading.Thread(target=audio_processing_loop, daemon=True).start()
    send_telegram("🤖 تم تشغيل نظام استقبال مكالمات واتساب تلقائيًا")
    while True:
        endpoint.libHandleEvents(100)
        time.sleep(0.01)

@app.route('/')
def home(): return "WhatsApp SIP Bot is running."
@app.route('/health')
def health(): return jsonify({'status':'healthy'})

if __name__ == "__main__":
    threading.Thread(target=sip_main, daemon=True).start()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
