import pyaudio
import numpy as np
import queue
import threading
import time
import pyttsx3
import openai
import tempfile
import os
import requests
import json
import soundfile as sf
from dotenv import load_dotenv
import subprocess

# Cargar variables de entorno
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# Configuración de Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"  # Valor inicial, se actualizará con la selección

# Documentos de ejemplo
documents = [
    "My name is Jean and I live in Paris.",
    "My name is Mark and I live in Berlin.",
    "My name is Giorgio and I live in Rome."
]

# Configuración de audio
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
LISTEN_TIME = 5

# Inicializar PyAudio y la cola de audio
audio_queue = queue.Queue()
audio = pyaudio.PyAudio()

# Configurar el motor de voz
engine = pyttsx3.init()
engine.setProperty('rate', 150)

def simple_search(query, documents):
    """Busca documentos relevantes basados en la consulta."""
    relevant_docs = []
    query_words = set(query.lower().split())
    for doc in documents:
        doc_words = set(doc.lower().split())
        if query_words.intersection(doc_words):
            relevant_docs.append(doc)
    return relevant_docs if relevant_docs else documents

def generate_response_ollama(query, relevant_docs):
    """Genera una respuesta usando Ollama basada en documentos relevantes."""
    prompt = f"""
Given these documents, answer the question.
Documents:
{chr(10).join(['- ' + doc for doc in relevant_docs])}

Question: {query}
Answer:
"""
    data = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    try:
        response = requests.post(OLLAMA_URL, json=data)
        response.raise_for_status()
        return response.json().get("response", "Lo siento, no pude generar una respuesta.")
    except requests.exceptions.RequestException as e:
        print(f"Error al llamar a Ollama: {e}")
        return f"Error al comunicarse con Ollama: {e}"

def record_audio():
    """Graba audio del micrófono y lo coloca en la cola."""
    try:
        stream = audio.open(format=FORMAT, channels=CHANNELS,
                            rate=RATE, input=True,
                            frames_per_buffer=CHUNK)
        print("🎤 Asistente RAG con Ollama activado. Habla para hacer una pregunta...")
        while True:
            print("🎤 Escuchando...")
            frames = []
            start_time = time.time()
            while time.time() - start_time < LISTEN_TIME:
                data = stream.read(CHUNK, exception_on_overflow=False)
                frames.append(data)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                audio_data = np.frombuffer(b''.join(frames), dtype=np.int16)
                sf.write(temp_file.name, audio_data, RATE)
                audio_queue.put(temp_file.name)
    except Exception as e:
        print(f"Error en la grabación: {e}")
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()

def process_audio():
    """Procesa el audio de la cola, lo transcribe y genera una respuesta."""
    while True:
        audio_file_path = audio_queue.get()
        try:
            if os.path.exists(audio_file_path) and os.path.getsize(audio_file_path) > 0:
                with open(audio_file_path, "rb") as audio_file:
                    transcription = openai.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )
                    question = transcription.text.strip()
                os.unlink(audio_file_path)
                if question:
                    print(f"📝 Pregunta transcrita: {question}")
                    relevant_docs = simple_search(question, documents)
                    reply = generate_response_ollama(question, relevant_docs)
                    print(f"🤖 Respuesta: {reply}")
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

def ensure_ollama_running():
    """Verifica si Ollama está corriendo y lo inicia si no lo está."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama ya está corriendo.")
            return True
    except requests.exceptions.ConnectionError:
        print("❌ Ollama no está corriendo. Intentando iniciarlo...")
        return start_ollama()

def start_ollama():
    """Inicia Ollama en segundo plano."""
    try:
        subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print("⏳ Iniciando Ollama...")
        return wait_for_ollama()
    except Exception as e:
        print(f"⚠️ Error al iniciar Ollama: {e}")
        print("Asegúrate de que Ollama esté instalado y accesible desde la línea de comandos.")
        return False

def wait_for_ollama():
    """Espera hasta que Ollama esté listo."""
    max_attempts = 10
    attempt = 0
    while attempt < max_attempts:
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                print("✅ Ollama está listo.")
                return True
        except requests.exceptions.ConnectionError:
            time.sleep(1)
            attempt += 1
    print("❌ No se pudo conectar a Ollama después de varios intentos.")
    return False

def check_ollama():
    """Verifica Ollama, selecciona un modelo y asegura que esté corriendo."""
    global OLLAMA_MODEL
    if not ensure_ollama_running():
        print("❌ No se pudo iniciar Ollama. El programa no puede continuar.")
        exit(1)
    try:
        response = requests.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            models = response.json().get("models", [])
            if models:
                available_models = [model["name"] for model in models]
                print("Modelos disponibles en Ollama:")
                for i, model in enumerate(available_models, 1):
                    print(f"{i}. {model}")
                while True:
                    try:
                        choice = input("Selecciona el número del modelo que deseas usar: ")
                        selected_index = int(choice) - 1
                        if 0 <= selected_index < len(available_models):
                            OLLAMA_MODEL = available_models[selected_index]
                            print(f"Modelo seleccionado: {OLLAMA_MODEL}")
                            break
                        else:
                            print("Número inválido. Intenta de nuevo.")
                    except ValueError:
                        print("Por favor, ingresa un número válido.")
            else:
                print("No hay modelos disponibles en Ollama. Instala un modelo con: ollama pull llama3")
        else:
            print("Error al conectar con Ollama")
    except requests.exceptions.RequestException:
        print("⚠️ No se puede conectar a Ollama. Asegúrate de que esté ejecutándose con: ollama serve")

# Asegurarse de que Ollama esté corriendo y seleccionar modelo
check_ollama()

# Ejecutar en hilos separados
record_thread = threading.Thread(target=record_audio, daemon=True)
process_thread = threading.Thread(target=process_audio, daemon=True)
record_thread.start()
process_thread.start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Deteniendo el asistente...")