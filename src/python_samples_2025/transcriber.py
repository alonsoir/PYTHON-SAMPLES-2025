import pyaudio
import numpy as np
import queue
import threading
import time
import pyttsx3
import openai
import tempfile
import os
from dotenv import load_dotenv
import soundfile as sf

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de audio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024  # Tamaño de buffer
LISTEN_TIME = 5  # Segundos de escucha antes de procesar

# Inicializar PyAudio y la cola de audio
audio_queue = queue.Queue()
audio = pyaudio.PyAudio()

# Configurar el motor de voz
engine = pyttsx3.init()
engine.setProperty('rate', 150)  # Velocidad de habla

# Función para capturar audio en tiempo real
def record_audio():
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS,
                          rate=RATE, input=True,
                          frames_per_buffer=CHUNK)
        print("🎤 Asistente activado. Habla...")
        
        while True:
            frames = []
            start_time = time.time()
            
            while time.time() - start_time < LISTEN_TIME:
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                except Exception as e:
                    print(f"Error leyendo audio: {e}")
                    time.sleep(0.1)  # Pequeña pausa para recuperarse
            
            # Guardar audio en un archivo temporal
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
                sf.write(temp_file.name, audio_data, RATE)
                audio_queue.put(temp_file.name)
                
    except Exception as e:
        print(f"Error en la grabación: {e}")
        
# Función para transcribir y responder en tiempo real
def process_audio():
    while True:
        audio_file_path = audio_queue.get()
        
        try:
            # Comprobar que el archivo existe y tiene contenido
            if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
                # Transcribir con OpenAI Whisper API
                with open(audio_file_path, "rb") as audio_file:
                    transcription = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                    text = transcription.text.strip()
                
                # Eliminar el archivo temporal después de usarlo
                try:
                    os.unlink(audio_file_path)
                except Exception:
                    pass
                
                if text:
                    print(f"📝 Transcripción: {text}")
                    
                    # Consultar a OpenAI para la respuesta
                    response = openai.chat.completions.create(
                        model="gpt-3.5-turbo",
                        messages=[{"role": "user", "content": text}]
                    )
                    reply = response.choices[0].message.content
                    print(f"🤖 Respuesta: {reply}")
                    
                    # Leer la respuesta en voz alta
                    engine.say(reply)
                    engine.runAndWait()
            else:
                print("Archivo de audio vacío o no existe")
                
        except Exception as e:
            print(f"Error en el procesamiento: {e}")
            try:
                os.unlink(audio_file_path)
            except:
                pass

# Ejecutar en hilos separados
record_thread = threading.Thread(target=record_audio, daemon=True)
process_thread = threading.Thread(target=process_audio, daemon=True)
record_thread.start()
process_thread.start()

# Mantener el programa corriendo
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Deteniendo el asistente...")