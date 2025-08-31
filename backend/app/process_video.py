import os
import json
from google import genai
from dotenv import load_dotenv
import pydantic
from typing import List, Optional
import requests
import time
import numpy as np
import zipfile
import cv2  # OpenCV 라이브러리 import 추가


# .env 파일에서 환경 변수 로드
load_dotenv()

# 0. .env 파일로부터 API 키 설정
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("환경 변수 'GEMINI_API_KEY'를 찾을 수 없습니다. .env 파일을 확인해주세요.")

client = genai.Client(api_key=api_key)


# 2. structured_output을 위한 응답 스키마 정의 (Pydantic 모델 사용)
class ProductInfo(pydantic.BaseModel):
    """영상에서 감지된 상품에 대한 정보입니다."""
    name: str = pydantic.Field(description="상품의 이름")
    price: Optional[str] = pydantic.Field(description="나타난 상품의 가격. 가격이 보이지 않으면 null입니다.")
    time_min: int = pydantic.Field(description="해당 상품이 동영상에서 구체적으로 나타난 시간(분)")
    time_sec: int = pydantic.Field(description="해당 상품이 동영상에서 구체적으로 나타난 시간(초)")
    time_ms: int = pydantic.Field(description="해당 상품이 동영상에서 구체적으로 나타난 시간(밀리초)")


def _add_coordinates_from_txt(
    product_list: List[ProductInfo], 
    video_path: str
) -> List[ProductInfo]:
    """
    상품 정보 리스트에 해당하는 txt 파일에서 좌표 정보를 찾아 추가합니다.
    """
    txt_path = os.path.splitext(video_path)[0] + ".txt"
    
    if not os.path.exists(txt_path):
        print(f"경고: 좌표 파일 '{txt_path}'을(를) 찾을 수 없습니다. 좌표 없이 진행합니다.")
        return product_list

    try:
        with open(txt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # txt 파일 데이터를 파싱하여 [시간, x, y, z] 형태의 리스트로 저장
        coord_data = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 4:
                try:
                    # 시간, x, y, z 값만 float으로 변환하여 저장
                    coord_data.append([float(p) for p in parts[:4]])
                except (ValueError, IndexError):
                    # 숫자로 변환할 수 없는 줄은 건너뜁니다.
                    continue
        
        if not coord_data:
            print(f"경고: '{txt_path}' 파일에서 유효한 좌표 데이터를 읽지 못했습니다.")
            return product_list

    except Exception as e:
        print(f"좌표 파일을 읽는 중 오류 발생: {e}")
        return product_list

    # 각 상품 정보에 대해 가장 가까운 시간의 좌표를 찾습니다.
    a = []
    for product in product_list:
        # ProductInfo의 시간 정보를 전체 초(float)로 변환
        product_time_sec = product.time_min * 60 + product.time_sec + product.time_ms / 1000.0
        
        min_diff = float('inf')
        closest_coords = None

        # 모든 좌표 데이터와 시간 차이를 비교하여 가장 가까운 행을 찾습니다.
        for row in coord_data:
            time_diff = abs(row[0] - product_time_sec)
            if time_diff < min_diff:
                min_diff = time_diff
                closest_coords = row

        # 가장 가까운 좌표를 찾았으면 ProductInfo 객체에 값을 할당합니다.
        if closest_coords:
            a.append(closest_coords)
            
    return a

def analyze_products_in_video(video_path: str) -> Optional[list[ProductInfo]]:
    """
    동영상을 분석하여 프롬프트에 따른 상품 정보를 structured_output 형식으로 추출합니다.
    이미 분석 결과(json)가 존재하면 API를 호출하지 않고 캐시된 결과를 반환합니다.

    Args:
        video_path (str): 분석할 로컬 동영상 파일의 경로.

    Returns:
        Optional[list[ProductInfo]]: 추출된 상품 정보 리스트가 담긴 Pydantic 모델 객체.
                                         오류 발생 시 None을 반환합니다.
    """
    # 1. JSON 파일 경로 생성 및 캐시 확인
    try:
        # 동영상 파일명에서 확장자를 제외한 부분을 가져옵니다.
        base_name = os.path.basename(video_path)
        file_name_without_ext = os.path.splitext(base_name)[0]
        
        # 동영상이 있는 디렉토리에 .json 확장자로 된 파일 경로를 만듭니다.
        json_file_path = os.path.join(os.path.dirname(video_path), f"{file_name_without_ext}.json")

        if os.path.exists(json_file_path):
            print(f"'{json_file_path}'에서 캐시된 결과를 로드합니다.")
            with open(json_file_path, "r", encoding="utf-8") as f:
                json_data = json.load(f)
                # JSON 데이터를 Pydantic 모델 리스트로 변환하여 반환
                return [ProductInfo(**item) for item in json_data]

    except Exception as e:
        print(f"캐시된 JSON 파일을 읽는 중 오류가 발생했습니다: {e}")
        # 캐시 읽기 실패 시, API를 통해 새로 분석을 진행합니다.
        pass

    # --- 캐시가 없는 경우, 아래의 Gemini API 호출 로직 실행 ---
    try:
        print(f"'{video_path}' 파일을 업로드하는 중...")
        video_file = client.files.upload(file=video_path)

        while video_file.state.name == "PROCESSING":
            print("파일 처리 중...")
            video_file = client.files.get(name=video_file.name)

        if video_file.state.name != "ACTIVE":
            raise Exception(f"파일 처리 실패: {video_file.state.name}")
            
        print("파일 업로드 및 처리 완료.")

        prompt = (
            "이 영상에 나타난 상품의 이름과 나타난 가격, 영상에서 상품이 나타난 시간을 모두 말하라. 가격이 보이지 않으면 상품 이름만 말하라."
        )
        
        print("모델을 호출하여 영상 분석을 시작합니다...")
        
        response = client.models.generate_content(
            model="gemini-2.5-pro",  # 모델 이름을 최신 버전으로 명시하는 것이 좋습니다.
            contents=[video_file, prompt],
            config= {
                "response_mime_type": "application/json",
                "response_schema": list[ProductInfo],
            }
        )
        
        # Pydantic 모델 리스트를 가져옵니다.
        product_info_list = response.parsed

        if product_info_list:
            # --- 기능 추가 ---
            # API 응답 결과에 좌표 정보를 추가합니다.
            xyz_info_list = _add_coordinates_from_txt(product_info_list, video_path)

            # Pydantic 모델을 JSON으로 저장하기 위해 dict 리스트로 변환
            data_to_save = [info.model_dump() for info in product_info_list]

            for i in range(len(product_info_list)):
                data_to_save[i]['x'] = xyz_info_list[i][1]
                data_to_save[i]['y'] = xyz_info_list[i][2]
                data_to_save[i]['z'] = xyz_info_list[i][3]

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        
        # # 1. 반환된 결과를 JSON 파일로 저장
        # if product_info_list:
        #     # Pydantic 모델을 JSON으로 저장하기 위해 dict 리스트로 변환
        #     # 모델 인스턴스에서는 .model_dump()를 사용하고, 일반 dict에서는 그대로 사용
        #     if isinstance(product_info_list[0], dict):
        #          data_to_save = product_info_list
        #     else: # Pydantic 모델인 경우
        #          data_to_save = [info.model_dump() for info in product_info_list]


        #     with open(json_file_path, "w", encoding="utf-8") as f:
        #         json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        #     print(f"분석 결과를 '{json_file_path}'에 저장했습니다.")
        
        return product_info_list

    except FileNotFoundError:
        print(f"오류: '{video_path}' 파일을 찾을 수 없습니다. 파일 경로를 확인해주세요.")
        return None
    except Exception as e:
        print(f"오류가 발생했습니다: {e}")
        return None


def get_3d_model(video_path: str, server_url: str = "http://localhost:7141"):
    """
    서버에 동영상 파일을 업로드하고, 결과 파일을 폴링하여 다운로드합니다.
    """
    # --- 1. 파일 유효성 검사 ---
    if not os.path.exists(video_path):
        print(f"❌ 오류: 파일이 존재하지 않습니다. '{video_path}'")
        return
    
    # --- 2. /generate: 동영상 파일 업로드 ---
    generate_url = f"{server_url}/generate"
    print(f"🚀 동영상 파일 업로드 중: '{os.path.basename(video_path)}'...")

    try:
        with open(video_path, 'rb') as f:
            files = {'file': (os.path.basename(video_path), f, 'video/mp4')}
            response = requests.post(generate_url, files=files, timeout=30)
            
            # HTTP 오류 (4xx, 5xx) 발생 시 예외 발생
            response.raise_for_status()
        
        data = response.json()
        job_id = data.get('id')

        if not job_id:
            print(f"❌ 오류: 서버에서 유효한 Job ID를 받지 못했습니다. 응답: {data}")
            return
            
        print(f"✅ 업로드 완료! Job ID: {job_id}")

    except requests.exceptions.RequestException as e:
        print(f"❌ 서버 연결 오류: {e}")
        return

    # --- 3. /search: 10초 단위로 상태 폴링 및 결과 다운로드 ---
    search_url = f"{server_url}/search"
    print("\n🔄 10초마다 결과 생성 여부를 확인합니다...")

    while True:
        try:
            params = {'id': job_id}
            response = requests.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            # 응답이 파일(zip)인지 JSON(상태)인지 헤더로 확인
            if 'application/zip' in response.headers.get('Content-Type', ''):
                # --- 4-1. 파일 다운로드 및 압축 해제 ---
                print("\n🎉 변환 완료! 결과 파일을 다운로드합니다...")
                
                # 결과 저장 디렉토리 생성
                output_dir = os.path.dirname(video_path)

                zip_filename = os.path.join(output_dir, f"download.zip")
                with open(zip_filename, 'wb') as f:
                    f.write(response.content)
                
                print(f"✅ '{zip_filename}' 저장 완료.")

                # 압축 해제
                with zipfile.ZipFile(zip_filename, 'r') as zip_ref:
                    zip_ref.extractall(output_dir)
                print(f"✅ '{output_dir}' 디렉토리에 파일 압축 해제 완료.")
                
                # 원본 zip 파일 삭제 (선택 사항)
                os.remove(zip_filename)
                
                break # 루프 종료

            else:
                # --- 4-2. 상태 확인 ---
                status_data = response.json()
                status = status_data.get('status')

                if status == 0:
                    print("⏳ 처리 중... 10초 후 다시 확인합니다.")
                    time.sleep(10)
                elif status == -1:
                    print("❌ 서버에서 오류가 발생했거나 작업을 찾을 수 없습니다.")
                    break # 루프 종료
                else:
                    print(f"❓ 알 수 없는 상태 코드: {status}")
                    break

        except requests.exceptions.RequestException as e:
            print(f"❌ 서버 통신 오류: {e}")
            print("10초 후 재시도합니다.")
            time.sleep(10)

# 선명도 점수를 계산하는 헬퍼 함수
def calculate_focus_score(frame: np.ndarray) -> float:
    """
    라플라시안 변환의 분산을 사용하여 프레임의 선명도 점수를 계산합니다.
    점수가 높을수록 프레임이 더 선명합니다.
    """
    if frame is None:
        return 0.0
    # 이미지를 흑백으로 변환하여 계산을 단순화하고 색상 정보의 영향을 배제합니다.
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    # 라플라시안 변환 후 분산을 계산하여 반환합니다.
    return cv2.Laplacian(gray, cv2.CV_64F).var()

def save_product_frames(
    video_path: str,
    product_info_list: List[ProductInfo],
    search_range_ms: int = 50,
    step_ms: int = 5
):
    """
    동영상에서 특정 시간 주변의 프레임들을 탐색하여 가장 선명한 프레임을 저장합니다.

    Args:
        video_path (str): 원본 동영상 파일의 경로.
        product_info_list (List[Union[dict, 'ProductInfo']]): 상품 정보 리스트.
        search_range_ms (int): 선명한 프레임을 찾기 위해 탐색할 시간 범위(밀리초).
                               예: 250이면 지정 시간의 -250ms ~ +250ms 범위를 탐색합니다.
        step_ms (int): 탐색 시 건너뛸 시간 간격(밀리초). 작을수록 꼼꼼하지만 오래 걸립니다.
    """
    # 1. 동영상 파일 존재 여부 확인
    if not os.path.exists(video_path):
        print(f"❌ 오류: 동영상 파일을 찾을 수 없습니다. '{video_path}'")
        return

    # 2. 이미지 저장용 'img' 폴더 경로 설정 및 생성
    video_dir = os.path.dirname(video_path)
    output_img_dir = os.path.join(video_dir, "img") # 폴더 이름 변경
    os.makedirs(output_img_dir, exist_ok=True)
    print(f"✅ 선명한 프레임을 저장할 폴더를 준비했습니다: '{output_img_dir}'")

    # 3. 동영상 캡처 객체 생성
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"❌ 오류: 동영상을 열 수 없습니다. '{video_path}'")
        return

    # 4. 각 상품 정보에 대해 가장 선명한 프레임 추출
    print("🚀 가장 선명한 프레임 탐색 및 추출을 시작합니다...")
    for i, product_info in enumerate(product_info_list):
        # Pydantic 모델과 dict 형태 모두 지원
        if isinstance(product_info, dict):
            target_timestamp_sec = product_info.get('time_min', 0) * 60 + product_info.get('time_sec', 0) + product_info.get('time_ms', 0) / 1000
            product_name = product_info.get('name', 'unknown')
            product_price = product_info.get('price', 0)
        else:
            target_timestamp_sec = product_info.time_min * 60 + product_info.time_sec + product_info.time_ms / 1000
            product_name = product_info.name
            product_price = product_info.price

        target_timestamp_ms = int(target_timestamp_sec * 1000)

        best_frame = None
        max_focus_score = -1.0
        best_frame_time_ms = -1

        # 지정된 시간 주변을 탐색
        start_ms = max(0, target_timestamp_ms - search_range_ms)
        end_ms = target_timestamp_ms + search_range_ms
        
        print(f"\n  [항목 {i}] '{product_name}' 탐색 중... (목표 시간: {target_timestamp_sec:.2f}초)")
        
        for current_ms in range(start_ms, end_ms, step_ms):
            cap.set(cv2.CAP_PROP_POS_MSEC, current_ms)
            success, frame = cap.read()

            if success:
                score = calculate_focus_score(frame)
                # 더 선명한 프레임을 찾으면 교체
                if score > max_focus_score:
                    max_focus_score = score
                    best_frame = frame.copy() # 중요: 프레임 데이터를 복사해야 합니다.
                    best_frame_time_ms = current_ms

        if best_frame is not None:
            # 가장 선명했던 프레임을 이미지 파일로 저장
            image_name = f"{i}.png"
            image_path = os.path.join(output_img_dir, image_name)
            cv2.imwrite(image_path, best_frame)
            chosen_time_sec = best_frame_time_ms / 1000
            print(f"  - ✔️ '{image_path}' 저장 완료 (선택된 시간: {chosen_time_sec:.2f}초, 선명도: {max_focus_score:.2f})")
        else:
            print(f"  - ❌ {target_timestamp_sec:.2f}초 주변에서 프레임을 읽는 데 실패했습니다.")

    # 5. 자원 해제
    cap.release()
    print("\n🎉 모든 프레임 추출 작업을 완료했습니다.")



if __name__ == '__main__':
    # 분석할 동영상 파일 경로
    video_file_path = "backend/media/1/1.mp4" 

    get_3d_model(video_file_path)
    product_result = analyze_products_in_video(video_file_path)
    save_product_frames(video_file_path, product_result)
