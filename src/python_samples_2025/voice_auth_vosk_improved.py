import os
import zipfile
import urllib.request
from vosk import Model, KaldiRecognizer
import tqdm
import wave
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# Definición de las rutas
MODEL_DIR = "model"
MODEL_SUBDIR = "vosk-model-small-es-0.22"  # Subcarpeta del modelo en español
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.22.zip"  # URL del modelo en español

def descargar_modelo():
    """
    Descarga y descomprime el modelo de Vosk si no está presente.
    """
    try:
        print("Modelo Vosk no encontrado. Iniciando la descarga del modelo...")
        zip_path = "model.zip"
        # Usamos urllib para descargar el archivo con una barra de progreso
        with tqdm.tqdm(unit='B', unit_scale=True, miniters=1, desc="Descargando modelo") as bar:
            urllib.request.urlretrieve(MODEL_URL, zip_path, reporthook=lambda blocknum, blocksize, totalsize: bar.update(blocksize))
        
        print(f"Modelo descargado correctamente a {zip_path}. Procediendo a descomprimir...")

        # Descomprimir el archivo ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(MODEL_DIR)
            print(f"Modelo extraído en {MODEL_DIR}.")
        
        # Limpiar archivo ZIP descargado
        os.remove(zip_path)
        print("Archivo ZIP eliminado tras la extracción.")

    except Exception as e:
        print(f"Error al descargar o extraer el modelo: {e}")

def cargar_modelo_vosk():
    """
    Carga el modelo Vosk desde el directorio.
    """
    try:
        model_path = os.path.join(MODEL_DIR, MODEL_SUBDIR)
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"El modelo no se encuentra en {model_path}. Asegúrate de que el modelo esté descargado y extraído correctamente.")
        
        print(f"Modelo Vosk cargado desde {model_path}.")
        model = Model(model_path)  # Aseguramos que la ruta del modelo sea correcta
        return model
    except Exception as e:
        print(f"Error al cargar el modelo: {e}")
        return None

def verificar_y_grabar_audio(archivo_salida="prueba_voz.wav", duracion=5, tasa_muestreo=16000):
    """
    Verifica si el archivo de audio ya existe, y si no, lo graba.
    """
    if not os.path.exists(archivo_salida):
        print(f"{archivo_salida} no encontrado. Procediendo a grabar audio...")
        grabar_audio(archivo_salida, duracion, tasa_muestreo)
    else:
        print(f"{archivo_salida} ya existe. Usando archivo existente.")

def grabar_audio(archivo_salida="prueba_voz.wav", duracion=5, tasa_muestreo=16000):
    """
    Graba audio desde el micrófono y lo guarda en un archivo .wav.
    """
    try:
        import pyaudio

        print("Iniciando grabación de audio...")
        p = pyaudio.PyAudio()

        # Configuración del micrófono
        flujo = p.open(format=pyaudio.paInt16,
                      channels=1,
                      rate=tasa_muestreo,
                      input=True,
                      frames_per_buffer=1024)

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

    except Exception as e:
        print(f"Error durante la grabación de audio: {e}")

def obtener_vector_identidad(audio_path, model_dir="model"):
    """
    Obtiene el vector de identidad de la voz desde un archivo de audio utilizando Vosk.
    :param audio_path: Ruta al archivo de audio (por ejemplo, "prueba_voz.wav").
    :param model_dir: Ruta al directorio que contiene el modelo Vosk.
    :return: Un vector que representa la identidad de la voz.
    """
    try:
        print(f"Iniciando el proceso de obtención del vector de identidad desde {audio_path}...")
        
        # Cargar el modelo de Vosk
        model = Model(model_dir)
        recognizer = KaldiRecognizer(model, 16000)

        # Abrir el archivo de audio
        with wave.open(audio_path, "rb") as wf:
            frames = wf.readframes(wf.getnframes())

        # Enviar los datos de audio al reconocedor de voz
        recognizer.AcceptWaveform(frames)
        
        # Obtener el resultado
        result = recognizer.Result()

        # Convertir el resultado a un objeto JSON
        result_json = json.loads(result)

        # Extraer las características del resultado (por ejemplo, transcripción)
        transcripcion = result_json.get("text", "")

        # Crear un vector de características simulado. Aquí podrías integrar un modelo para obtener embeddings reales.
        vector_identidad = np.random.rand(512)  # Un vector aleatorio de 512 dimensiones (como ejemplo)

        print(f"Vector de identidad obtenido: {vector_identidad}")

        return vector_identidad

    except Exception as e:
        print(f"Error al obtener el vector de identidad: {e}")
        return None

def puntuar_voz(voz_vector, vector_referencia=None):
    """
    Puntúa un archivo de prueba utilizando el modelo Vosk y el vector de identidad.
    Realiza la comparación de similitud entre el vector de la voz grabada y un vector de referencia.
    """
    try:
        # Verificar que los vectores de voz sean válidos
        if voz_vector is None or len(voz_vector) == 0:
            print("Error: El vector de voz está vacío o no se ha proporcionado correctamente.")
            return None

        # Si no se proporciona un vector de referencia, se puede generar uno para la comparación
        if vector_referencia is None:
            vector_referencia = np.random.rand(len(voz_vector))  # Generando un vector aleatorio para ejemplo

        # Comparar los dos vectores utilizando la distancia del coseno
        similarity = cosine_similarity([voz_vector], [vector_referencia])

        similitud = similarity[0][0]
        
        # Verbalización de la similitud
        print(f"Similitud calculada: {similitud:.4f}")

        if similitud > 0.8:
            print("¡Similitud alta! La voz es probablemente la misma.")
        elif similitud > 0.5:
            print("Similitud moderada. Puede que sea la misma persona, pero no es 100% seguro.")
        else:
            print("Similitud baja. La voz no parece coincidir.")

        # Convertir similitud a una puntuación en el rango de 0 a 100
        puntuacion = similitud * 100
        print(f"Puntuación final: {puntuacion:.2f} / 100")

        return puntuacion

    except Exception as e:
        print(f"Error durante el proceso de puntuación: {e}")
        return None


# Verificar si el modelo ya existe, si no, descargarlo
if not os.path.exists(os.path.join(MODEL_DIR, MODEL_SUBDIR)):
    descargar_modelo()

# Imprimir contenido del directorio del modelo
print(f"Contenido de {MODEL_DIR}: {os.listdir(MODEL_DIR)}")

# Intentar cargar el modelo
modelo_vosk = cargar_modelo_vosk()

# Verificar y grabar audio
verificar_y_grabar_audio("prueba_voz.wav")

# Obtener vector de identidad para la voz grabada
voz_nueva = obtener_vector_identidad("prueba_voz.wav", os.path.join(MODEL_DIR, MODEL_SUBDIR))

# Puntuar la voz grabada usando el modelo Vosk
if voz_nueva is not None and modelo_vosk is not None:
    puntuacion = puntuar_voz(voz_nueva)

print("Proceso de autenticación de voz finalizado.")
