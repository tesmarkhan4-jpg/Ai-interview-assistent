import numpy as np
import websocket
import json
import threading
import soundcard as sc
import queue
import time
from PyQt6.QtCore import QThread, pyqtSignal
from keys import key_manager
import sys

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
        api_key = key_manager.get_key("DEEPGRAM")
        if not api_key:
            self.error_occurred.emit("Deepgram API Key not found!")
            self.is_running = False
            return

        uri = f"wss://api.deepgram.com/v1/listen?model=nova-3&language=en-US&smart_format=true&encoding=linear16&sample_rate={self.rate}&channels={self.channels}&endpointing=750&interim_results=true&diarize=false&punctuate=true"
        
        try:
            self.ws = websocket.create_connection(
                uri, 
                header=[f"Authorization: Token {api_key}"]
            )
            
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
                                
                                # --- INTELLIGENT AGC (Auto Gain Control) ---
                                # Boost quiet voices so Deepgram hears them better
                                max_val = np.max(np.abs(data))
                                if 0 < max_val < 0.05: # Extremely quiet
                                    data = data * 8.0 # Aggressive boost
                                elif 0.05 <= max_val < 0.2: # Quiet
                                    data = data * 3.0 # Moderate boost
                                    
                                data_int16 = (data[:, 0] * 32767).astype(np.int16)
                                if not audio_queue.full():
                                    audio_queue.put(data_int16.tobytes())
                            except Exception as e:
                                print(f"[Audio] Record error: {e}")
                                break
                except Exception as e:
                    print(f"[Audio] Mic Thread Critical Error: {e}")

            threading.Thread(target=mic_reader, daemon=True).start()

            # --- Thread 2: Precision Sender ---
            def sender():
                last_send_time = time.time()
                silence_chunk = np.zeros(int(self.rate * 0.1), dtype=np.int16).tobytes()
                while self.is_running and self.ws and self.ws.connected:
                    try:
                        data = audio_queue.get_nowait()
                        if self.ws and self.ws.connected:
                            self.ws.send_binary(data)
                            last_send_time = time.time()
                    except queue.Empty:
                        if time.time() - last_send_time >= 0.1:
                            if self.ws and self.ws.connected:
                                self.ws.send_binary(silence_chunk)
                                last_send_time = time.time()
                        time.sleep(0.01)
                    except:
                        break

            threading.Thread(target=sender, daemon=True).start()

            # --- Thread 3: 'Rapid Flush' Logic ---
            def flush_timer():
                while self.is_running and self.ws and self.ws.connected:
                    if self.transcript_buffer:
                        full_text = " ".join(self.transcript_buffer).strip()
                        low_text = full_text.lower()
                        
                        # --- AGGRESSIVE RESPONSE LOGIC ---
                        # 1. Question Trigger: (1.5s) - Allow for a natural pause after a question
                        if full_text.endswith("?"):
                            threshold = 1.5
                        # 2. Syntactic Cliffhanger: (5.0s) - Wait significantly longer for unfinished thoughts
                        elif any(low_text.endswith(w) for w in ["you", "about", "your", "the", "that", "how", "can", "could", "would", "is", "are", "for", "with", "of", "to", "and", "but", "or", "really", "very", "mostly", "if", "when", "be", "was", "were", "my", "our", "their", "this", "these", "those", "so", "because", "like"]):
                            threshold = 5.0
                        # 3. Sentence Finish (Period/Exclamation): (4.0s) - Wait for more sentences
                        elif full_text.endswith(".") or full_text.endswith("!"):
                            threshold = 4.0
                        # 4. Standard Pause: (5.0s) - General buffer
                        else:
                            threshold = 5.0
                            
                        if (time.time() - self.last_transcript_time > threshold):
                            self.flush_now()
                    time.sleep(0.1)

            threading.Thread(target=flush_timer, daemon=True).start()

            # --- Receiver Loop ---
            while self.is_running and self.ws and self.ws.connected:
                try:
                    msg = self.ws.recv()
                    data = json.loads(msg)
                    
                    if "channel" in data:
                        is_final = data.get("is_final")
                        alternatives = data["channel"].get("alternatives", [])
                        if alternatives:
                            sentence = alternatives[0].get("transcript", "").strip()
                            if sentence:
                                self.last_transcript_time = time.time() # Update timer for ALL incoming speech
                                if is_final:
                                    self.transcript_buffer.append(sentence)
                                    self.partial_transcript_received.emit(" ".join(self.transcript_buffer))
                                else:
                                    current_full = " ".join(self.transcript_buffer + [sentence])
                                    self.partial_transcript_received.emit(current_full)
                except:
                    break

        except Exception as e:
            print(f"[Audio] Connection failed: {e}")
        finally:
            if self.ws:
                try: self.ws.close()
                except: pass
                self.ws = None

    def flush_now(self):
        if self.transcript_buffer:
            full_text = " ".join(self.transcript_buffer).strip()
            if len(full_text) > 5:
                self.transcript_received.emit(full_text)
            self.transcript_buffer = []

    def stop(self):
        self.is_running = False
        if self.ws:
            try: self.ws.close()
            except: pass
        self.wait()
