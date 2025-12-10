from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import yt_dlp
import os
import uuid
import time
from datetime import datetime
import logging
import random

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Downloader API by Nabees",
    version="2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Allow all origins (you can restrict this later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# Anti-bot user agents (rotate randomly)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

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

def get_ytdl_opts_with_bot_protection(use_cookies=True):
    """Get yt-dlp options with anti-bot protection"""
    # Check if cookies file exists
    cookie_file = 'cookies.txt' if use_cookies and os.path.exists('cookies.txt') else None
    
    opts = {
        'quiet': True,
        'no_warnings': True,
        'ignoreerrors': False,
        'no_check_certificate': True,
        'prefer_insecure': False,
        
        # Custom headers to appear more like a browser
        'http_headers': {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        },
        
        # Rate limiting and retry settings
        'sleep_interval': 1,
        'max_sleep_interval': 5,
        'retries': 3,
        'fragment_retries': 3,
        'skip_unavailable_fragments': True,
        'keep_fragments': False,
        
        # Extract settings
        'extract_flat': False,
        'force_ipv4': True,
        'geo_bypass': True,
        'geo_bypass_country': 'US',
        
        # Cookie settings
        'cookiefile': cookie_file,
    }
    
    if cookie_file:
        opts['cookiesfrombrowser'] = ('chrome', )  # Auto-load from browser if available
    
    return opts

def extract_video_info_with_retry(url, max_retries=3):
    """Extract video info with retry logic for bot challenges"""
    for attempt in range(max_retries):
        try:
            # Rotate user agent each attempt
            opts = get_ytdl_opts_with_bot_protection()
            opts['http_headers']['User-Agent'] = random.choice(USER_AGENTS)
            
            # Add delay between retries (except first attempt)
            if attempt > 0:
                delay = 2 ** attempt  # Exponential backoff: 2, 4 seconds
                logger.info(f"Retry attempt {attempt + 1}/{max_retries} after {delay}s delay")
                time.sleep(delay)
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                return info
                
        except yt_dlp.utils.DownloadError as e:
            error_msg = str(e)
            
            # Check for specific bot challenges
            if any(keyword in error_msg.lower() for keyword in ['sign in', 'bot', 'confirm']):
                if attempt < max_retries - 1:
                    logger.warning(f"Bot challenge detected (attempt {attempt + 1}): {error_msg[:100]}...")
                    continue
                else:
                    raise Exception(f"YouTube bot challenge after {max_retries} attempts. Try adding cookies.txt")
            
            # Check for age restriction
            elif 'age restricted' in error_msg.lower():
                # Try with different options for age-restricted videos
                if attempt == 0:
                    logger.info("Age-restricted video detected, trying with cookies...")
                    opts = get_ytdl_opts_with_bot_protection(use_cookies=True)
                    continue
                else:
                    raise Exception("Age-restricted video. You need to provide cookies with age verification.")
            
            # Other errors
            else:
                raise Exception(f"YouTube error: {error_msg}")
    
    raise Exception(f"Failed after {max_retries} retries")

@app.get("/")
async def root():
    """Root endpoint with API info"""
    return create_response(
        "success",
        "YouTube Downloader API by Nabees",
        {
            "endpoints": {
                "GET /": "This info page",
                "GET /health": "Health check",
                "GET /video/info": "Get video information",
                "GET /video/download": "Download video",
                "GET /audio/download": "Download audio only",
                "GET /troubleshoot": "API troubleshooting tips"
            },
            "example": "/video/info?url=https://youtu.be/Yocja_N5s1I",
            "note": "For best results, add a cookies.txt file to bypass bot checks"
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return create_response(
        "success",
        "API is running smoothly on Render!",
        {
            "status": "healthy",
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "platform": "Render Python FastAPI",
            "yt_dlp_version": yt_dlp.version.__version__
        }
    )

@app.get("/troubleshoot")
async def troubleshoot():
    """Get troubleshooting tips"""
    has_cookies = os.path.exists('cookies.txt')
    return create_response(
        "success",
        "Troubleshooting information",
        {
            "cookies_file": "Present" if has_cookies else "Missing",
            "cookies_help": "Add a cookies.txt file exported from your browser when logged into YouTube" if not has_cookies else "Cookies file detected",
            "common_issues": [
                "'Sign in to confirm' error: YouTube is blocking automated requests",
                "Solution 1: Add cookies.txt file to your project",
                "Solution 2: Wait 24 hours for server IP to cool down",
                "Solution 3: Use residential proxy (advanced)"
            ],
            "current_user_agent": random.choice(USER_AGENTS)[:50] + "..."
        }
    )

@app.get("/video/info")
async def get_video_info(url: str):
    """
    Get video information
    Example: /video/info?url=https://youtu.be/Yocja_N5s1I
    """
    try:
        # Validate URL
        if not url or 'youtu' not in url:
            return create_response(
                "error",
                "Please provide a valid YouTube URL"
            )
        
        # Extract video info with retry logic
        info = extract_video_info_with_retry(url)
        
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
        
        # Sort formats by quality
        def sort_key(fmt):
            quality = fmt['quality']
            if 'p' in quality:
                try:
                    return -int(quality.replace('p', ''))
                except:
                    return 0
            return 0
        
        formats.sort(key=sort_key)
        
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
            "audio_formats": [f for f in formats if not f['has_video'] and f['has_audio']][:3]
        }
        
        return create_response(
            "success",
            "Video information retrieved successfully",
            video_data
        )
        
    except Exception as e:
        logger.error(f"Error getting video info: {str(e)}")
        
        # Provide helpful error messages
        error_msg = str(e)
        if 'bot' in error_msg.lower() or 'sign in' in error_msg.lower():
            suggestion = "Add a cookies.txt file to bypass bot detection"
        elif 'age restricted' in error_msg.lower():
            suggestion = "Video is age-restricted. Provide cookies with age verification"
        elif 'unavailable' in error_msg.lower():
            suggestion = "Video may be private or removed"
        else:
            suggestion = "Try again later or use a different video"
        
        return create_response(
            "error",
            f"Failed to get video info: {error_msg}",
            {"suggestion": suggestion, "tip": "See /troubleshoot endpoint for help"}
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
        
        # Get options with bot protection
        opts = get_ytdl_opts_with_bot_protection()
        opts['outtmpl'] = filepath.replace('.mp4', '')
        opts['format'] = quality
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            result = ydl.extract_info(url, download=True)
            actual_filename = ydl.prepare_filename(result)
        
        # Find the actual downloaded file
        for ext in ['.mp4', '.webm', '.mkv', '.m4a']:
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
            f"Download failed: {str(e)}",
            {"tip": "Try the /video/info endpoint first to check if video is accessible"}
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
        
        # Get options with bot protection
        opts = get_ytdl_opts_with_bot_protection()
        opts['outtmpl'] = filepath.replace('.mp3', '')
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        
        # Check for the actual file (could be .mp3 or .m4a)
        actual_file = filepath.replace('.mp3', '.mp3')
        if not os.path.exists(actual_file):
            actual_file = filepath.replace('.mp3', '.m4a')
        
        return FileResponse(
            path=actual_file,
            filename=f"audio_{download_id}.{actual_file.split('.')[-1]}",
            media_type='audio/mpeg'
        )
        
    except Exception as e:
        logger.error(f"Audio download error: {str(e)}")
        return create_response(
            "error",
            f"Audio download failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
