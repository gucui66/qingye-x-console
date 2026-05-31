#!/usr/bin/env python3
"""
测试视频下载功能
快速验证双保险方案是否正常工作
"""
import subprocess
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

def test_ytdlp_installed():
    """测试yt-dlp是否安装"""
    print("🔍 测试1: 检查yt-dlp安装...")
    try:
        result = subprocess.run(['yt-dlp', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            version = result.stdout.strip()
            print(f"   ✅ yt-dlp已安装: {version}")
            return True
        else:
            print(f"   ✗ yt-dlp命令执行失败")
            return False
    except FileNotFoundError:
        print(f"   ✗ 未找到yt-dlp命令")
        print(f"   💡 安装方法: pip install yt-dlp")
        return False

def test_ffmpeg_installed():
    """测试ffmpeg是否安装（yt-dlp某些格式需要）"""
    print("\n🔍 测试2: 检查ffmpeg安装...")
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        if result.returncode == 0:
            version_line = result.stdout.split('\n')[0]
            print(f"   ✅ ffmpeg已安装: {version_line}")
            return True
        else:
            print(f"   ⚠️ ffmpeg命令执行失败（可选）")
            return False
    except FileNotFoundError:
        print(f"   ⚠️ 未找到ffmpeg命令（可选，某些视频格式需要）")
        return False

def test_cookies_exist():
    """测试cookies文件是否存在"""
    print("\n🔍 测试3: 检查Twitter cookies...")
    cookies_file = ROOT_DIR / 'twitter_cookies.json'
    if os.path.exists(cookies_file):
        import json
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
            cookie_names = [c.get('name') for c in cookies]
            has_auth = 'auth_token' in cookie_names
            if has_auth:
                print(f"   ✅ cookies文件存在且包含auth_token ({len(cookies)}个cookies)")
                return True
            else:
                print(f"   ⚠️ cookies文件存在但缺少auth_token")
                print(f"   💡 使用'获取Cookie助手.py'重新获取")
                return False
        except:
            print(f"   ✗ cookies文件格式错误")
            return False
    else:
        print(f"   ⚠️ 未找到cookies文件: {cookies_file}")
        print(f"   💡 使用'获取Cookie助手.py'获取cookies")
        return False

def test_download_video(tweet_url=None):
    """测试下载一个视频"""
    if not tweet_url:
        print("\n⏭️  跳过测试4: 下载测试（未提供推文URL）")
        print("   💡 用法: python 测试视频下载.py https://twitter.com/xxx/status/xxx")
        return None
    
    print(f"\n🔍 测试4: 下载视频...")
    print(f"   推文: {tweet_url}")
    
    output_file = '/tmp/test_video.mp4'
    
    # 构建命令
    cmd = ['yt-dlp', '-f', 'best', '--no-playlist', '-o', output_file]
    
    # 如果有cookies，使用cookies
    cookies_file = ROOT_DIR / 'twitter_cookies.json'
    netscape_cookies = None
    if os.path.exists(cookies_file):
        print(f"   ├─ 转换cookies...")
        import json
        from services.downloader_helpers import convert_cookies_to_netscape
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            netscape_cookies = convert_cookies_to_netscape(str(cookies_file), cookies)
            if netscape_cookies:
                cmd.extend(['--cookies', netscape_cookies])
                print(f"   ├─ 使用cookies登录")
        except Exception as e:
            print(f"   ⚠️ cookies转换失败: {e}")
    
    cmd.append(tweet_url)
    
    print(f"   ├─ 开始下载...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(output_file):
            file_size = os.path.getsize(output_file)
            size_mb = file_size / 1024 / 1024
            print(f"   ✅ 下载成功! ({size_mb:.1f}MB)")
            print(f"   文件: {output_file}")
            
            # 清理测试文件
            try:
                os.remove(output_file)
                print(f"   ♻️  已清理测试文件")
            except:
                pass
            
            return True
        else:
            print(f"   ✗ 下载失败")
            if result.stderr:
                error_lines = [line for line in result.stderr.split('\n') if 'ERROR' in line]
                if error_lines:
                    print(f"   错误: {error_lines[0]}")
            return False
    except subprocess.TimeoutExpired:
        print(f"   ✗ 下载超时 (>2分钟)")
        return False
    except Exception as e:
        print(f"   ✗ 异常: {e}")
        return False
    finally:
        if netscape_cookies and os.path.exists(netscape_cookies):
            try:
                os.remove(netscape_cookies)
            except OSError:
                pass

def test_selenium_cdp():
    """测试Selenium CDP功能"""
    print("\n🔍 测试5: Selenium CDP支持...")
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        # 启用性能日志
        chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.get('https://www.google.com')
        
        # 尝试获取性能日志
        logs = driver.get_log('performance')
        driver.quit()
        
        if len(logs) > 0:
            print(f"   ✅ Selenium CDP功能正常 (获取到{len(logs)}条日志)")
            return True
        else:
            print(f"   ⚠️ Selenium CDP可能未启用")
            return False
    except Exception as e:
        print(f"   ✗ Selenium CDP测试失败: {e}")
        return False

def main():
    print("=" * 60)
    print("🎯 Twitter视频下载 - 功能测试")
    print("=" * 60)
    
    # 运行所有测试
    results = []
    
    results.append(('yt-dlp安装', test_ytdlp_installed()))
    results.append(('ffmpeg安装', test_ffmpeg_installed()))
    results.append(('Twitter cookies', test_cookies_exist()))
    
    # 如果提供了推文URL，测试下载
    tweet_url = sys.argv[1] if len(sys.argv) > 1 else None
    if tweet_url:
        results.append(('视频下载', test_download_video(tweet_url)))
    
    results.append(('Selenium CDP', test_selenium_cdp()))
    
    # 打印总结
    print("\n" + "=" * 60)
    print("📊 测试总结")
    print("=" * 60)
    
    passed = sum(1 for name, result in results if result is True)
    failed = sum(1 for name, result in results if result is False)
    skipped = sum(1 for name, result in results if result is None)
    total = len(results)
    
    for name, result in results:
        status = "✅" if result is True else ("⚠️" if result is None else "✗")
        print(f"{status} {name}")
    
    print(f"\n通过: {passed}/{total}  失败: {failed}/{total}  跳过: {skipped}/{total}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！系统已就绪")
        return 0
    else:
        print("\n⚠️  部分测试失败，请查看上方错误信息")
        return 1

if __name__ == '__main__':
    sys.exit(main())
