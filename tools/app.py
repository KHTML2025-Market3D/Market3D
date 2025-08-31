import os
import uuid
import subprocess
import zipfile
import io
from flask import Flask, request, jsonify, send_file
from multiprocessing import Process, Queue, Manager

# --- 설정 (기존과 동일) ---
UPLOAD_FOLDER = 'uploads'
LOGS_FOLDER = 'logs'
CONFIG_FILE = 'config/base.yaml'

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['LOGS_FOLDER'] = LOGS_FOLDER

# --- 백그라운드 워커 함수 (기존과 동일) ---
def process_queue(task_queue, job_status):
    """
    Queue에서 작업을 가져와 순차적으로 3D 맵 생성 및 최적화를 수행합니다.
    """
    while True:
        job_id, mp4_path = task_queue.get()
        
        try:
            job_status[job_id] = 'processing'
            print(f"[{job_id}] 처리 시작: {mp4_path}")
            
            # job_id가 이미 파일의 basename이므로 그대로 사용합니다.
            main_cmd = [
                'python', 'main.py',
                '--dataset', mp4_path,
                '--config', CONFIG_FILE,
                '--no-viz'
            ]
            print(f"[{job_id}] main.py 실행...")
            # main.py 실행 시 표준 출력/에러를 캡처하여 로그로 남길 수 있습니다.
            result = subprocess.run(main_cmd, check=True, capture_output=True, text=True)
            print(f"[{job_id}] main.py stdout: {result.stdout}")


            original_ply_path = os.path.join(LOGS_FOLDER, f"{job_id}.ply")
            optimized_ply_path = os.path.join(LOGS_FOLDER, f"{job_id}_optimized.ply")
            
            optimize_cmd = [
                'python', 'optimize_ply.py',
                original_ply_path,
                optimized_ply_path
            ]
            print(f"[{job_id}] optimize_ply.py 실행...")
            opt_result = subprocess.run(optimize_cmd, check=True, capture_output=True, text=True)
            print(f"[{job_id}] optimize_ply.py stdout: {opt_result.stdout}")

            job_status[job_id] = 'completed'
            print(f"[{job_id}] 처리 완료")

        except subprocess.CalledProcessError as e:
            job_status[job_id] = 'failed'
            print(f"[{job_id}] 처리 실패: {e.stderr}")
        except Exception as e:
            job_status[job_id] = 'failed'
            print(f"[{job_id}] 처리 중 예외 발생: {e}")


# --- API 엔드포인트 ---
@app.route('/generate', methods=['POST'])
def generate_map():
    if 'file' not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "파일이 선택되지 않았습니다."}), 400
    if file and file.filename.endswith('.mp4'):
        # --- 수정된 부분: 파일명을 기반으로 job_id 생성 및 중복 확인 ---
        basename = os.path.splitext(file.filename)[0]
        job_id = basename
        
        # 원본 ply 파일 존재 여부 확인
        ply_path = os.path.join(app.config['LOGS_FOLDER'], f"{job_id}_optimized.ply")

        if os.path.exists(ply_path):
            print(f"✔️ [{job_id}] 기존 파일이 존재하여 처리를 건너<binary data, 2 bytes, 1 bytes>니다.")
            job_status[job_id] = 'completed' # 상태를 'completed'로 설정
            return jsonify({"id": job_id, "message": "Result already exists."})
        
        # 파일이 없으면 기존 로직 수행
        mp4_filename = f"{job_id}.mp4" # 저장할 파일명도 job_id와 통일
        mp4_path = os.path.join(app.config['UPLOAD_FOLDER'], mp4_filename)
        file.save(mp4_path)
        
        task_queue.put((job_id, mp4_path))
        job_status[job_id] = 'queued'
        
        print(f"[{job_id}] 작업이 큐에 추가되었습니다: {mp4_path}")
        return jsonify({"id": job_id})
    else:
        return jsonify({"error": "mp4 파일만 업로드할 수 있습니다."}), 400

@app.route('/search', methods=['GET'])
def search_status():
    """
    작업 ID를 받아 상태를 확인하고, 완료된 작업의 결과 파일을 반환합니다.
    """
    job_id = request.args.get('id')
    if not job_id:
        return jsonify({"error": "id 파라미터가 필요합니다."}), 400

    # --- 수정된 부분: 특별 ID 로직 제거 및 통합 ---
    status = job_status.get(job_id)

    # 서버 재시작 등으로 메모리(job_status)에는 없지만 파일은 존재할 경우를 대비
    if status is None:
        optimized_ply_path_check = os.path.join(LOGS_FOLDER, f"{job_id}_optimized.ply")
        if os.path.exists(optimized_ply_path_check):
            status = 'completed'
            print(f"🔍 [{job_id}] 메모리에 상태는 없지만 완료된 파일이 있어 'completed'로 처리합니다.")


    if status == 'completed':
        txt_path = os.path.join(LOGS_FOLDER, f"{job_id}.txt")
        optimized_ply_path = os.path.join(LOGS_FOLDER, f"{job_id}_optimized.ply")

        if os.path.exists(txt_path) and os.path.exists(optimized_ply_path):
            memory_file = io.BytesIO()
            with zipfile.ZipFile(memory_file, 'w') as zf:
                zf.write(txt_path, os.path.basename(txt_path))
                zf.write(optimized_ply_path, os.path.basename(optimized_ply_path))
            memory_file.seek(0)
            
            print(f"✅ [{job_id}] 결과 파일 전송 완료.")
            return send_file(
                memory_file,
                download_name=f'{job_id}_result.zip',
                mimetype='application/zip',
                as_attachment=True
            )
        else:
            # 상태는 'completed'이지만 파일이 없는 예외적인 경우
            job_status[job_id] = 'failed'
            print(f"❌ [{job_id}] 상태는 'completed'지만 결과 파일을 찾을 수 없습니다.")
            return jsonify({"status": -1, "message": "결과 파일 생성에 실패했습니다."})

    elif status == 'processing' or status == 'queued':
        print(f"⏳ [{job_id}] 작업 진행 중... (상태: {status})")
        return jsonify({"status": 0})
    else: # ID가 없거나 'failed' 상태인 경우
        print(f"❌ [{job_id}] 작업을 찾을 수 없거나 실패했습니다. (상태: {status})")
        return jsonify({"status": -1})


# --- 서버 실행 (기존과 동일) ---
if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(LOGS_FOLDER, exist_ok=True)

    manager = Manager()
    job_status = manager.dict()
    task_queue = Queue()

    worker_process = Process(target=process_queue, args=(task_queue, job_status))
    worker_process.daemon = True
    worker_process.start()

    app.run(host='0.0.0.0', port=7141)
