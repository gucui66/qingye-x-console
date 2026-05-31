"""
文档生成模块
生成视频、照片和回复的汇总文档
"""
import os
from typing import List, Dict
from datetime import datetime
import core.config as config


class DocumentGenerator:
    """文档生成器"""
    
    def __init__(self, username: str, docs_dir: str = None):
        """
        初始化文档生成器
        :param username: Twitter用户名
        :param docs_dir: 自定义文档输出目录（None则使用全局配置）
        """
        self.username = username
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.docs_dir = docs_dir if docs_dir else config.DOCS_DIR

    def _resolve_media_link(self, local_path: str = None, app_url: str = None):
        """优先使用本地文件，其次使用应用内数据库流式地址。"""
        if local_path and os.path.exists(local_path):
            return os.path.relpath(local_path, self.docs_dir)
        return app_url or ''
    
    def generate_video_document(self, video_results: List[Dict]):
        """
        生成视频文档
        :param video_results: 视频下载结果列表
        """
        if not video_results:
            print("没有视频数据，跳过视频文档生成")
            return
        
        print(f"\n生成视频文档...")
        
        if config.GENERATE_HTML_DOC:
            self._generate_video_html(video_results)
        
        if config.GENERATE_MD_DOC:
            self._generate_video_markdown(video_results)
    
    def generate_photo_document(self, photo_results: List[Dict]):
        """
        生成照片文档
        :param photo_results: 照片下载结果列表
        """
        if not photo_results:
            print("没有照片数据，跳过照片文档生成")
            return
        
        print(f"\n生成照片文档...")
        
        if config.GENERATE_HTML_DOC:
            self._generate_photo_html(photo_results)
        
        if config.GENERATE_MD_DOC:
            self._generate_photo_markdown(photo_results)
    
    def generate_reply_document(self, replies: List[Dict]):
        """
        生成回复文档
        :param replies: 回复推文列表
        """
        if not replies:
            print("没有回复数据，跳过回复文档生成")
            return
        
        print(f"\n生成回复文档...")
        
        if config.GENERATE_HTML_DOC:
            self._generate_reply_html(replies)
        
        if config.GENERATE_MD_DOC:
            self._generate_reply_markdown(replies)
    
    def _generate_video_html(self, video_results: List[Dict]):
        """生成视频HTML文档"""
        filename = f"videos_{self.username}_{self.timestamp}.html"
        filepath = os.path.join(self.docs_dir, filename)
        attempted_count = len(video_results)
        success_count = sum(1 for v in video_results if v['success'])
        failed_count = attempted_count - success_count
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{self.username} 的视频汇总</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(180deg, #f9fcf7 0%, #f2f8ee 100%);
            color: #203120;
        }}
        h1 {{
            color: #78bf63;
            border-bottom: 3px solid #78bf63;
            padding-bottom: 10px;
        }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .video-item {{
            background: white;
            margin-bottom: 20px;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .video-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .video-number {{
            font-size: 24px;
            font-weight: bold;
            color: #78bf63;
        }}
        .video-date {{
            color: #607460;
            font-size: 14px;
        }}
        .video-content {{
            margin: 15px 0;
            padding: 15px;
            background: #eef7e8;
            border-radius: 5px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .video-thumbnail {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            margin: 10px 0;
        }}
        .video-links {{
            margin-top: 15px;
        }}
        .video-links a {{
            display: inline-block;
            margin-right: 10px;
            padding: 8px 15px;
            background: #78bf63;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 14px;
        }}
        .video-links a:hover {{
            background: #4d8f45;
        }}
        .tweet-link {{
            background: #72866f !important;
        }}
        .tweet-link:hover {{
            background: #5b6f57 !important;
        }}
        video {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <h1>@{self.username} 的视频汇总</h1>
    
    <div class="stats">
        <p><strong>下载尝试总数：</strong>{attempted_count}</p>
        <p><strong>生成时间：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><strong>成功下载：</strong>{success_count}</p>
        <p><strong>下载失败：</strong>{failed_count}</p>
    </div>
"""
        
        for video in video_results:
            date_str = video['date'][:10] if video['date'] else '未知日期'
            
            html_content += f"""
    <div class="video-item">
        <div class="video-header">
            <span class="video-number">视频 #{video['number']:04d}</span>
            <span class="video-date">{date_str}</span>
        </div>
        
        <div class="video-content">{self._escape_html(video['tweet_content'])}</div>
"""
            
            # 如果视频下载成功，显示视频
            video_link = self._resolve_media_link(video.get('video_path'), video.get('video_app_url'))
            if video['success'] and video_link:
                html_content += f"""
        <video controls>
            <source src="{video_link}" type="video/mp4">
            您的浏览器不支持视频标签。
        </video>
"""
            # 否则显示缩略图（如果有）
            elif video.get('thumbnail_path') and os.path.exists(video['thumbnail_path']):
                rel_path = os.path.relpath(video['thumbnail_path'], self.docs_dir)
                html_content += f"""
        <img src="{rel_path}" alt="视频缩略图" class="video-thumbnail">
"""
            elif video.get('thumbnail_url'):
                html_content += f"""
        <img src="{video['thumbnail_url']}" alt="视频缩略图" class="video-thumbnail">
"""
            
            # 获取视频源URL（优先使用直连URL，否则使用推文URL）
            source_url = video.get('direct_url') or video.get('tweet_url_for_ytdlp') or video.get('video_url') or video['tweet_url']
            
            html_content += f"""
        <div class="video-links">
            <a href="{video['tweet_url']}" target="_blank" class="tweet-link">查看原推文</a>
            <a href="{source_url}" target="_blank">视频源链接</a>
"""
            
            if video['success'] and video_link:
                html_content += f"""
            <a href="{video_link}" download>下载视频</a>
"""
            
            html_content += """
        </div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"  ✓ HTML文档已生成: {filepath}")
    
    def _generate_video_markdown(self, video_results: List[Dict]):
        """生成视频Markdown文档"""
        filename = f"videos_{self.username}_{self.timestamp}.md"
        filepath = os.path.join(self.docs_dir, filename)
        attempted_count = len(video_results)
        success_count = sum(1 for v in video_results if v['success'])
        failed_count = attempted_count - success_count
        
        md_content = f"""# @{self.username} 的视频汇总

**下载尝试总数：** {attempted_count}  
**生成时间：** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**成功下载：** {success_count}  
**下载失败：** {failed_count}

---

"""
        
        for video in video_results:
            date_str = video['date'][:10] if video['date'] else '未知日期'
            
            md_content += f"""## 视频 #{video['number']:04d}

**日期：** {date_str}  
**推文链接：** {video['tweet_url']}

### 推文内容

```
{video['tweet_content']}
```

"""
            
            # 如果有缩略图
            if video.get('thumbnail_path') and os.path.exists(video['thumbnail_path']):
                rel_path = os.path.relpath(video['thumbnail_path'], self.docs_dir)
                md_content += f"### 缩略图\n\n![缩略图]({rel_path})\n\n"
            elif video.get('thumbnail_url'):
                md_content += f"### 缩略图\n\n![缩略图]({video['thumbnail_url']})\n\n"
            
            # 获取视频源URL（优先使用直连URL，否则使用推文URL）
            source_url = video.get('direct_url') or video.get('tweet_url_for_ytdlp') or video.get('video_url') or video['tweet_url']
            
            md_content += f"""### 链接

- [视频源链接]({source_url})
- [推文地址]({video['tweet_url']})
"""
            
            video_link = self._resolve_media_link(video.get('video_path'), video.get('video_app_url'))
            if video['success'] and video_link:
                md_content += f"- [本地视频]({video_link})\n"
            
            md_content += "\n---\n\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"  ✓ Markdown文档已生成: {filepath}")
    
    def _generate_photo_html(self, photo_results: List[Dict]):
        """生成照片HTML文档"""
        filename = f"photos_{self.username}_{self.timestamp}.html"
        filepath = os.path.join(self.docs_dir, filename)
        attempted_count = len(photo_results)
        success_count = sum(1 for p in photo_results if p['success'])
        failed_count = attempted_count - success_count
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{self.username} 的照片汇总</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(180deg, #f9fcf7 0%, #f2f8ee 100%);
            color: #203120;
        }}
        h1 {{
            color: #78bf63;
            border-bottom: 3px solid #78bf63;
            padding-bottom: 10px;
        }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .photo-item {{
            background: white;
            margin-bottom: 20px;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .photo-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .photo-number {{
            font-size: 24px;
            font-weight: bold;
            color: #78bf63;
        }}
        .photo-date {{
            color: #607460;
            font-size: 14px;
        }}
        .photo-content {{
            margin: 15px 0;
            padding: 15px;
            background: #eef7e8;
            border-radius: 5px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .photo-image {{
            max-width: 100%;
            height: auto;
            border-radius: 5px;
            margin: 10px 0;
            cursor: pointer;
            transition: transform 0.2s;
        }}
        .photo-image:hover {{
            transform: scale(1.02);
        }}
        .photo-links {{
            margin-top: 15px;
        }}
        .photo-links a {{
            display: inline-block;
            margin-right: 10px;
            padding: 8px 15px;
            background: #78bf63;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 14px;
        }}
        .photo-links a:hover {{
            background: #4d8f45;
        }}
        .tweet-link {{
            background: #72866f !important;
        }}
        .tweet-link:hover {{
            background: #5b6f57 !important;
        }}
    </style>
</head>
<body>
    <h1>@{self.username} 的照片汇总</h1>
    
    <div class="stats">
        <p><strong>下载尝试总数：</strong>{attempted_count}</p>
        <p><strong>生成时间：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        <p><strong>成功下载：</strong>{success_count}</p>
        <p><strong>下载失败：</strong>{failed_count}</p>
    </div>
"""
        
        for photo in photo_results:
            date_str = photo['date'][:10] if photo['date'] else '未知日期'
            
            html_content += f"""
    <div class="photo-item">
        <div class="photo-header">
            <span class="photo-number">照片 #{photo['number']:04d}</span>
            <span class="photo-date">{date_str}</span>
        </div>
        
        <div class="photo-content">{self._escape_html(photo['tweet_content'])}</div>
"""
            
            # 如果照片下载成功，显示照片
            photo_link = self._resolve_media_link(photo.get('photo_path'), photo.get('photo_app_url'))
            if photo['success'] and photo_link:
                html_content += f"""
        <img src="{photo_link}" alt="照片 {photo['number']}" class="photo-image">
"""
            
            html_content += f"""
        <div class="photo-links">
            <a href="{photo['tweet_url']}" target="_blank" class="tweet-link">查看原推文</a>
            <a href="{photo['photo_url']}" target="_blank">原始照片链接</a>
"""
            
            if photo['success'] and photo_link:
                html_content += f"""
            <a href="{photo_link}" download>下载照片</a>
"""
            
            html_content += """
        </div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"  ✓ HTML文档已生成: {filepath}")
    
    def _generate_photo_markdown(self, photo_results: List[Dict]):
        """生成照片Markdown文档"""
        filename = f"photos_{self.username}_{self.timestamp}.md"
        filepath = os.path.join(self.docs_dir, filename)
        attempted_count = len(photo_results)
        success_count = sum(1 for p in photo_results if p['success'])
        failed_count = attempted_count - success_count
        
        md_content = f"""# @{self.username} 的照片汇总

**下载尝试总数：** {attempted_count}  
**生成时间：** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}  
**成功下载：** {success_count}  
**下载失败：** {failed_count}

---

"""
        
        for photo in photo_results:
            date_str = photo['date'][:10] if photo['date'] else '未知日期'
            
            md_content += f"""## 照片 #{photo['number']:04d}

**日期：** {date_str}  
**推文链接：** {photo['tweet_url']}

### 推文内容

```
{photo['tweet_content']}
```

"""
            
            # 如果照片存在
            photo_link = self._resolve_media_link(photo.get('photo_path'), photo.get('photo_app_url'))
            if photo['success'] and photo_link:
                md_content += f"### 照片\n\n![照片]({photo_link})\n\n"
            
            md_content += f"""### 链接

- [原始照片]({photo['photo_url']})
- [推文地址]({photo['tweet_url']})
"""
            
            if photo['success'] and photo_link:
                md_content += f"- [本地照片]({photo_link})\n"
            
            md_content += "\n---\n\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"  ✓ Markdown文档已生成: {filepath}")
    
    def _generate_reply_html(self, replies: List[Dict]):
        """生成回复HTML文档"""
        filename = f"replies_{self.username}_{self.timestamp}.html"
        filepath = os.path.join(self.docs_dir, filename)
        
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>@{self.username} 的回复汇总</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: linear-gradient(180deg, #f9fcf7 0%, #f2f8ee 100%);
            color: #203120;
        }}
        h1 {{
            color: #78bf63;
            border-bottom: 3px solid #78bf63;
            padding-bottom: 10px;
        }}
        .stats {{
            background: white;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .reply-item {{
            background: white;
            margin-bottom: 20px;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .reply-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #d7e6d0;
        }}
        .reply-date {{
            color: #607460;
            font-size: 14px;
        }}
        .reply-content {{
            margin: 15px 0;
            padding: 15px;
            background: #eef7e8;
            border-radius: 5px;
            white-space: pre-wrap;
            word-wrap: break-word;
        }}
        .reply-meta {{
            display: flex;
            gap: 20px;
            margin-top: 10px;
            color: #607460;
            font-size: 14px;
        }}
        .reply-links {{
            margin-top: 15px;
        }}
        .reply-links a {{
            display: inline-block;
            padding: 8px 15px;
            background: #78bf63;
            color: white;
            text-decoration: none;
            border-radius: 5px;
            font-size: 14px;
        }}
        .reply-links a:hover {{
            background: #4d8f45;
        }}
    </style>
</head>
<body>
    <h1>@{self.username} 的回复汇总</h1>
    
    <div class="stats">
        <p><strong>总回复数：</strong>{len(replies)}</p>
        <p><strong>生成时间：</strong>{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </div>
"""
        
        for i, reply in enumerate(replies, 1):
            date_str = reply['date'][:10] if reply['date'] else '未知日期'
            
            html_content += f"""
    <div class="reply-item">
        <div class="reply-header">
            <span><strong>回复 #{i}</strong></span>
            <span class="reply-date">{date_str}</span>
        </div>
        
        <div class="reply-content">{self._escape_html(reply['content'])}</div>
        
        <div class="reply-meta">
            <span>❤️ {reply.get('likes', 0)}</span>
            <span>🔄 {reply.get('retweets', 0)}</span>
            <span>💬 {reply.get('replies', 0)}</span>
        </div>
        
        <div class="reply-links">
            <a href="{reply['url']}" target="_blank">查看原推文</a>
        </div>
    </div>
"""
        
        html_content += """
</body>
</html>
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"  ✓ HTML文档已生成: {filepath}")
    
    def _generate_reply_markdown(self, replies: List[Dict]):
        """生成回复Markdown文档"""
        filename = f"replies_{self.username}_{self.timestamp}.md"
        filepath = os.path.join(self.docs_dir, filename)
        
        md_content = f"""# @{self.username} 的回复汇总

**总回复数：** {len(replies)}  
**生成时间：** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

"""
        
        for i, reply in enumerate(replies, 1):
            date_str = reply['date'][:10] if reply['date'] else '未知日期'
            
            md_content += f"""## 回复 #{i}

**日期：** {date_str}  
**链接：** {reply['url']}

### 内容

```
{reply['content']}
```

**互动数据：** ❤️ {reply.get('likes', 0)} | 🔄 {reply.get('retweets', 0)} | 💬 {reply.get('replies', 0)}

---

"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"  ✓ Markdown文档已生成: {filepath}")
    
    @staticmethod
    def _escape_html(text: str) -> str:
        """转义HTML特殊字符"""
        if not text:
            return ""
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))
