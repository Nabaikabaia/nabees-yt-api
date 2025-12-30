# 🎵 Nãbēēs YouTube API

A powerful REST API for downloading YouTube videos and music as MP3/MP4 with full metadata support. Deploy instantly on Render.

## ✨ Features

- 🔍 Search YouTube videos and music
- 🎵 Download as MP3 with ID3 tags (artist, album, cover art)
- 📹 Download as MP4 in multiple qualities
- 📊 Get video information and metadata
- 🛡️ Rate limiting and security features
- 🔄 Automatic file cleanup
- 🏷️ Full metadata support for music

## 🚀 Quick Deploy on Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/nabeels/nabeels-youtube-api)

### Manual Deployment:

1. **Fork this repository**
2. **Create a new Web Service on Render**
3. **Connect your GitHub repository**
4. **Configure settings:**
   - Build Command: `npm install && npm run setup`
   - Start Command: `npm start`
   - Environment Variables (optional):
     - `API_KEY`: Your secret API key
     - `API_KEY_REQUIRED`: Set to "true" to enable API key authentication
     - `ALLOWED_ORIGINS`: Comma-separated list of allowed origins
5. **Click "Create Web Service"**

## 📚 API Documentation

### Base URL
