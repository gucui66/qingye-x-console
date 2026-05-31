"""
配置文件
"""
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.abspath(__file__)
ENV_FILE = os.path.join(BASE_DIR, ".env")
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "static", "screenshots")
MEDIA_SHARDS_DIR = os.path.join(DATA_DIR, "media_shards")
MEDIA_SHARD_ARCHIVE_DIR = os.path.join(DATA_DIR, "media_shards_archive")
MEDIA_STAGING_DIR = os.path.join(DATA_DIR, ".media_staging")
MEDIA_SHARD_BUCKETS = int(os.getenv("MEDIA_SHARD_BUCKETS", "8") or "8")
ADMIN_FILE = os.path.join(DATA_DIR, "admin.txt")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")


def _load_env_file():
    """轻量加载 .env 文件，避免直接运行 python3 app.py 时环境变量失效。"""
    if not os.path.exists(ENV_FILE):
        return

    try:
        with open(ENV_FILE, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")

                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception as e:
        print(f"⚠️ 加载 .env 失败: {e}")


_load_env_file()

VIDEOS_DIR = os.path.join(OUTPUT_DIR, "videos")
PHOTOS_DIR = os.path.join(OUTPUT_DIR, "photos")
REPLIES_DIR = os.path.join(OUTPUT_DIR, "replies")
DOCS_DIR = os.path.join(OUTPUT_DIR, "documents")

# 确保基础目录存在
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(MEDIA_SHARDS_DIR, exist_ok=True)
os.makedirs(MEDIA_SHARD_ARCHIVE_DIR, exist_ok=True)
os.makedirs(MEDIA_STAGING_DIR, exist_ok=True)

def get_user_dirs(username):
    """
    为每个用户创建独立的文件夹
    例如：output/AC/videos/, output/AC/photos/, output/AC/documents/
    """
    user_output_dir = os.path.join(OUTPUT_DIR, username)
    user_videos_dir = os.path.join(user_output_dir, "videos")
    user_photos_dir = os.path.join(user_output_dir, "photos")
    user_replies_dir = os.path.join(user_output_dir, "replies")
    user_docs_dir = os.path.join(user_output_dir, "documents")
    
    # 创建用户专属目录
    for directory in [user_output_dir, user_videos_dir, user_photos_dir, user_replies_dir, user_docs_dir]:
        os.makedirs(directory, exist_ok=True)
    
    return {
        'output': user_output_dir,
        'videos': user_videos_dir,
        'photos': user_photos_dir,
        'replies': user_replies_dir,
        'documents': user_docs_dir
    }

# API配置（如果使用Twitter API）
# 从环境变量中读取，或者直接在这里配置
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_SECRET = os.getenv("TWITTER_ACCESS_SECRET", "")
# ⚠️ 安全警告：不要在这里硬编码Token！请使用环境变量或后台管理界面配置
TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN", "")

# Cookie 文件（Selenium 登录优先使用）
COOKIE_FILE = os.getenv("COOKIE_FILE", os.path.join(BASE_DIR, "twitter_cookies.json"))

# Twitter账号登录（用于Selenium模式，必需）
# 登录后才能看到敏感内容（包括媒体）
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")  # Twitter账号用户名/邮箱/手机号
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")  # Twitter账号密码

# Selenium浏览器模式
SELENIUM_HEADLESS = os.getenv("SELENIUM_HEADLESS", "true").lower() == "true"  # 是否无头模式（False=显示浏览器窗口）
SELENIUM_MANUAL_LOGIN = os.getenv("SELENIUM_MANUAL_LOGIN", "false").lower() == "true"  # 是否手动登录（True=暂停让用户手动登录）

# 爬取设置
MAX_TWEETS = 1000  # 最大爬取推文数量，设为None则无限制
DOWNLOAD_VIDEOS = True
DOWNLOAD_PHOTOS = True
DOWNLOAD_REPLIES = True

# 文档设置
GENERATE_HTML_DOC = True  # 生成HTML文档
GENERATE_MD_DOC = True    # 生成Markdown文档
