import pyaudio
import wave
import os
import time

# Configuración de grabación
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000  # Frecuencia de muestreo estándar para reconocimiento de voz
CHUNK = 1024
DURATION = 5  # Duración de cada grabación en segundos
NUM_MUESTRAS = 10  # Número total de grabaciones
OUTPUT_DIR = "dataset"  # Carpeta donde se guardarán los archivos

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

    print("🎙️ Iniciando grabación...")

    # Crear el buffer para almacenar el audio
    frames = []

    # Grabar durante el tiempo especificado
    for _ in range(0, int(tasa_muestreo / 1024 * duracion)):
        data = flujo.read(1024)
        frames.append(data)

    print("🛑 Grabación finalizada.")

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

    print(f"✅ Audio guardado como {archivo_salida}.")

# Función para verificar y grabar el archivo de prueba
def verificar_y_grabar_audio(archivo_salida="prueba_voz.wav"):
    if not os.path.exists(archivo_salida):
        print(f"{archivo_salida} no encontrado. Procediendo a grabar audio...")
        grabar_audio(archivo_salida)  # Llama a la función de grabación si el archivo no existe
    else:
        print(f"{archivo_salida} ya existe. Usando archivo existente.")

# Función para grabar varias muestras de voz
def grabar_muestras():
    print(f"\n📢 Iniciando proceso de grabación de {NUM_MUESTRAS} muestras de voz.")
    print(f"📂 Las muestras se guardarán en la carpeta: {OUTPUT_DIR}/")

    # Crear la carpeta si no existe
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    audio = pyaudio.PyAudio()
    
    try:
        for i in range(1, NUM_MUESTRAS + 1):
            file_name = os.path.join(OUTPUT_DIR, f"mi_voz_{i}.wav")

            print(f"\n🎙️ Preparado para grabar muestra {i}/{NUM_MUESTRAS}.")
            print(f"⏳ Duración de la grabación: {DURATION} segundos.")
            print("🎧 Por favor, habla claramente y en un tono normal.")
            time.sleep(2)  # Pausa antes de empezar

            stream = audio.open(format=FORMAT, channels=CHANNELS,
                                rate=RATE, input=True,
                                frames_per_buffer=CHUNK)

            print("🔴 GRABANDO... No hables demasiado bajo ni demasiado alto.")
            frames = []

            for _ in range(0, int(RATE / CHUNK * DURATION)):
                data = stream.read(CHUNK)
                frames.append(data)

            print("🛑 Grabación finalizada.")

            stream.stop_stream()
            stream.close()

            with wave.open(file_name, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(audio.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))

            print(f"✅ Muestra {i} guardada en {file_name}")
            print("⏳ Pausa de 3 segundos antes de la siguiente grabación...")
            time.sleep(3)  # Espera antes de la siguiente grabación

        print("\n🎉 Todas las grabaciones se han completado con éxito.")
    except Exception as e:
        print(f"⚠️ Error durante la grabación: {e}")
    finally:
        audio.terminate()
        print("🎤 Grabación finalizada. Cerrando el sistema de audio.")

# Comenzar el proceso de grabación
grabar_muestras()
