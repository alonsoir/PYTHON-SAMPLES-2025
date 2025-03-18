import os
import wave
import audioop
import numpy as np
import requests
import zipfile
import soundfile as sf
import simpleaudio as sa
from pocketsphinx import AudioFile, get_model_path
from difflib import SequenceMatcher
import matplotlib.pyplot as plt

# Función para descargar y descomprimir el modelo de español si no existe
def download_and_extract_model(model_url, model_dir):
    if not os.path.exists(model_dir):
        print(f"Modelo de español no encontrado. Descargando desde {model_url}...")
        response = requests.get(model_url, stream=True)
        zip_path = os.path.join(model_dir, 'es-model.zip')
        with open(zip_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
        print("Descarga completada. Descomprimiendo el archivo...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_dir)
        os.remove(zip_path)  # Eliminar el archivo zip después de extraer
        print("Modelo descomprimido correctamente.")
    else:
        print("Modelo de español ya está presente.")

# Función para reproducir el audio
def play_audio(audio_path):
    data, samplerate = sf.read(audio_path)
    play_obj = sa.play_buffer((data * 32767).astype(np.int16), 1, 2, samplerate)
    play_obj.wait_done()

# Función para obtener la transcripción de un archivo de audio
def transcribe_audio(audio_path, spanish_model_path):
    config = {
        'verbose': True,
        'audio_file': audio_path,
        'hmm': spanish_model_path,  # Modelo acústico en español
        'lm': os.path.join(spanish_model_path, 'es-20k.lm.bin'),  # Lenguaje en español
        'dict': os.path.join(spanish_model_path, 'es.dict')  # Diccionario en español
    }
    
    audio = AudioFile(**config)
    transcription = ""
    
    for phrase in audio:
        transcription += str(phrase)
    return transcription

# Función para comparar dos transcripciones (similitud de texto)
def compare_transcriptions(transcription1, transcription2):
    return SequenceMatcher(None, transcription1, transcription2).ratio()

# Función para graficar las similitudes
def plot_similarity(similarity_scores, filenames):
    plt.figure(figsize=(10, 6))
    plt.bar(filenames, similarity_scores, color='skyblue')
    plt.xlabel('Archivos de Voz')
    plt.ylabel('Similitud (%)')
    plt.title('Similitud de Transcripciones')
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.show()

# URL para descargar el modelo de español
model_url = 'https://github.com/cmusphinx/es-alexa/archive/refs/heads/master.zip'
model_dir = os.path.join(os.getcwd(), 'es-alexa')

# Descargar y extraer el modelo si no existe
download_and_extract_model(model_url, model_dir)

# Directorio de audios
data_directory = os.path.join(os.getcwd(), 'dataset')

# Procesar todos los archivos .wav en la carpeta "dataset"
similarity_scores = []
filenames = []

for filename in os.listdir(data_directory):
    if filename.endswith(".wav"):
        file_path = os.path.join(data_directory, filename)
        print(f"\nProcesando archivo: {file_path}")

        # Reproducir el archivo de audio
        print(f"Reproduciendo {filename}...")
        play_audio(file_path)

        # Obtener la transcripción del archivo de audio
        transcription = transcribe_audio(file_path, model_dir)
        print(f"Texto reconocido de {filename}: {transcription}")

        # Almacenar las similitudes para el gráfico posterior
        filenames.append(filename)
        
# Procesar el archivo "prueba_voz.wav" para evaluar la similitud de voz
prueba_voz_path = os.path.join(os.getcwd(), 'prueba_voz.wav')
print(f"\nProcesando archivo de prueba: {prueba_voz_path}")

# Obtener la transcripción del archivo de prueba
prueba_voz_transcription = transcribe_audio(prueba_voz_path, model_dir)
print(f"Texto reconocido del archivo de prueba: {prueba_voz_transcription}")

# Comparar la transcripción del archivo de prueba con los archivos en 'dataset'
for filename in os.listdir(data_directory):
    if filename.endswith(".wav"):
        file_path = os.path.join(data_directory, filename)

        # Obtener la transcripción del archivo actual
        file_transcription = transcribe_audio(file_path, model_dir)

        # Comparar las transcripciones
        similarity = compare_transcriptions(prueba_voz_transcription, file_transcription)
        similarity_scores.append(similarity * 100)  # Convertir a porcentaje
        print(f"Similitud con {filename}: {similarity * 100:.2f}%")

# Graficar las similitudes
plot_similarity(similarity_scores, filenames)
