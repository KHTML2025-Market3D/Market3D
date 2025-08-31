# tools/visualize_open3d.py
# 네가 준 코드 그대로 + URL 입력도 받도록 최소 수정(내려받아 임시파일로 사용)
import os, tempfile, urllib.request
import argparse
import numpy as np
import open3d as o3d
from scipy.spatial.transform import Rotation

def _resolve_local_or_download(path_or_url: str) -> str:
    """로컬 경로면 그대로, http(s)면 임시파일로 다운로드해서 경로 반환"""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        tmpdir = tempfile.mkdtemp(prefix="plytraj_")
        filename = os.path.basename(path_or_url.split("?")[0]) or "download.bin"
        local = os.path.join(tmpdir, filename)
        print(f"Downloading {path_or_url} -> {local}")
        urllib.request.urlretrieve(path_or_url, local)
        return local
    return path_or_url

def visualize(ply_file, traj_file):
    """
    Loads a point cloud and a camera trajectory file and visualizes them together.

    :param ply_file: Path or URL to the .ply point cloud file.
    :param traj_file: Path or URL to the .txt trajectory file (TUM format).
    """
    ply_file = _resolve_local_or_download(ply_file)
    traj_file = _resolve_local_or_download(traj_file)

    print(f"Loading point cloud from {ply_file}...")
    try:
        pcd = o3d.io.read_point_cloud(ply_file)
        if not pcd.has_points():
            print(f"Error: The point cloud file {ply_file} is empty or could not be read.")
            return
    except Exception as e:
        print(f"Error reading point cloud file: {e}")
        return

    print(f"Loading trajectory from {traj_file}...")
    try:
        traj_data = np.loadtxt(traj_file)
    except Exception as e:
        print(f"Error reading trajectory file: {e}")
        return

    geometries = [pcd]

    camera_positions = traj_data[:, 1:4]
    line_set = o3d.geometry.LineSet(
        points=o3d.utility.Vector3dVector(camera_positions),
        lines=o3d.utility.Vector2iVector([[i, i + 1] for i in range(len(camera_positions) - 1)])
    )
    line_set.paint_uniform_color([1.0, 0.0, 0.0])  # red
    geometries.append(line_set)

    num_poses = len(traj_data)
    frame_step = max(1, num_poses // 50)

    for i in range(0, num_poses, frame_step):
        translation = traj_data[i, 1:4]            # tx, ty, tz
        quat = traj_data[i, 4:8]                   # qx, qy, qz, qw

        T = np.eye(4)
        T[:3, :3] = Rotation.from_quat(quat).as_matrix()
        T[:3, 3] = translation

        mesh_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=0.05)
        mesh_frame.transform(T)
        geometries.append(mesh_frame)

    print("Visualizing... Press 'q' to close the window.")
    o3d.visualization.draw_geometries(
        geometries,
        window_name="MASt3R-SLAM Output Visualization",
        width=1920,
        height=1080,
    )

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize MASt3R-SLAM output files.")
    parser.add_argument('--ply_file', type=str, required=True,
                        help='Path or URL to the point cloud .ply file.')
    parser.add_argument('--traj_file', type=str, required=True,
                        help='Path or URL to the camera trajectory .txt file (TUM format).')
    args = parser.parse_args()

    try:
        import open3d  # noqa
        import scipy   # noqa
    except ImportError:
        print("This script requires 'open3d' and 'scipy'.")
        print("Install with:  pip install open3d scipy")
    else:
        visualize(args.ply_file, args.traj_file)
