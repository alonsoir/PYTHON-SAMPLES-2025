import os
import requests
import tarfile
import gzip
import shutil
import numpy as np
import soundfile as sf
import simpleaudio as sa
import matplotlib.pyplot as plt
from tqdm import tqdm
from pocketsphinx import AudioFile, Decoder
from difflib import SequenceMatcher
from colorama import Fore, Style

def test_pocketsphinx(model_dir):
    """Prueba la inicialización del modelo."""
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Inicializando el modelo de reconocimiento de voz...")
    
    # Ajustar las rutas para que coincidan con la ubicación real de los archivos
    hmm_path = os.path.join(model_dir, 'model_parameters', 'voxforge_es_sphinx.cd_ptm_4000')
    dict_path = os.path.join(os.path.dirname(model_dir), 'es.dict')  # Subir un nivel
    lm_path = os.path.join(os.path.dirname(model_dir), 'es-20k.lm')  # Subir un nivel
    
    config = Decoder.default_config()
    config.set_string('-hmm', hmm_path)
    config.set_string('-dict', dict_path)
    config.set_string('-lm', lm_path)
    
    try:
        decoder = Decoder(config)
        print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Modelo cargado correctamente.")
        return True
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Error al cargar el modelo: {e}")
        return False

def download_file(url, output_path):
    """Descarga un archivo con barra de progreso."""
    if os.path.exists(output_path):
        print(f"{Fore.YELLOW}[INFO]{Style.RESET_ALL} {output_path} ya existe. Omitiendo descarga.")
        return
    
    print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} Descargando {url}...")
    response = requests.get(url, stream=True)
    total_size = int(response.headers.get('content-length', 0))
    block_size = 1024  # 1 KB
    t = tqdm(total=total_size, unit='B', unit_scale=True, desc=f"Descargando {os.path.basename(output_path)}")
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(block_size):
            t.update(len(chunk))
            f.write(chunk)
    t.close()
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Descarga completada: {output_path}")

def extract_tar_gz(file_path, output_dir):
    """Extrae un archivo tar.gz."""
    print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} Extrayendo {file_path}...")
    with tarfile.open(file_path, 'r:gz') as tar:
        tar.extractall(output_dir)
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Extracción completada: {output_dir}")

def extract_gz(file_path, output_path):
    """Extrae un archivo gz."""
    print(f"{Fore.BLUE}[INFO]{Style.RESET_ALL} Descomprimiendo {file_path}...")
    with gzip.open(file_path, 'rb') as f_in:
        with open(output_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Archivo descomprimido: {output_path}")

def setup_models():
    """Descarga y extrae los modelos de español si no están presentes."""
    # Directorio base para los modelos
    base_model_dir = os.path.join(os.getcwd(), 'model', 'es')
    os.makedirs(base_model_dir, exist_ok=True)
    
    cmusphinx_dir = os.path.join(base_model_dir, 'cmusphinx-es-5.2')
    os.makedirs(cmusphinx_dir, exist_ok=True)
    
    # Verificar si los archivos necesarios existen
    hmm_path = os.path.join(cmusphinx_dir, 'model_parameters', 'voxforge_es_sphinx.cd_ptm_4000')
    dict_path = os.path.join(base_model_dir, 'es.dict')
    lm_path = os.path.join(base_model_dir, 'es-20k.lm')
    
    # URLs de los archivos necesarios
    base_url = "https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/Spanish/"
    
    # Descargar y extraer acoustic model si no existe
    if not os.path.exists(hmm_path):
        acoustic_model_url = f"{base_url}cmusphinx-es-5.2-model.tar.gz"
        acoustic_model_tar = os.path.join(base_model_dir, 'cmusphinx-es-5.2-model.tar.gz')
        download_file(acoustic_model_url, acoustic_model_tar)
        extract_tar_gz(acoustic_model_tar, base_model_dir)
    
    # Descargar diccionario si no existe
    if not os.path.exists(dict_path):
        dict_url = f"{base_url}es.dict.gz"
        dict_gz = os.path.join(base_model_dir, 'es.dict.gz')
        download_file(dict_url, dict_gz)
        extract_gz(dict_gz, dict_path)
    
    # Descargar modelo de lenguaje si no existe
    if not os.path.exists(lm_path):
        lm_url = f"{base_url}es-20k.lm.gz"
        lm_gz = os.path.join(base_model_dir, 'es-20k.lm.gz')
        download_file(lm_url, lm_gz)
        extract_gz(lm_gz, lm_path)
    
    # Crear directorio para dataset si no existe
    data_directory = os.path.join(os.getcwd(), 'dataset')
    os.makedirs(data_directory, exist_ok=True)
    
    # Verificar si el modelo se inicializó correctamente
    if not test_pocketsphinx(cmusphinx_dir):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} El modelo no se ha inicializado correctamente. Saliendo...")
        exit(1)

def play_audio(audio_path):
    """Reproduce un archivo de audio."""
    try:
        data, samplerate = sf.read(audio_path)
        play_obj = sa.play_buffer((data * 32767).astype(np.int16), 1, 2, samplerate)
        play_obj.wait_done()
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Error al reproducir el audio {audio_path}: {e}")

def transcribe_audio(audio_path, model_dir):
    """Obtiene la transcripción de un archivo de audio usando PocketSphinx."""
    try:
        # Ajustar las rutas para que coincidan con la ubicación real de los archivos
        hmm_path = os.path.join(model_dir, 'model_parameters', 'voxforge_es_sphinx.cd_ptm_4000')
        dict_path = os.path.join(os.path.dirname(model_dir), 'es.dict')  # Subir un nivel
        lm_path = os.path.join(os.path.dirname(model_dir), 'es-20k.lm')  # Subir un nivel
        
        config = {
            'verbose': False,
            'audio_file': audio_path,
            'hmm': hmm_path,
            'lm': lm_path,
            'dict': dict_path
        }
        
        audio = AudioFile(**config)
        transcription = " ".join(str(phrase) for phrase in audio)
        return transcription
    except Exception as e:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Error al transcribir {audio_path}: {e}")
        return ""

def compare_transcriptions(transcription1, transcription2):
    """Compara dos transcripciones."""
    if not transcription1 or not transcription2:
        return 0
    return SequenceMatcher(None, transcription1, transcription2).ratio()

def plot_similarity(similarity_scores, filenames):
    """Grafica las similitudes."""
    plt.figure(figsize=(10, 6))
    plt.bar(filenames, similarity_scores, color='skyblue')
    plt.xlabel('Archivos de Voz')
    plt.ylabel('Similitud (%)')
    plt.title('Similitud de Transcripciones')
    plt.xticks(rotation=90)
    plt.tight_layout()
    plt.savefig('similitud_transcripciones.png')
    print(f"{Fore.GREEN}[SUCCESS]{Style.RESET_ALL} Gráfico guardado como 'similitud_transcripciones.png'")
    plt.show()

def main():
    # Configurar los modelos primero
    setup_models()
    
    # Definir rutas de directorios
    model_dir = os.path.join(os.getcwd(), 'model', 'es', 'cmusphinx-es-5.2')
    data_directory = os.path.join(os.getcwd(), 'dataset')
    
    # Verificar si el directorio de datos existe y tiene archivos
    if not os.path.exists(data_directory):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Directorio de datos no encontrado: {data_directory}")
        exit(1)
    
    wav_files = [f for f in os.listdir(data_directory) if f.endswith(".wav")]
    if not wav_files:
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} No se encontraron archivos WAV en: {data_directory}")
        exit(1)
    
    # Procesar el archivo de prueba
    prueba_voz_path = os.path.join(os.getcwd(), 'prueba_voz.wav')
    if not os.path.exists(prueba_voz_path):
        print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Archivo de prueba no encontrado: {prueba_voz_path}")
        exit(1)
    
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Procesando archivo de prueba {prueba_voz_path}")
    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Reproduciendo audio de prueba...")
    play_audio(prueba_voz_path)
    
    prueba_voz_transcription = transcribe_audio(prueba_voz_path, model_dir)
    print(f"{Fore.MAGENTA}[TRANSCRIPCIÓN]{Style.RESET_ALL} Archivo de prueba: {prueba_voz_transcription}")
    
    # Procesar archivos de dataset
    similarity_scores = []
    filenames = []
    
    for filename in wav_files:
        file_path = os.path.join(data_directory, filename)
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Procesando {file_path}")
        
        print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Reproduciendo audio...")
        play_audio(file_path)
        
        file_transcription = transcribe_audio(file_path, model_dir)
        print(f"{Fore.MAGENTA}[TRANSCRIPCIÓN]{Style.RESET_ALL} {filename}: {file_transcription}")
        
        similarity = compare_transcriptions(prueba_voz_transcription, file_transcription)
        similarity_scores.append(similarity * 100)
        filenames.append(filename)
        print(f"{Fore.YELLOW}[SIMILITUD]{Style.RESET_ALL} {filename}: {similarity * 100:.2f}%")
    
    # Mostrar gráfico de similitudes
    plot_similarity(similarity_scores, filenames)

if __name__ == "__main__":
    main()