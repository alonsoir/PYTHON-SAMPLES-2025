import speech_recognition as sr
import os
from pydub import AudioSegment
from pydub.playback import play
import time
import random

# Obtener el directorio actual
current_directory = os.getcwd()

# Definir la ruta completa de la carpeta "dataset"
dataset_path = os.path.join(current_directory, "dataset")

# Inicializar el reconocedor
recognizer = sr.Recognizer()

# Recorrer todos los archivos en la carpeta "dataset"
for filename in os.listdir(dataset_path):
    # Verificar si el archivo tiene extensión .wav
    if filename.endswith(".wav"):
        audio_path = os.path.join(dataset_path, filename)
        print(f"Procesando archivo: {audio_path}")

        # Reproducir el archivo de audio
        audio = AudioSegment.from_wav(audio_path)
        print(f"Reproduciendo {filename}...")
        play(audio)

        # Abrir el archivo de audio y realizar el reconocimiento de voz
        with sr.AudioFile(audio_path) as source:
            audio_data = recognizer.record(source)

        attempt = 0
        max_attempts = 3
        while attempt < max_attempts:
            try:
                # Intentar reconocer el audio
                text = recognizer.recognize_google(audio_data)
                print(f"Texto reconocido de {filename}: {text}")
                break  # Si se reconoce correctamente, salir del bucle
            except sr.UnknownValueError:
                print(f"Google Speech Recognition no pudo entender el audio en {filename}")
                break  # Si no puede entender, salir del bucle
            except sr.RequestError as e:
                print(f"No se pudo solicitar los resultados del servicio de Google Speech Recognition para {filename}; {e}")
                attempt += 1
                if attempt < max_attempts:
                    wait_time = random.uniform(2, 5)  # Espera aleatoria entre 2 y 5 segundos
                    print(f"Reintentando en {wait_time:.2f} segundos...")
                    time.sleep(wait_time)  # Esperar un tiempo aleatorio antes de reintentar
                else:
                    print("Se alcanzó el número máximo de intentos.")
                    break
            except ConnectionResetError:
                print(f"Error de conexión al procesar {filename}. Intentando nuevamente...")
                attempt += 1
                if attempt < max_attempts:
                    wait_time = random.uniform(5, 10)  # Espera aleatoria entre 5 y 10 segundos
                    print(f"Reintentando en {wait_time:.2f} segundos...")
                    time.sleep(wait_time)  # Esperar un tiempo aleatorio antes de reintentar
                else:
                    print("Se alcanzó el número máximo de intentos.")
                    break
