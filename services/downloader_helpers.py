import os
import tempfile
from typing import List, Optional, Tuple
from urllib.parse import urlparse


def safe_int(value, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def unique_urls(urls: List[str]) -> List[str]:
    seen = set()
    normalized = []
    for url in urls or []:
        if not url:
            continue
        text = str(url).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def pick_thumbnail_url(payload: dict) -> Optional[str]:
    if not isinstance(payload, dict):
        return None

    thumbnails = payload.get('thumbnails')
    if isinstance(thumbnails, list):
        candidates = [item.get('url') for item in thumbnails if isinstance(item, dict) and item.get('url')]
        if candidates:
            return candidates[-1]

    for key in ('thumbnail', 'thumbnail_url', 'preview_image_url'):
        value = payload.get(key)
        if value:
            return value

    return None


def extract_direct_video_urls(payload: dict) -> Tuple[Optional[str], List[str]]:
    """从 yt-dlp 元数据里挑选最适合直连下载的候选 URL。"""
    if not isinstance(payload, dict):
        return None, []

    formats = payload.get('formats')
    candidates = []

    if isinstance(formats, list):
        for fmt in formats:
            if not isinstance(fmt, dict):
                continue

            url = fmt.get('url')
            if not url:
                continue

            protocol = str(fmt.get('protocol') or '')
            ext = str(fmt.get('ext') or '')
            height = safe_int(fmt.get('height'), 0) or 0
            tbr = safe_int(fmt.get('tbr') or fmt.get('vbr'), 0) or 0
            has_audio = 1 if str(fmt.get('acodec') or '').lower() not in {'', 'none'} else 0
            progressive = all(marker not in protocol for marker in ('m3u8', 'dash', 'ism'))

            candidates.append({
                'url': url,
                'score': (
                    1 if progressive and ext == 'mp4' else 0,
                    1 if progressive else 0,
                    1 if ext == 'mp4' else 0,
                    has_audio,
                    height,
                    tbr,
                ),
            })

    direct_url = payload.get('url')
    if direct_url:
        candidates.append({
            'url': direct_url,
            'score': (0, 0, 0, 0, 0, 0),
        })

    sorted_urls = unique_urls([
        item['url']
        for item in sorted(candidates, key=lambda item: item['score'], reverse=True)
    ])
    if not sorted_urls:
        return None, []

    return sorted_urls[0], sorted_urls[1:]


def extract_ytdlp_error_message(raw_output: str) -> str:
    """提取 yt-dlp 输出里的关键错误行。"""
    error_msg = (raw_output or '').strip()
    if not error_msg:
        return ''

    error_lines = [line.strip() for line in error_msg.split('\n') if 'ERROR' in line or 'error' in line]
    if error_lines:
        return error_lines[0]
    return error_msg.splitlines()[0].strip()


def is_retryable_ytdlp_error(error_msg: str) -> bool:
    """判断是否属于值得自动重试的临时网络错误。"""
    normalized = (error_msg or '').lower()
    if not normalized:
        return False

    retryable_markers = [
        'unexpected_eof',
        'ssl',
        'timed out',
        'timeout',
        'connection reset',
        'remote end closed connection',
        'temporary failure',
        'network is unreachable',
        'connection aborted',
        'eof occurred in violation of protocol',
    ]
    return any(marker in normalized for marker in retryable_markers)


def cleanup_ytdlp_temp_files(save_path: str):
    """清理失败尝试留下的 yt-dlp 临时文件，避免脏状态影响重试。"""
    temp_candidates = [
        save_path,
        save_path + '.part',
        save_path + '.ytdl',
    ]

    for path in temp_candidates:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass


def convert_cookies_to_netscape(json_cookies_file: str, cookies: list) -> Optional[str]:
    """将浏览器 JSON cookies 写成 yt-dlp 需要的 Netscape cookies 文件。"""
    try:
        with tempfile.NamedTemporaryFile(
            mode='w',
            encoding='utf-8',
            delete=False,
            prefix='twitter_cookies_',
            suffix='.txt'
        ) as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies:
                domain = cookie.get('domain', '.twitter.com')
                flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expiration = str(int(cookie.get('expirationDate', 0)))
                name = cookie.get('name', '')
                value = cookie.get('value', '')

                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiration}\t{name}\t{value}\n")

            return f.name
    except Exception as e:
        print(f"     ⚠️ cookies转换失败 ({json_cookies_file}): {e}")
        return None


def get_file_extension(url: str) -> Optional[str]:
    """
    从 URL 获取文件扩展名。
    :param url: 文件 URL
    :return: 扩展名（不带点）
    """
    parsed = urlparse(url or '')
    path = parsed.path

    if '?' in path:
        path = path.split('?')[0]

    ext = os.path.splitext(path)[1]
    if ext:
        return ext.lstrip('.')

    return None
