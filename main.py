from fastapi import FastAPI, HTTPException
import yt_dlp
import os
import uuid
import time
from datetime import datetime
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Downloader API by Nabees",
    version="2.1",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuration
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def create_response(status: str, message: str, data=None):
    """Helper function for consistent responses"""
    response = {
        "status": status,
        "message": message,
        "creator": "Nabees",
        "timestamp": datetime.now().isoformat(),
        "service": "Render Python API"
    }
    if data:
        response["data"] = data
    return response

def get_ytdl_opts():
    """Get yt-dlp options with cookie support - FIXED VERSION"""
    # Check if cookies.txt exists
    cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
    
    opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'no_check_certificate': True,
        
        # HTTP headers to look like a browser
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        },
        
        # IMPORTANT: Disable browser cookie loading
        # Remove 'cookiesfrombrowser' completely
        'cookiefile': cookie_file,
        
        # Retry settings
        'retries': 5,
        'fragment_retries': 5,
        'skip_unavailable_fragments': True,
        
        # Network settings
        'socket_timeout': 30,
        'sleep_interval': 2,
    }
    
    return opts

def extract_video_info_safe(url):
    """Safe extraction with error handling"""
    try:
        opts = get_ytdl_opts()
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
            
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        
        # Check specific errors
        if "chrome cookies database" in error_msg:
            raise Exception("Cookie loading issue. Using only cookies.txt now.")
        elif "Sign in" in error_msg or "bot" in error_msg.lower():
            raise Exception("YouTube bot protection triggered.")
        elif "unavailable" in error_msg:
            raise Exception("Video is private, deleted, or region restricted.")
        else:
            raise Exception(f"YouTube error: {error_msg[:100]}")

@app.get("/")
async def root():
    """Root endpoint with API info"""
    cookie_exists = os.path.exists('cookies.txt')
    
    return create_response(
        "success",
        "YouTube Downloader API by Nabees",
        {
            "cookie_status": "Present" if cookie_exists else "Missing",
            "cookie_count": count_cookies() if cookie_exists else 0,
            "endpoints": {
                "GET /": "This info page",
                "GET /cookie-status": "Check cookie file",
                "GET /video/info": "Get video information",
                "GET /video/download": "Download video",
                "GET /audio/download": "Download audio only"
            },
            "example": "/video/info?url=https://youtu.be/Yocja_N5s1I",
            "note": f"Using {'cookies.txt' if cookie_exists else 'no cookies'}"
        }
    )

def count_cookies():
    """Count cookies in cookies.txt file"""
    try:
        with open('cookies.txt', 'r') as f:
            lines = [line.strip() for line in f.readlines() 
                    if line.strip() and not line.startswith('#')]
            return len(lines)
    except:
        return 0

@app.get("/cookie-status")
async def cookie_status():
    """Check the status of cookies.txt file"""
    if not os.path.exists('cookies.txt'):
        return create_response(
            "error",
            "cookies.txt file not found",
            {
                "action": "Add cookies.txt file to your project",
                "how_to": "Export cookies from browser when logged into YouTube"
            }
        )
    
    cookie_count = count_cookies()
    
    # Test if cookies work
    try:
        opts = {
            'quiet': True,
            'cookiefile': 'cookies.txt',
            # IMPORTANT: No cookiesfrombrowser
        }
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Test with a simple, always-available video
            info = ydl.extract_info('https://youtu.be/jNQXAC9IVRw', download=False)
        
        return create_response(
            "success",
            "Cookies are working!",
            {
                "cookie_count": cookie_count,
                "test_video": "First YouTube video",
                "test_result": "SUCCESS",
                "video_title": info.get('title', 'N/A')[:50]
            }
        )
        
    except Exception as e:
        error_msg = str(e)
        return create_response(
            "warning" if cookie_count > 0 else "error",
            f"Cookie file exists but has issues ({cookie_count} cookies)",
            {
                "error": error_msg[:150],
                "cookie_count": cookie_count,
                "fix": "Regenerate cookies.txt from logged-in browser if error persists"
            }
        )

@app.get("/video/info")
async def get_video_info(url: str):
    """
    Get video information
    Example: /video/info?url=https://youtu.be/Yocja_N5s1I
    """
    try:
        if not url or 'youtu' not in url:
            return create_response(
                "error",
                "Please provide a valid YouTube URL"
            )
        
        info = extract_video_info_safe(url)
        
        # Process video formats
        formats = []
        for fmt in info.get('formats', []):
            if fmt.get('filesize') or fmt.get('filesize_approx'):
                format_info = {
                    "format_id": fmt.get('format_id'),
                    "ext": fmt.get('ext'),
                    "quality": fmt.get('format_note', 'Unknown'),
                    "filesize": fmt.get('filesize') or fmt.get('filesize_approx', 0),
                    "has_video": fmt.get('vcodec') != 'none',
                    "has_audio": fmt.get('acodec') != 'none'
                }
                formats.append(format_info)
        
        video_data = {
            "title": info.get('title', 'Unknown'),
            "duration": info.get('duration_string', 'Unknown'),
            "view_count": info.get('view_count', 0),
            "uploader": info.get('uploader', 'Unknown'),
            "thumbnail": info.get('thumbnail', ''),
            "description": info.get('description', '')[:200] + '...' if info.get('description') else '',
            "upload_date": info.get('upload_date', 'Unknown'),
            "channel_url": info.get('channel_url', ''),
            "total_formats": len(formats),
            "video_formats": [f for f in formats if f['has_video']][:5],
            "audio_formats": [f for f in formats if not f['has_video'] and f['has_audio']][:3],
            "using_cookies": os.path.exists('cookies.txt')
        }
        
        return create_response(
            "success",
            "Video information retrieved successfully",
            video_data
        )
        
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        
        error_msg = str(e)
        if 'chrome cookies database' in error_msg:
            suggestion = "Fixed: Now using only cookies.txt file"
        elif 'bot' in error_msg.lower() or 'sign in' in error_msg.lower():
            suggestion = "YouTube is blocking. Cookies may be expired."
        elif 'age restricted' in error_msg.lower():
            suggestion = "Video is age-restricted"
        elif 'unavailable' in error_msg.lower():
            suggestion = "Video may be private or removed"
        else:
            suggestion = "Try a different video"
        
        return create_response(
            "error",
            f"Failed to get video info: {error_msg[:100]}",
            {
                "suggestion": suggestion,
                "cookie_file": "Present" if os.path.exists('cookies.txt') else "Missing",
                "cookie_count": count_cookies() if os.path.exists('cookies.txt') else 0
            }
        )

@app.get("/video/download")
async def download_video(url: str, quality: str = "best[height<=720]"):
    """
    Download video
    Example: /video/download?url=YOUTUBE_URL&quality=best[height<=720]
    """
    try:
        download_id = str(uuid.uuid4())
        filename = f"{download_id}.mp4"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        opts = get_ytdl_opts()
        opts['outtmpl'] = filepath.replace('.mp4', '')
        opts['format'] = quality
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(url, download=True)
            actual_filename = ydl.prepare_filename(result)
        
        # Find the actual downloaded file
        for ext in ['.mp4', '.webm', '.mkv']:
            if os.path.exists(actual_filename + ext):
                actual_file = actual_filename + ext
                break
        else:
            actual_file = actual_filename
        
        return FileResponse(
            path=actual_file,
            filename=f"video_{download_id}.{actual_file.split('.')[-1]}",
            media_type='video/mp4'
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return create_response(
            "error",
            f"Download failed: {str(e)[:100]}",
            {"tip": "Try the /video/info endpoint first to check accessibility"}
        )

@app.get("/audio/download")
async def download_audio(url: str):
    """
    Download audio only
    Example: /audio/download?url=YOUTUBE_URL
    """
    try:
        download_id = str(uuid.uuid4())
        filename = f"{download_id}.mp3"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        opts = get_ytdl_opts()
        opts['outtmpl'] = filepath.replace('.mp3', '')
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        return FileResponse(
            path=filepath.replace('.mp3', '.mp3'),
            filename=f"audio_{download_id}.mp3",
            media_type='audio/mpeg'
        )
        
    except Exception as e:
        logger.error(f"Audio download error: {str(e)}")
        return create_response(
            "error",
            f"Audio download failed: {str(e)[:100]}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
