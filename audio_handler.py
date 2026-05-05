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
        # --- SYNC WITH LIVE DASHBOARD KEYS ---
        from keys import key_manager
        api_key = key_manager.get_key("DEEPGRAM")
        
        if not api_key:
            # Fallback to .env if dashboard is empty/failed
            dg_keys = [k.strip() for k in os.getenv("DEEPGRAM_API_KEYS", os.getenv("DEEPGRAM_API_KEY", "")).split(",") if k.strip()]
            if dg_keys:
                api_key = dg_keys[int(time.time()) % len(dg_keys)]
            else:
                self.error_occurred.emit("Deepgram API Keys not found! Please check dashboard.")
                self.is_running = False
                return

        uri = f"wss://api.deepgram.com/v1/listen?model=nova-3&language=en-US&smart_format=true&encoding=linear16&sample_rate={self.rate}&channels={self.channels}&endpointing=750&interim_results=true&diarize=false&punctuate=true"
        
        try:
            import ssl
            import certifi
            self.ws = websocket.create_connection(
                uri, 
                header=[f"Authorization: Token {api_key}"],
                sslopt={"ca_certs": certifi.where()}
            )
            print(f"[Audio] Intelligence Bridge Established. (Key: {api_key[:8]}...)")
            
            audio_queue = queue.Queue(maxsize=100) # Cap to ~10s of audio to prevent lag
            self.transcript_buffer = []
            self.last_transcript_time = time.time()

            # --- Thread 1: Mic Reader ---
            def mic_reader():
                print(f"[Audio] Initializing capture at {self.rate}Hz...")
                try:
                    speaker = sc.default_speaker()
                    mic = None
                    
                    # Try Loopback first (to hear interviewer)
                    try:
                        print(f"[Audio] Attempting loopback on: {speaker.name}")
                        mic = sc.get_microphone(id=speaker.name, include_loopback=True)
                    except Exception as e:
                        print(f"[Audio] Loopback failed: {e}. Falling back to default mic.")
                        mic = sc.default_microphone()
                    
                    if not mic:
                        self.error_occurred.emit("No audio capture device found.")
                        return

                    print(f"[Audio] Active Device: {mic.name}")
                    
                    with mic.recorder(samplerate=self.rate) as recorder:
                        while self.is_running and self.ws and self.ws.connected:
                            try:
                                data = recorder.record(numframes=int(self.rate * 0.1))
                                
                                # Boost quiet voices
                                max_val = np.max(np.abs(data))
                                if 0 < max_val < 0.05: data = data * 8.0
                                elif 0.05 <= max_val < 0.2: data = data * 3.0
                                    
                                data_int16 = (data[:, 0] * 32767).astype(np.int16)
                                if not audio_queue.full():
                                    audio_queue.put(data_int16.tobytes())
                            except Exception as e:
                                print(f"[Audio] Mic Stream Error: {e}")
                                break
                except Exception as e:
                    print(f"[Audio] Device Error: {e}")
                    self.error_occurred.emit(f"Audio Device Error: {str(e)}")

            threading.Thread(target=mic_reader, daemon=True).start()

            # --- Thread 2: Precision Sender ---
            def sender():
                last_send_time = time.time()
                silence_chunk = np.zeros(int(self.rate * 0.1), dtype=np.int16).tobytes()
                
                while self.is_running and self.ws and self.ws.connected:
                    try:
                        # Send real audio or keep-alive silence
                        try:
                            chunk = audio_queue.get(timeout=0.1)
                        except queue.Empty:
                            chunk = silence_chunk
                        
                        self.ws.send_binary(chunk)
                        
                        # Aggressive Keep-Alive (every 5 seconds)
                        if time.time() - last_send_time > 5:
                            self.ws.send(json.dumps({"type": "KeepAlive"}))
                            last_send_time = time.time()
                            
                    except Exception as e:
                        print(f"[Audio] Sender error: {e}")
                        break

            threading.Thread(target=sender, daemon=True).start()

            # --- Thread 3: Intelligence Receiver ---
            self.ws.settimeout(0.5)
            while self.is_running and self.ws and self.ws.connected:
                try:
                    raw_msg = self.ws.recv()
                    if not raw_msg: continue
                    msg = json.loads(raw_msg)
                    
                    if "channel" in msg:
                        transcript = msg["channel"]["alternatives"][0]["transcript"]
                        is_final = msg.get("is_final", False)
                        
                        if transcript:
                            if is_final:
                                self.transcript_buffer.append(transcript)
                                self.last_transcript_time = time.time()
                            else:
                                current_full = " ".join(self.transcript_buffer + [transcript])
                                self.partial_transcript_received.emit(current_full)
                                self.last_transcript_time = time.time()
                except websocket.WebSocketTimeoutException:
                    pass # Normal timeout to allow silence check
                except Exception as e:
                    print(f"[Audio] Receiver error: {e}")
                    break

                # --- NATURAL PAUSE DETECTION ---
                # If we have text and haven't heard anything for 1.5s, trigger AI
                if self.transcript_buffer and (time.time() - self.last_transcript_time > 1.5):
                    full_text = " ".join(self.transcript_buffer).strip()
                    if len(full_text) > 10: # Minimum length to avoid noise
                        self.transcript_received.emit(full_text)
                    self.transcript_buffer = []

        except Exception as e:
            print(f"[Audio] WebSocket Critical Error: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass
            self.ws = None
