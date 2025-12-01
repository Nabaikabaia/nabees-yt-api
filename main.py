from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import yt_dlp
import os
import uuid
from datetime import datetime
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YouTube Downloader API by Nabees",
    version="1.0",
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
                "GET /audio/download": "Download audio only"
            },
            "example": "/video/info?url=https://youtu.be/Yocja_N5s1I"
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
            "platform": "Render Python FastAPI"
        }
    )

@app.get("/video/info")
async def get_video_info(url: str):
    """
    Get video information
    Example: /video/info?url=https://youtu.be/Yocja_N5s1I
    """
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Process video formats
            formats = []
            for fmt in info.get('formats', []):
                if fmt.get('filesize') or fmt.get('filesize_approx'):
                    format_info = {
                        "format_id": fmt.get('format_id'),
                        "ext": fmt.get('ext'),
                        "quality": fmt.get('format_note', 'Unknown'),
                        "filesize": fmt.get('filesize') or fmt.get('filesize_approx', 0)
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
                "total_formats": len(formats),
                "sample_formats": formats[:5]  # Show first 5 formats
            }
            
            return create_response(
                "success",
                "Video information retrieved successfully",
                video_data
            )
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return create_response(
            "error",
            f"Failed to get video info: {str(e)}"
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
        
        ydl_opts = {
            'outtmpl': filepath.replace('.mp4', ''),
            'format': quality,
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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
        return create_response(
            "error",
            f"Download failed: {str(e)}"
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
        
        ydl_opts = {
            'outtmpl': filepath.replace('.mp3', ''),
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        return FileResponse(
            path=filepath.replace('.mp3', '.mp3'),
            filename=f"audio_{download_id}.mp3",
            media_type='audio/mpeg'
        )
        
    except Exception as e:
        return create_response(
            "error",
            f"Audio download failed: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
