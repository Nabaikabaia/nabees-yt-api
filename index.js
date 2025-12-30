const express = require('express');
const cors = require('cors');
const helmet = require('helmet');
const rateLimit = require('express-rate-limit');
const morgan = require('morgan');
const fs = require('fs');
const path = require('path');
const YT = require('./YTDownloader');

const app = express();
const PORT = process.env.PORT || 3000;

// Nãbēēs API Configuration
const API_NAME = "Nãbēēs YouTube API";
const API_VERSION = "2.0.0";
const API_AUTHOR = "Nãbēēs";
const CONTACT = "https://github.com/nabeels";
const MAX_FILE_AGE = 3 * 60 * 60 * 1000; // 3 hours for Render's ephemeral storage

// Ensure directories exist
const dirs = ['./XeonMedia/audio', './downloads', './temp'];
dirs.forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

// Middleware
app.use(helmet({
    contentSecurityPolicy: {
        directives: {
            defaultSrc: ["'self'"],
            styleSrc: ["'self'", "'unsafe-inline'"],
            scriptSrc: ["'self'"],
            imgSrc: ["'self'", "data:", "https://i.ytimg.com"]
        }
    }
}));

app.use(cors({
    origin: process.env.ALLOWED_ORIGINS ? process.env.ALLOWED_ORIGINS.split(',') : '*',
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type', 'Authorization', 'x-api-key']
}));

app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));
app.use(morgan('tiny'));

// Static files with cache control
app.use('/downloads', express.static('downloads', {
    maxAge: '1h',
    setHeaders: (res, path) => {
        res.set('X-Content-Type-Options', 'nosniff');
    }
}));

// API Key Middleware (optional)
const apiKeyMiddleware = (req, res, next) => {
    if (process.env.API_KEY_REQUIRED === 'true') {
        const apiKey = req.headers['x-api-key'] || req.query.api_key;
        const validKey = process.env.API_KEY;
        
        if (!apiKey || apiKey !== validKey) {
            return res.status(401).json({
                success: false,
                message: 'Invalid or missing API key',
                documentation: 'https://github.com/nabeels/nabeels-youtube-api'
            });
        }
    }
    next();
};

// Rate limiting per endpoint
const generalLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    max: process.env.RATE_LIMIT_MAX || 100,
    message: { success: false, message: 'Too many requests, please try again later.' },
    standardHeaders: true,
    legacyHeaders: false
});

const downloadLimiter = rateLimit({
    windowMs: 60 * 60 * 1000,
    max: process.env.DOWNLOAD_LIMIT_MAX || 10,
    message: { success: false, message: 'Download limit exceeded. Try again later.' }
});

// Routes
app.get('/', (req, res) => {
    res.json({
        api: API_NAME,
        version: API_VERSION,
        author: API_AUTHOR,
        status: 'online',
        timestamp: new Date().toISOString(),
        endpoints: [
            { method: 'GET', path: '/api/search', description: 'Search YouTube videos' },
            { method: 'GET', path: '/api/search/music', description: 'Search music tracks' },
            { method: 'GET', path: '/api/video/info', description: 'Get video information' },
            { method: 'POST', path: '/api/download/mp3', description: 'Download as MP3' },
            { method: 'POST', path: '/api/download/music', description: 'Download music with metadata' },
            { method: 'GET', path: '/api/download/mp4', description: 'Get MP4 download links' },
            { method: 'GET', path: '/api/health', description: 'API health check' },
            { method: 'GET', path: '/api/stats', description: 'API statistics' }
        ],
        documentation: 'https://github.com/nabeels/nabeels-youtube-api',
        note: 'Use responsibly and respect YouTube Terms of Service'
    });
});

// API Routes with rate limiting
app.use('/api/search', generalLimiter);
app.use('/api/video/info', generalLimiter);
app.use('/api/download/mp3', downloadLimiter, apiKeyMiddleware);
app.use('/api/download/music', downloadLimiter, apiKeyMiddleware);

// Search endpoint
app.get('/api/search', async (req, res) => {
    try {
        const { q, limit = 20, page = 1 } = req.query;
        
        if (!q || q.trim().length < 2) {
            return res.status(400).json({
                success: false,
                message: 'Search query must be at least 2 characters long'
            });
        }

        const results = await YT.search(q, { 
            limit: Math.min(parseInt(limit), 50),
            page: parseInt(page)
        });

        res.json({
            success: true,
            query: q,
            page: parseInt(page),
            limit: results.length,
            totalResults: results.length,
            results: results.map(video => ({
                id: video.videoId,
                title: video.title,
                url: `https://youtu.be/${video.videoId}`,
                duration: video.timestamp || video.duration,
                views: video.views,
                thumbnail: video.thumbnail,
                channel: video.author,
                uploaded: video.ago
            }))
        });
    } catch (error) {
        console.error('Search error:', error);
        res.status(500).json({
            success: false,
            message: 'Search failed',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// Search music endpoint
app.get('/api/search/music', async (req, res) => {
    try {
        const { q, limit = 10 } = req.query;
        
        if (!q) {
            return res.status(400).json({
                success: false,
                message: 'Search query is required'
            });
        }

        const tracks = await YT.searchTrack(q);
        const limitedTracks = tracks.slice(0, Math.min(parseInt(limit), 20));

        res.json({
            success: true,
            query: q,
            count: limitedTracks.length,
            tracks: limitedTracks.map(track => ({
                id: track.id,
                title: track.title,
                artist: track.artist,
                album: track.album,
                duration: track.duration,
                thumbnail: track.image,
                url: track.url,
                isYtMusic: track.isYtMusic
            }))
        });
    } catch (error) {
        console.error('Music search error:', error);
        res.status(500).json({
            success: false,
            message: 'Music search failed',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// Video info endpoint
app.get('/api/video/info', async (req, res) => {
    try {
        const { url, id } = req.query;
        const videoId = url || id;
        
        if (!videoId) {
            return res.status(400).json({
                success: false,
                message: 'YouTube URL or ID is required'
            });
        }

        const info = await YT.mp4(videoId);
        
        res.json({
            success: true,
            video: {
                id: YT.getVideoID(videoId),
                title: info.title,
                description: info.description.substring(0, 500) + '...',
                duration: info.duration,
                uploadDate: info.date,
                channel: info.channel,
                thumbnail: info.thumb.url,
                viewCount: info.viewCount || 'Unknown',
                formats: [{
                    quality: info.quality,
                    contentLength: info.contentLength,
                    url: info.videoUrl
                }]
            }
        });
    } catch (error) {
        console.error('Video info error:', error);
        res.status(500).json({
            success: false,
            message: 'Failed to get video information',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// Download MP3 endpoint
app.post('/api/download/mp3', async (req, res) => {
    try {
        const { url, metadata = {}, autoWriteTags = true } = req.body;
        
        if (!url) {
            return res.status(400).json({
                success: false,
                message: 'YouTube URL is required'
            });
        }

        if (!YT.isYTUrl(url)) {
            return res.status(400).json({
                success: false,
                message: 'Invalid YouTube URL'
            });
        }

        console.log(`[${new Date().toISOString()}] MP3 download started: ${url}`);
        
        const result = await YT.mp3(url, metadata, autoWriteTags);
        
        // Generate unique filename
        const videoId = YT.getVideoID(url);
        const cleanTitle = result.meta.title.replace(/[^\w\s-]/gi, '').substring(0, 100);
        const filename = `${cleanTitle}_${videoId}_${Date.now()}.mp3`;
        const newPath = `./downloads/${filename}`;
        
        fs.renameSync(result.path, newPath);
        
        const downloadUrl = `${req.protocol}://${req.get('host')}/downloads/${filename}`;
        
        res.json({
            success: true,
            message: 'MP3 downloaded successfully',
            data: {
                id: videoId,
                title: result.meta.title,
                artist: result.meta.channel,
                duration: result.meta.seconds,
                thumbnail: result.meta.image,
                downloadUrl: downloadUrl,
                directLink: downloadUrl,
                fileSize: formatBytes(result.size),
                expiresAt: new Date(Date.now() + MAX_FILE_AGE).toISOString()
            }
        });
    } catch (error) {
        console.error('MP3 download error:', error);
        res.status(500).json({
            success: false,
            message: 'MP3 download failed',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// Download music endpoint
app.post('/api/download/music', async (req, res) => {
    try {
        const { query, trackId, quality = 'high' } = req.body;
        
        if (!query && !trackId) {
            return res.status(400).json({
                success: false,
                message: 'Query or trackId is required'
            });
        }

        console.log(`[${new Date().toISOString()}] Music download started: ${query || trackId}`);
        
        let result;
        if (trackId) {
            result = await YT.downloadMusic([{ id: trackId }]);
        } else {
            result = await YT.downloadMusic(query);
        }
        
        // Save to downloads
        const cleanTitle = result.meta.title.replace(/[^\w\s-]/gi, '').substring(0, 100);
        const filename = `${cleanTitle}_${result.meta.id}_${Date.now()}.mp3`;
        const newPath = `./downloads/${filename}`;
        
        fs.renameSync(result.path, newPath);
        
        const downloadUrl = `${req.protocol}://${req.get('host')}/downloads/${filename}`;
        
        res.json({
            success: true,
            message: 'Music downloaded with full metadata',
            data: {
                ...result.meta,
                downloadUrl: downloadUrl,
                directLink: downloadUrl,
                fileSize: formatBytes(result.size),
                expiresAt: new Date(Date.now() + MAX_FILE_AGE).toISOString(),
                hasMetadata: true,
                metadata: {
                    title: result.meta.title,
                    artist: result.meta.artist,
                    album: result.meta.album,
                    year: result.meta.year || new Date().getFullYear(),
                    coverArt: result.meta.image
                }
            }
        });
    } catch (error) {
        console.error('Music download error:', error);
        res.status(500).json({
            success: false,
            message: 'Music download failed',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// MP4 download info endpoint
app.get('/api/download/mp4', async (req, res) => {
    try {
        const { url, quality = 'best' } = req.query;
        
        if (!url) {
            return res.status(400).json({
                success: false,
                message: 'YouTube URL is required'
            });
        }

        const qualityMap = {
            'low': 134,
            'medium': 135,
            'high': 136,
            'hd': 137,
            'best': 'best'
        };

        const qualityCode = qualityMap[quality] || quality;
        const info = await YT.mp4(url, qualityCode);
        
        res.json({
            success: true,
            data: {
                title: info.title,
                thumbnail: info.thumb.url,
                duration: parseInt(info.duration),
                quality: info.quality,
                size: formatBytes(parseInt(info.contentLength || 0)),
                directLink: info.videoUrl,
                expiresAt: new Date(Date.now() + 6 * 60 * 60 * 1000).toISOString(), // 6 hours
                availableQualities: [
                    { id: 134, label: '360p', format: 'mp4' },
                    { id: 135, label: '480p', format: 'mp4' },
                    { id: 136, label: '720p', format: 'mp4' },
                    { id: 137, label: '1080p', format: 'mp4' }
                ]
            }
        });
    } catch (error) {
        console.error('MP4 info error:', error);
        res.status(500).json({
            success: false,
            message: 'Failed to get MP4 information',
            error: process.env.NODE_ENV === 'development' ? error.message : undefined
        });
    }
});

// Health check endpoint
app.get('/api/health', (req, res) => {
    const uptime = process.uptime();
    const memoryUsage = process.memoryUsage();
    
    res.json({
        success: true,
        api: API_NAME,
        version: API_VERSION,
        status: 'healthy',
        uptime: formatUptime(uptime),
        memory: {
            rss: formatBytes(memoryUsage.rss),
            heapTotal: formatBytes(memoryUsage.heapTotal),
            heapUsed: formatBytes(memoryUsage.heapUsed),
            external: formatBytes(memoryUsage.external)
        },
        timestamp: new Date().toISOString(),
        environment: process.env.NODE_ENV || 'development'
    });
});

// Stats endpoint
app.get('/api/stats', (req, res) => {
    try {
        const downloadFiles = fs.readdirSync('./downloads').length;
        const tempFiles = fs.readdirSync('./XeonMedia/audio').length;
        
        res.json({
            success: true,
            stats: {
                downloads: {
                    count: downloadFiles,
                    directory: './downloads'
                },
                tempFiles: {
                    count: tempFiles,
                    directory: './XeonMedia/audio'
                },
                server: {
                    platform: process.platform,
                    nodeVersion: process.version,
                    uptime: formatUptime(process.uptime())
                }
            },
            limits: {
                maxFileAge: '3 hours',
                rateLimit: process.env.RATE_LIMIT_MAX || 100,
                downloadLimit: process.env.DOWNLOAD_LIMIT_MAX || 10
            }
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            message: 'Failed to get statistics'
        });
    }
});

// Utility functions
function formatBytes(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);
    
    return parts.join(' ');
}

// Error handling
app.use((err, req, res, next) => {
    console.error('Global error:', err);
    res.status(500).json({
        success: false,
        message: 'Internal server error',
        requestId: req.id || Date.now().toString(36),
        timestamp: new Date().toISOString()
    });
});

// 404 handler
app.use('*', (req, res) => {
    res.status(404).json({
        success: false,
        message: 'Endpoint not found',
        availableEndpoints: [
            '/',
            '/api/search',
            '/api/search/music',
            '/api/video/info',
            '/api/download/mp3',
            '/api/download/music',
            '/api/download/mp4',
            '/api/health',
            '/api/stats'
        ]
    });
});

// Start server
app.listen(PORT, () => {
    console.log(`
    🚀 ${API_NAME} v${API_VERSION}
    👤 Author: ${API_AUTHOR}
    🔗 Contact: ${CONTACT}
    
    📡 Server running on port ${PORT}
    🌐 Local: http://localhost:${PORT}
    🌐 Network: http://0.0.0.0:${PORT}
    
    📚 API Documentation:
    - Base URL: http://localhost:${PORT}
    - Health Check: http://localhost:${PORT}/api/health
    - Search: http://localhost:${PORT}/api/search?q=query
    
    ⚠️  Note: This API is for educational purposes only.
    ⚠️  Respect YouTube's Terms of Service.
    `);
});

// File cleanup scheduler (important for Render's ephemeral storage)
setInterval(() => {
    cleanupDirectory('./downloads', MAX_FILE_AGE);
    cleanupDirectory('./XeonMedia/audio', 1 * 60 * 60 * 1000); // 1 hour for temp files
    console.log(`[${new Date().toISOString()}] Cleanup completed`);
}, 30 * 60 * 1000); // Run every 30 minutes

function cleanupDirectory(directory, maxAge) {
    if (!fs.existsSync(directory)) return;
    
    const now = Date.now();
    const files = fs.readdirSync(directory);
    let cleaned = 0;
    
    files.forEach(file => {
        const filePath = path.join(directory, file);
        try {
            const stats = fs.statSync(filePath);
            if (now - stats.mtime.getTime() > maxAge) {
                fs.unlinkSync(filePath);
                cleaned++;
            }
        } catch (err) {
            console.error(`Failed to clean up ${filePath}:`, err.message);
        }
    });
    
    if (cleaned > 0) {
        console.log(`Cleaned up ${cleaned} old files from ${directory}`);
    }
}
