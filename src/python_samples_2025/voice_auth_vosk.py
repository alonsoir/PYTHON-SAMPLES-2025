import pyaudio
import wave
import os
import time
import requests
import zipfile
import shutil
from vosk import Model, KaldiRecognizer
import numpy as np

# Configuración de grabación
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Frecuencia de muestreo estándar para reconocimiento de voz
CHUNK = 1024
DURATION = 5  # Duración de cada grabación en segundos
NUM_MUESTRAS = 10  # Número total de grabaciones
OUTPUT_DIR = "dataset"  # Carpeta donde se guardarán los archivos
MODEL_DIR = "model"  # Carpeta donde se guardará el modelo Vosk

# Verificar si el archivo de prueba existe, si no, grabar el audio
def grabar_audio(archivo_salida="prueba_voz.wav", duracion=5, tasa_muestreo=16000):
    """
    Graba audio desde el micrófono y lo guarda en un archivo .wav.
    :param archivo_salida: Nombre del archivo donde se guardará el audio.
    :param duracion: Duración de la grabación en segundos.
    :param tasa_muestreo: Tasa de muestreo del audio (por defecto 16000 Hz).
    """
    p = pyaudio.PyAudio()

    # Configuración del micrófono
    flujo = p.open(format=pyaudio.paInt16,
                  channels=1,
                  rate=tasa_muestreo,
                  input=True,
                  frames_per_buffer=1024)

    print("Grabando...")

    # Crear el buffer para almacenar el audio
    frames = []

    # Grabar durante el tiempo especificado
    for _ in range(0, int(tasa_muestreo / 1024 * duracion)):
        data = flujo.read(1024)
        frames.append(data)

    print("Grabación finalizada.")

    # Guardar el archivo .wav
    with wave.open(archivo_salida, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(tasa_muestreo)
        wf.writeframes(b''.join(frames))

    # Cerrar el flujo
    flujo.stop_stream()
    flujo.close()
    p.terminate()

    print(f"Audio guardado como {archivo_salida}.")

# Verificar la existencia del archivo y crear uno si no existe
def verificar_y_grabar_audio(archivo_salida="prueba_voz.wav"):
    if not os.path.exists(archivo_salida):
        print(f"{archivo_salida} no encontrado. Procediendo a grabar audio...")
        grabar_audio(archivo_salida)
    else:
        print(f"{archivo_salida} ya existe. Usando archivo existente.")

import os
import zipfile
import urllib.request
from vosk import Model

MODEL_DIR = "model"
MODEL_SUBDIR = "vosk-model-small-en-us-0.15"  # Subcarpeta donde se encuentran los archivos del modelo
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"


def descargar_modelo():
    print("Modelo Vosk no encontrado. Descargando modelo...")
    zip_path = "model.zip"
    urllib.request.urlretrieve(MODEL_URL, zip_path)
    print(f"Modelo descargado a {zip_path}.")

    # Descomprimir el archivo ZIP
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(MODEL_DIR)
    print(f"Modelo extraído en {MODEL_DIR}.")

def cargar_modelo_vosk():
    model_path = os.path.join(MODEL_DIR, MODEL_SUBDIR)
    if not os.path.exists(model_path):
        raise Exception(f"El modelo no se encuentra en {model_path}. Asegúrate de que el modelo esté descargado y extraído correctamente.")
    
    print(f"Modelo Vosk cargado desde {model_path}")
    model = Model(model_path)
    return model

# Reconocer voz con Vosk
def reconocer_voz(audio_path, model):
    print(f"Reconociendo voz en {audio_path}...")
    wf = wave.open(audio_path, "rb")
    rec = KaldiRecognizer(model, wf.getframerate())
    
    # Reconocer cada fragmento de audio
    resultados = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            resultados.append(rec.Result())
    
    resultados.append(rec.FinalResult())
    return resultados

# Función para obtener el vector de identidad de la voz
def obtener_vector_identidad(audio_path, model):
    print(f"Obteniendo vector de identidad de la voz para {audio_path}...")
    resultados = reconocer_voz(audio_path, model)
    print("Resultados de reconocimiento:")
    for resultado in resultados:
        print(resultado)
    # Para este ejemplo, el 'vector de identidad' es solo el texto reconocido
    return resultados

# Entrenar un modelo con los audios de entrenamiento (dataset)
def entrenar_modelo(dataset_dir, model):
    print(f"Entrenando modelo con los audios en {dataset_dir}...")
    # Este proceso es simplificado. Idealmente, deberías extraer características acústicas y entrenar un modelo de reconocimiento
    # utilizando un enfoque de aprendizaje supervisado. Aquí solo mostramos un ejemplo de cómo reconocer los audios.
    vectores = []
    for archivo in os.listdir(dataset_dir):
        if archivo.endswith(".wav"):
            ruta_audio = os.path.join(dataset_dir, archivo)
            print(f"Entrenando con {ruta_audio}...")
            vectores.append(obtener_vector_identidad(ruta_audio, model))
    print("Entrenamiento completado.")

# Validar la autenticación de voz con el archivo de prueba
def autenticar_voz(prueba_audio, model, dataset_dir):
    print("Iniciando proceso de autenticación de voz...")
    # Primero, entrenamos el modelo con los audios de entrenamiento
    entrenar_modelo(dataset_dir, model)

    # Ahora, obtenemos el vector de identidad de la voz de prueba
    resultado_prueba = obtener_vector_identidad(prueba_audio, model)
    
    # Aquí deberías agregar un mecanismo para comparar el vector de identidad con los datos entrenados
    # En este caso, solo vamos a mostrar el texto reconocido y compararlo
    print(f"Resultado de la prueba de autenticación:")
    for resultado in resultado_prueba:
        print(resultado)
    
    # Ejemplo de puntuación de autenticación (esto sería más complejo en la realidad)
    puntuacion = 0.85  # Puntuación de autenticación ficticia (en un caso real se comparan vectores)
    print(f"Puntuación de autenticación: {puntuacion}")

    # Definir umbral de autenticación
    umbral = 0.80
    if puntuacion >= umbral:
        print("Autenticación exitosa.")
    else:
        print("Autenticación fallida.")

# Inicia el proceso
if __name__ == "__main__":
    verificar_y_grabar_audio("prueba_voz.wav")
    # Verificar si el modelo ya existe, si no, descargarlo
    if not os.path.exists(os.path.join(MODEL_DIR, MODEL_SUBDIR)):
        descargar_modelo()

    # Imprimir contenido del directorio del modelo
    print(f"Contenido de {MODEL_DIR}: {os.listdir(MODEL_DIR)}") 

    # Intentar cargar el modelo
    try:
        modelo_vosk = cargar_modelo_vosk()
        print("Modelo cargado correctamente.")
        # Autenticación de la voz
        autenticar_voz("prueba_voz.wav", modelo_vosk, OUTPUT_DIR)
    except Exception as e:
        print(f"Error al cargar el modelo: {e}")
    
    print("OK!")
