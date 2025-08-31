
import open3d as o3d
import numpy as np
import os

def optimize_ply(input_path, output_path, voxel_size=0.01, nb_neighbors=20, std_ratio=2.0):
    """
    PLY 파일(포인트 클라우드)을 최적화하고 압축합니다.

    과정:
    1. 통계적 이상점 제거 (Statistical Outlier Removal)
    2. 복셀 그리드 다운샘플링 (Voxel Grid Downsampling)
    3. 바이너리 형식으로 저장하여 압축

    :param input_path: 입력 PLY 파일 경로
    :param output_path: 저장할 최적화된 PLY 파일 경로
    :param voxel_size: 다운샘플링 시 사용할 복셀(3D 픽셀)의 크기. 클수록 더 많이 압축됩니다.
    :param nb_neighbors: 이상점 계산 시 고려할 이웃 포인트의 수.
    :param std_ratio: 이상점으로 판단할 표준 편차의 배수. 클수록 이상점을 덜 제거합니다.
    """
    print(f"'{input_path}' 파일 로딩 중...")
    try:
        pcd = o3d.io.read_point_cloud(input_path)
        if not pcd.has_points():
            print("오류: 포인트 클라우드를 로드할 수 없거나 포인트가 없습니다.")
            return
    except Exception as e:
        print(f"파일 로딩 중 오류 발생: {e}")
        return

    original_point_count = len(pcd.points)
    print(f"최적화 전 포인트 수: {original_point_count}")

    # 1. 통계적 이상점 제거
    print("1단계: 통계적 이상점 제거 진행 중...")
    cl, ind = pcd.remove_statistical_outlier(nb_neighbors=nb_neighbors, std_ratio=std_ratio)
    pcd = pcd.select_by_index(ind)
    points_after_outlier_removal = len(pcd.points)
    print(f"이상점 제거 후 포인트 수: {points_after_outlier_removal} ({original_point_count - points_after_outlier_removal}개 제거)")

    # 2. 복셀 그리드 다운샘플링
    print(f"2단계: 복셀 크기 {voxel_size}로 다운샘플링 진행 중...")
    pcd = pcd.voxel_down_sample(voxel_size=voxel_size)
    points_after_downsampling = len(pcd.points)
    print(f"다운샘플링 후 포인트 수: {points_after_downsampling} ({points_after_outlier_removal - points_after_downsampling}개 제거)")

    # 3. 바이너리 형식으로 저장
    print("3단계: 바이너리 PLY 형식으로 파일 저장 중...")
    try:
        o3d.io.write_point_cloud(output_path, pcd, write_ascii=False)
        final_size = os.path.getsize(output_path)
        print(f"성공! 최적화된 파일이 '{output_path}'에 저장되었습니다.")
        print(f"최종 포인트 수: {points_after_downsampling}")
        print(f"최종 파일 크기: {final_size / 1024 / 1024:.2f} MB")

        original_size = os.path.getsize(input_path)
        print(f"원본 파일 크기: {original_size / 1024 / 1024:.2f} MB")
        print(f"압축률: {original_size / final_size:.2f}배")

    except Exception as e:
        print(f"파일 저장 중 오류 발생: {e}")


import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Optimize a PLY point cloud file.')
    parser.add_argument('input_file', type=str, help='Input PLY file path.')
    parser.add_argument('output_file', type=str, help='Output PLY file path.')
    parser.add_argument('--voxel_size', type=float, default=0.02, help='Voxel size for downsampling.')
    parser.add_argument('--std_ratio', type=float, default=5.0, help='Standard deviation ratio for outlier removal.')

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.")
    else:
        optimize_ply(args.input_file, args.output_file, voxel_size=args.voxel_size, std_ratio=args.std_ratio)
