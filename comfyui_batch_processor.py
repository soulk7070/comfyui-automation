import json
import requests
import websocket
import uuid
import time
import os
import re
import random
from datetime import datetime
import logging
from pathlib import Path

class ComfyUIBatchProcessor:
    def __init__(self, server_address="127.0.0.1:8188"):
        self.server_address = server_address
        self.client_id = str(uuid.uuid4())

        # Setup logging
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_dir / 'batch_process.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

        # Workflow paths
        self.workflows = {
            'landscape': 'workflows/landscape.json',
            'portrait': 'workflows/portrait.json',
            'square': 'workflows/square.json'
        }

        def parse_prompt_file(self, filepath):
        """Parse prompt file dan ekstrak prompt dengan rasio (Versi Perbaikan)"""
        prompts = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or '(' not in line:
                        continue
                    
                    try:
                        # Pisahkan teks prompt utama dari bagian rasio
                        prompt_text, ratio_part = line.rsplit(' (', 1)
                        prompt_text = prompt_text.strip()
                        
                        # Regex untuk menemukan semua pasangan (nama):jumlah
                        ratio_pattern = r'([^)]+)\):(\d+)'
                        matches = re.findall(ratio_pattern, ratio_part)
                        
                        if not matches:
                            self.logger.warning(f"Format rasio tidak valid di baris {line_num}: {line}")
                            continue

                        ratios = []
                        for name, count in matches:
                            ratios.append({'type': name.strip(), 'count': int(count)})
                        
                        if ratios:
                            prompts.append({
                                'text': prompt_text,
                                'ratios': ratios,
                                'line_num': line_num
                            })

                    except ValueError:
                        self.logger.warning(f"Format tidak valid di baris {line_num} (kesalahan pemisahan): {line}")
        except FileNotFoundError:
            self.logger.error(f"File prompt tidak ditemukan: {filepath}")
        return prompts

    def load_workflow(self, workflow_type):
        """Load workflow JSON file"""
        workflow_path = self.workflows.get(workflow_type)
        if not workflow_path or not os.path.exists(workflow_path):
            self.logger.error(f"Workflow '{workflow_type}' tidak ditemukan di path: {workflow_path}")
            raise FileNotFoundError(f"Workflow {workflow_type} tidak ditemukan")
        with open(workflow_path, 'r') as f:
            return json.load(f)

    def update_workflow_prompt(self, workflow, prompt_text):
        """Update prompt text dalam workflow"""
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'CLIPTextEncode':
                if 'inputs' in node_data and 'text' in node_data['inputs']:
                    node_data['inputs']['text'] = prompt_text

            if node_data.get('class_type') == 'KSampler':
                if 'inputs' in node_data:
                    node_data['inputs']['seed'] = random.randint(1, 1000000000)
        return workflow

    def queue_prompt(self, workflow):
        """Queue prompt ke ComfyUI"""
        p = {"prompt": workflow, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        try:
            resp = requests.post(f"http://{self.server_address}/prompt", data=data)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Error queuing prompt: {e}")
            return None

    def get_history(self, prompt_id):
        """Get generation history"""
        try:
            resp = requests.get(f"http://{self.server_address}/history/{prompt_id}")
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            self.logger.error(f"Error getting history: {e}")
            return None

    def wait_for_completion(self, prompt_id, timeout=300):
        """Wait for prompt completion"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            history = self.get_history(prompt_id)
            if history and prompt_id in history:
                return True
            time.sleep(2)
        return False

    def process_prompts(self, prompt_file):
        """Process all prompts from file"""
        prompts = self.parse_prompt_file(prompt_file)
        if not prompts:
            self.logger.info("Tidak ada prompt valid untuk diproses.")
            return

        total_generations = sum(sum(r['count'] for r in p['ratios']) for p in prompts)
        self.logger.info(f"Memulai proses {len(prompts)} prompt dengan total {total_generations} gambar.")

        completed = 0
        failed = 0
        for prompt_idx, prompt_data in enumerate(prompts):
            prompt_text = prompt_data['text']
            self.logger.info(f"\nMemproses prompt {prompt_idx + 1}/{len(prompts)}: {prompt_text[:50]}...")
            
            for ratio_data in prompt_data['ratios']:
                ratio_type = ratio_data['type']
                count = ratio_data['count']
                for i in range(count):
                    try:
                        workflow = self.load_workflow(ratio_type)
                        workflow = self.update_workflow_prompt(workflow, prompt_text)
                        
                        result = self.queue_prompt(workflow)
                        if result and 'prompt_id' in result:
                            prompt_id = result['prompt_id']
                            self.logger.info(f" - Generating {ratio_type} {i+1}/{count} (ID: {prompt_id})")
                            
                            if self.wait_for_completion(prompt_id):
                                completed += 1
                                self.logger.info(f"   Selesai: {ratio_type} {i+1}/{count}")
                            else:
                                failed += 1
                                self.logger.error(f"   X Timeout: {ratio_type} {i+1}/{count}")
                        else:
                            failed += 1
                            self.logger.error(f"   X Gagal queue: {ratio_type} {i+1}/{count}")
                        
                        time.sleep(2) # Delay antar generation
                    
                    except Exception as e:
                        failed += 1
                        self.logger.error(f"   X Error: {e}")

        self.logger.info(f"\n{'='*50}")
        self.logger.info(f"SELESAI! Total: {total_generations}, Berhasil: {completed}, Gagal: {failed}")

    def test_connection(self):
        """Test koneksi ke ComfyUI"""
        try:
            resp = requests.get(f"http://{self.server_address}/system_stats")
            if resp.status_code == 200:
                self.logger.info("✅ Koneksi ke ComfyUI berhasil")
                return True
        except requests.exceptions.ConnectionError:
            pass
        
        self.logger.error("❌ Tidak dapat terhubung ke ComfyUI di http://{self.server_address}")
        return False

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python comfyui_batch_processor.py <prompt_file.txt>")
        sys.exit(1)
        
    prompt_file = sys.argv[1]
    if not os.path.exists(prompt_file):
        print(f"File tidak ditemukan: {prompt_file}")
        sys.exit(1)
        
    processor = ComfyUIBatchProcessor()
    
    if not processor.test_connection():
        print("Pastikan ComfyUI sedang berjalan dan dapat diakses!")
        sys.exit(1)
        
    processor.process_prompts(prompt_file)

