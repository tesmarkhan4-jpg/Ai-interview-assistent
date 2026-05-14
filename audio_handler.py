import numpy as np
import websocket
import json
import threading
import soundcard as sc
import queue
import time
from PyQt6.QtCore import QThread, pyqtSignal
import sys
import os

class AudioThread(QThread):
    transcript_received = pyqtSignal(str)
    partial_transcript_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.is_running = False
        self.rate = 16000
        self.channels = 1
        self.ws = None
        self.transcript_buffer = []
        self.last_transcript_time = time.time()

    def run(self):
        self.is_running = True
        while self.is_running:
            try:
                self.start_streaming()
            except Exception as e:
                print(f"[Audio] Stream error: {e}")
                if self.is_running:
                    time.sleep(2)
            else:
                if self.is_running:
                    time.sleep(1)
        
    def start_streaming(self):
        # --- KEY ROTATION & SYNC ---
        from hwid_utils import key_manager
        api_key = key_manager.get_key("DEEPGRAM")
        
        if not api_key:
            dg_keys = [k.strip() for k in os.getenv("DEEPGRAM_API_KEYS", os.getenv("DEEPGRAM_API_KEY", "")).split(",") if k.strip()]
            if dg_keys:
                api_key = dg_keys[int(time.time()) % len(dg_keys)]
            else:
                self.error_occurred.emit("Deepgram API Key Missing!")
                self.is_running = False
                return

        # Using NOVA-3 for Ultra-Low Latency & High Accuracy
        uri = f"wss://api.deepgram.com/v1/listen?model=nova-3&language=en-US&smart_format=true&encoding=linear16&sample_rate={self.rate}&channels={self.channels}&endpointing=250&interim_results=true&diarize=false&punctuate=true"
        
        try:
            import ssl
            import certifi
            self.ws = websocket.create_connection(
                uri, 
                header=[f"Authorization: Token {api_key}"],
                sslopt={"ca_certs": certifi.where()}
            )
            print(f"[Audio] Intelligence Bridge Established. (Key: {api_key[:8]}...)")
            
            from auth_manager import auth_manager
            auth_manager.report_key_usage("Deepgram", api_key)
            
            audio_queue = queue.Queue(maxsize=100)
            self.transcript_buffer = []
            self.last_transcript_time = time.time()

            # --- Thread 1: Robust System Audio & Mic Reader ---
            def mic_reader():
                try:
                    mic = None
                    all_mics = sc.all_microphones(include_loopback=True)
                    speaker = sc.default_speaker()
                    for m in all_mics:
                        if m.isloopback and speaker.name in m.name:
                            mic = m
                            break
                    if not mic:
                        for m in all_mics:
                            if m.isloopback:
                                mic = m
                                break
                    if not mic:
                        try: mic = sc.get_microphone(id=speaker.name, include_loopback=True)
                        except: pass
                    if not mic: mic = sc.default_microphone()
                    if not mic: return

                    with mic.recorder(samplerate=self.rate) as recorder:
                        while self.is_running and self.ws and self.ws.connected:
                            try:
                                data = recorder.record(numframes=int(self.rate * 0.1))
                                data_mono = data[:, 0] if len(data.shape) > 1 else data
                                max_val = np.max(np.abs(data_mono))
                                if 0 < max_val < 0.05: data_mono = data_mono * 10.0 # Boost whispers
                                elif 0.05 <= max_val < 0.2: data_mono = data_mono * 4.0
                                data_int16 = (data_mono * 32767).astype(np.int16)
                                if not audio_queue.full(): audio_queue.put(data_int16.tobytes())
                            except: break
                except: pass

            threading.Thread(target=mic_reader, daemon=True).start()

            # --- Thread 2: Precision Sender ---
            def sender():
                last_send_time = time.time()
                silence_chunk = np.zeros(int(self.rate * 0.1), dtype=np.int16).tobytes()
                while self.is_running and self.ws and self.ws.connected:
                    try:
                        try:
                            chunk = audio_queue.get(timeout=0.1)
                        except queue.Empty:
                            chunk = silence_chunk
                        
                        self.ws.send_binary(chunk)
                        if time.time() - last_send_time > 5:
                            self.ws.send(json.dumps({"type": "KeepAlive"}))
                            last_send_time = time.time()
                    except: break

            threading.Thread(target=sender, daemon=True).start()

            # --- Thread 3: 'Smart Patient' Logic ---
            def flush_timer():
                while self.is_running and self.ws and self.ws.connected:
                    if self.transcript_buffer:
                        full_text = " ".join(self.transcript_buffer).strip()
                        low_text = full_text.lower()
                        
                        # 1. Question Trigger: (0.7s) - Respond fast to clear queries
                        if any(full_text.endswith(s) for s in ["?", "right", "correct"]):
                            threshold = 0.7
                        # 2. Cliffhangers: (3.0s) - Wait during thinking pauses
                        elif any(low_text.endswith(w) for w in ["the", "and", "your", "my", "how", "can", "could", "would", "is", "are", "but", "really", "mostly"]):
                            threshold = 3.0
                        # 3. Sentence Finish: (2.0s)
                        elif any(full_text.endswith(s) for s in [".", "!"]):
                            threshold = 2.0
                        # 4. Standard Pause: (1.5s)
                        else:
                            threshold = 1.5
                            
                        if (time.time() - self.last_transcript_time > threshold):
                            self.flush_now()
                    time.sleep(0.1)

            threading.Thread(target=flush_timer, daemon=True).start()

            # --- Intelligence Receiver ---
            self.ws.settimeout(0.5)
            while self.is_running and self.ws and self.ws.connected:
                try:
                    raw_msg = self.ws.recv()
                    if not raw_msg: continue
                    msg = json.loads(raw_msg)
                    
                    if "channel" in msg:
                        transcript = msg["channel"]["alternatives"][0]["transcript"].strip()
                        is_final = msg.get("is_final", False)
                        
                        if transcript:
                            if is_final:
                                self.transcript_buffer.append(transcript)
                                self.last_transcript_time = time.time()
                                self.partial_transcript_received.emit(" ".join(self.transcript_buffer))
                            else:
                                current_full = " ".join(self.transcript_buffer + [transcript])
                                self.partial_transcript_received.emit(current_full)
                                self.last_transcript_time = time.time()
                except websocket.WebSocketTimeoutException: pass
                except: break

        except Exception as e:
            print(f"[Audio] Critical Error: {e}")
        finally:
            if self.ws:
                try: self.ws.close()
                except: pass
                self.ws = None

    def stop(self):
        self.is_running = False
        if self.ws:
            try: self.ws.close()
            except: pass
            self.ws = None

    def flush_now(self):
        if hasattr(self, 'transcript_buffer') and self.transcript_buffer:
            full_text = " ".join(self.transcript_buffer).strip()
            if len(full_text) > 8:
                self.transcript_received.emit(full_text)
            self.transcript_buffer = []
            self.last_transcript_time = time.time()
