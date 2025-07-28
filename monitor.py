import os
import time
import subprocess
from pathlib import Path
import logging
import shutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Direktori yang akan digunakan
WATCH_DIR = "prompts/queue"
PROCESSING_DIR = "prompts/processing"
COMPLETED_DIR = "prompts/completed"
FAILED_DIR = "prompts/failed"

def setup_directories():
    """Membuat semua direktori yang dibutuhkan."""
    for dir_path in [WATCH_DIR, PROCESSING_DIR, COMPLETED_DIR, FAILED_DIR]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

def process_file(filepath):
    """Memproses satu file prompt."""
    filename = os.path.basename(filepath)
    processing_path = os.path.join(PROCESSING_DIR, filename)
    completed_path = os.path.join(COMPLETED_DIR, filename)
    failed_path = os.path.join(FAILED_DIR, filename)

    try:
        # Salin file dari queue ke folder processing
        shutil.copy(filepath, processing_path)
        logger.info(f"Menyalin '{filename}' untuk diproses.")

        # Hapus file asli dari queue agar Git bisa mendeteksi penghapusan
        os.remove(filepath)
        logger.info(f"Menghapus '{filename}' dari antrian.")
        
        # Jalankan script utama untuk memproses file yang disalin
        cmd = ["python3", "comfyui_batch_processor.py", processing_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        logger.info(f"✅ Berhasil memproses: {filename}")
        logger.info(f"Output:\n{result.stdout}")
        # Pindahkan file dari processing ke completed
        os.rename(processing_path, completed_path)

    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Gagal memproses: {filename}")
        logger.error(f"Return Code: {e.returncode}")
        logger.error(f"Stderr:\n{e.stderr}")
        # Pindahkan file dari processing ke failed
        os.rename(processing_path, failed_path)
        
    except Exception as e:
        logger.error(f"❌ Terjadi error tak terduga saat memproses {filename}: {e}")
        # Jika file masih di processing, pindahkan ke failed
        if os.path.exists(processing_path):
            os.rename(processing_path, failed_path)

def monitor_directory():
    """Memantau direktori untuk file baru."""
    setup_directories()
    logger.info(f"Memonitor direktori '{WATCH_DIR}' untuk file prompt baru (.txt)...")
    while True:
        try:
            files = [f for f in os.listdir(WATCH_DIR) if f.endswith('.txt')]
            for file in files:
                filepath = os.path.join(WATCH_DIR, file)
                logger.info(f"Ditemukan file baru: {file}")
                process_file(filepath)
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            logger.info("Monitoring dihentikan oleh pengguna.")
            break
        except Exception as e:
            logger.error(f"Error dalam loop monitor: {e}")
            time.sleep(10)

if __name__ == "__main__":
    monitor_directory()
      
