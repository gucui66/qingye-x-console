"""
基于Tweepy的Twitter爬虫
需要Twitter API密钥
"""
import json
import os
from typing import List, Dict
from datetime import datetime
import core.config as config


class TweepyTwitterScraper:
    """使用Tweepy的Twitter爬虫"""
    
    def __init__(self, username: str):
        """
        初始化Tweepy爬虫
        :param username: Twitter用户名
        """
        self.username = username
        self.tweets_data = []
        self.profile_image_url = ''
        
        try:
            import tweepy
            
            # 检查API密钥配置
            if not config.TWITTER_BEARER_TOKEN:
                raise ValueError("""
Twitter API Bearer Token未配置！

请按以下步骤获取API密钥：

1. 访问 https://developer.twitter.com/
2. 登录并创建一个App
3. 在App设置中找到 "Keys and tokens"
4. 复制 Bearer Token

然后在项目根目录的 .env 中设置：
TWITTER_BEARER_TOKEN=你的Bearer Token

或者先导出环境变量再启动：
export TWITTER_BEARER_TOKEN="你的Bearer Token"

如果你使用的是本地管理后台，也可以在后台配置页里直接保存 Bearer Token。
""")
            
            # 创建客户端
            self.client = tweepy.Client(bearer_token=config.TWITTER_BEARER_TOKEN)
            
        except ImportError:
            raise ImportError("请先安装tweepy: pip install tweepy")
        except Exception as e:
            raise Exception(f"Tweepy初始化失败: {e}")
    
    def scrape_user_tweets(self, max_tweets=None, progress_callback=None):
        """
        使用Tweepy爬取推文
        :param max_tweets: 最大爬取数量
        :param progress_callback: 进度回调函数 callback(current, total)
        :return: 推文列表
        """
        import tweepy
        
        print(f"开始使用Twitter API爬取用户 @{self.username} 的推文...")
        
        # 设置最大推文数（None表示无限制）
        if max_tweets is None:
            max_tweets = 999999  # 设置一个很大的数字代表无限制
        
        try:
            # 获取用户信息
            user = self.client.get_user(username=self.username, user_fields=['profile_image_url'])
            if not user.data:
                print(f"用户 @{self.username} 不存在")
                return []
            self.profile_image_url = self._prefer_large_profile_image(
                getattr(user.data, 'profile_image_url', '') or ''
            )
            
            user_id = user.data.id
            print(f"找到用户: @{self.username} (ID: {user_id})")
            
            # 获取推文
            tweets = []
            pagination_token = None
            
            while len(tweets) < max_tweets:
                # Twitter API 要求 max_results 必须在 5-100 之间
                remaining = max_tweets - len(tweets)
                batch_size = max(5, min(100, remaining))
                
                response = self.client.get_users_tweets(
                    user_id,
                    max_results=batch_size,
                    tweet_fields=['created_at', 'public_metrics', 'attachments', 'referenced_tweets', 'text'],
                    expansions=['attachments.media_keys', 'referenced_tweets.id'],
                    media_fields=['url', 'preview_image_url', 'variants', 'type'],
                    pagination_token=pagination_token
                )
                
                if not response.data:
                    break
                
                # 处理媒体数据
                media_dict = {}
                if response.includes and 'media' in response.includes:
                    for media in response.includes['media']:
                        media_dict[media.media_key] = media
                
                # 处理推文
                for tweet in response.data:
                    # 如果已经达到目标数量，停止添加
                    if len(tweets) >= max_tweets:
                        break
                    
                    tweet_data = self._extract_tweet_data(tweet, media_dict)
                    tweets.append(tweet_data)
                    
                    # 进度回调
                    if progress_callback:
                        progress_callback(len(tweets), max_tweets)
                    
                    if len(tweets) % 10 == 0:
                        print(f"已爬取 {len(tweets)} 条推文...")
                
                # 检查是否有下一页
                if not response.meta.get('next_token'):
                    break
                
                pagination_token = response.meta['next_token']
            
            self.tweets_data = tweets
            print(f"爬取完成！共获取 {len(tweets)} 条推文")
            return tweets
            
        except tweepy.errors.Unauthorized as e:
            raise Exception(f"API认证失败: {e}\n请检查你的Bearer Token是否正确")
        except tweepy.errors.Forbidden as e:
            raise Exception(f"无权访问: {e}\n可能是API权限不足或用户是私密账号")
        except tweepy.errors.NotFound as e:
            raise Exception(f"用户不存在: {e}")
        except tweepy.errors.TooManyRequests:
            raise Exception(
                "Twitter API 速率限制：请求过于频繁。\n\n"
                "解决方案：\n"
                "1. 等待 15 分钟后再试\n"
                "2. 减少爬取数量\n"
                "3. Twitter API 限制：每15分钟最多请求 300 次\n\n"
                "如需大量爬取，请考虑升级 Twitter API 套餐"
            )
        except Exception as e:
            raise Exception(f"爬取失败: {e}")
    
    def _extract_tweet_data(self, tweet, media_dict) -> Dict:
        """
        提取推文数据
        :param tweet: tweepy tweet对象
        :param media_dict: 媒体字典
        :return: 推文数据字典
        """
        data = {
            'id': tweet.id,
            'url': f'https://twitter.com/{self.username}/status/{tweet.id}',
            'date': tweet.created_at.isoformat() if hasattr(tweet, 'created_at') and tweet.created_at else None,
            'content': tweet.text,
            'user': self.username,
            'author_username': self.username,
            'author_avatar_url': getattr(self, 'profile_image_url', ''),
            'likes': tweet.public_metrics.get('like_count', 0) if hasattr(tweet, 'public_metrics') else 0,
            'retweets': tweet.public_metrics.get('retweet_count', 0) if hasattr(tweet, 'public_metrics') else 0,
            'replies': tweet.public_metrics.get('reply_count', 0) if hasattr(tweet, 'public_metrics') else 0,
            'is_reply': hasattr(tweet, 'referenced_tweets') and tweet.referenced_tweets and 
                       any(ref.type == 'replied_to' for ref in tweet.referenced_tweets),
            'media': [],
            'videos': [],
            'photos': []
        }
        
        # 提取媒体信息
        if hasattr(tweet, 'attachments') and tweet.attachments:
            media_keys = tweet.attachments.get('media_keys', [])
            
            video_index = 0
            photo_index = 0
            for media_key in media_keys:
                if media_key not in media_dict:
                    continue
                
                media = media_dict[media_key]
                media_info = {
                    'type': media.type,
                    'url': None,
                    'thumbnail_url': None
                }
                
                # 图片（兼容dict和对象格式）
                if media.type == 'photo':
                    if isinstance(media, dict):
                        media_info['url'] = media.get('url')
                    else:
                        media_info['url'] = media.url if hasattr(media, 'url') else None
                    media_info['type'] = 'photo'
                    media_info['media_index'] = photo_index
                    data['photos'].append(media_info)
                    photo_index += 1
                
                # 视频
                elif media.type == 'video' or media.type == 'animated_gif':
                    # 获取最高质量的视频（兼容dict和对象格式）
                    if hasattr(media, 'variants') and media.variants:
                        # 处理variants中可能是dict或对象的情况
                        video_variants = []
                        for v in media.variants:
                            if isinstance(v, dict):
                                if v.get('bit_rate'):
                                    video_variants.append(v)
                            elif hasattr(v, 'bit_rate') and v.bit_rate:
                                video_variants.append(v)
                        
                        if video_variants:
                            # 找到最高码率的视频
                            if isinstance(video_variants[0], dict):
                                best_video = max(video_variants, key=lambda x: x.get('bit_rate', 0))
                                media_info['url'] = best_video.get('url')
                            else:
                                best_video = max(video_variants, key=lambda x: x.bit_rate)
                                media_info['url'] = best_video.url
                        elif media.variants:
                            # 取第一个variant
                            variant = media.variants[0]
                            if isinstance(variant, dict):
                                media_info['url'] = variant.get('url')
                            else:
                                media_info['url'] = variant.url if hasattr(variant, 'url') else None
                    
                    # 获取缩略图
                    if hasattr(media, 'preview_image_url'):
                        media_info['thumbnail_url'] = media.preview_image_url
                    
                    media_info['type'] = 'video'
                    media_info['media_index'] = video_index
                    media_info['playlist_item'] = video_index + 1
                    data['videos'].append(media_info)
                    video_index += 1
                
                data['media'].append(media_info)
        
        return data

    @staticmethod
    def _prefer_large_profile_image(url: str) -> str:
        text = str(url or '').strip()
        if not text:
            return ''
        return text.replace('_normal.', '_400x400.')
    
    def get_videos(self) -> List[Dict]:
        """获取所有包含视频的推文"""
        return [t for t in self.tweets_data if t['videos']]
    
    def get_photos(self) -> List[Dict]:
        """获取所有包含照片的推文"""
        return [t for t in self.tweets_data if t['photos']]
    
    def get_replies(self) -> List[Dict]:
        """获取所有回复推文"""
        return [t for t in self.tweets_data if t['is_reply']]
    
    def save_raw_data(self, filename="tweets_raw.json", output_dir=None):
        """保存原始数据"""
        target_dir = output_dir or config.OUTPUT_DIR
        os.makedirs(target_dir, exist_ok=True)
        filepath = os.path.join(target_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.tweets_data, f, ensure_ascii=False, indent=2)
        print(f"原始数据已保存至: {filepath}")


# 提供兼容性别名
TwitterScraper = TweepyTwitterScraper
SNSCRAPE_AVAILABLE = False  # 标记为使用Tweepy而非snscrape
