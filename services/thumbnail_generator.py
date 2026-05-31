"""
本地缩略图生成器。

优先用于没有远程封面图的视频。Docker 镜像里已安装 ffmpeg，因此 macOS
本地 Docker 部署时可以直接从视频第一秒附近截一帧。
"""
import os
import shutil
import subprocess


class ThumbnailGenerator:
    """用 ffmpeg 生成轻量预览图。"""

    @staticmethod
    def generate_video_thumbnail(video_path: str, output_path: str = None):
        if not video_path or not os.path.exists(video_path):
            return None
        if not shutil.which('ffmpeg'):
            return None

        if not output_path:
            stem, _ = os.path.splitext(video_path)
            output_path = f'{stem}_thumb.jpg'

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        command = [
            'ffmpeg',
            '-y',
            '-ss',
            '00:00:01',
            '-i',
            video_path,
            '-frames:v',
            '1',
            '-q:v',
            '3',
            output_path,
        ]
        try:
            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=20,
                check=False,
            )
            if result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return output_path
        except Exception as e:
            print(f"生成视频缩略图失败: {e}")
        return None

    @staticmethod
    def generate_photo_thumbnail(photo_path: str, output_path: str = None):
        if not photo_path or not os.path.exists(photo_path):
            return None
        return photo_path
