import json
import os

def validate_workflow(workflow_path):
    """Validate dan info workflow"""
    try:
        with open(workflow_path, 'r') as f:
            workflow = json.load(f)
        
        prompt_nodes = []
        sampler_nodes = []
        
        for node_id, node_data in workflow.items():
            if node_data.get('class_type') == 'CLIPTextEncode':
                prompt_nodes.append(node_id)
            elif node_data.get('class_type') == 'KSampler':
                sampler_nodes.append(node_id)
        
        print(f"✅ Workflow valid: {workflow_path}")
        if not prompt_nodes:
             print("   ⚠️ Peringatan: Tidak ditemukan node 'CLIPTextEncode' (untuk prompt).")
        else:
            print(f"   - Prompt nodes ditemukan: {prompt_nodes}")

        if not sampler_nodes:
            print("   ⚠️ Peringatan: Tidak ditemukan node 'KSampler' (untuk seed).")
        else:
            print(f"   - Sampler nodes ditemukan: {sampler_nodes}")
            
        return True
        
    except Exception as e:
        print(f"❌ Error validating {workflow_path}: {e}")
        return False

def setup_workflows():
    """Setup dan validasi semua workflow"""
    workflows = ['landscape', 'portrait', 'square']
    print("Memvalidasi workflows...")
    print("-" * 50)
    
    all_valid = True
    for wf in workflows:
        path = f"workflows/{wf}.json"
        if os.path.exists(path):
            if not validate_workflow(path):
                all_valid = False
        else:
            print(f"❌ Workflow tidak ditemukan: {path}")
            all_valid = False
            
    print("-" * 50)
    if all_valid:
        print("Semua workflow yang ada tampak valid.")
    else:
        print("Beberapa workflow bermasalah atau tidak ditemukan. Harap periksa file JSON Anda.")


if __name__ == "__main__":
    setup_workflows()
  
