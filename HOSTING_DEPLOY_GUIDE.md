# 🚀 Bot Hosting & Deployment Guide (Hosting Setup)

Yeh bot **100% Cloud-Ready & Hosting-Optimized** bana diya gaya hai.

---

## 📋 Features & Fixes Included
1. **Multi-Source Audio Engine (320kbps CD Quality)**:
   - Saavn CDN Lossless Stream Engine (Cloud Hosting par kabhi ban/block nahi hota).
   - YouTube link oEmbed/OpenGraph HTML Resolver (Cloud IP Block bypass).
   - Multi-Client yt-dlp + SoundCloud High Quality Fallback.
2. **Nayumi Voice AI Chat Removed**:
   - Voice channel mein AI chat / voice listening ko completely disable kar diya gaya hai.
   - Sabhi Voice Music commands (`play`, `pause`, `skip`, `volume`, `loop`, `stop`, `queue`) bilkul smoothly kaam karte hain.
3. **Cloud Single Instance & Cross-Platform Support**:
   - Render, Railway, VPS, Docker, Linux par restart hone par socket lock crash nahi hoga.

---

## 🌐 Option 1: Render.com (Recommended - 100% Free / Easy)

### Steps:
1. Apne code ko GitHub repository par upload (push) karein.
2. [Render Dashboard](https://dashboard.render.com/) par jayein -> **New +** -> **Background Worker** (ya **Web Service**).
3. Apni GitHub repository select karein.
4. Settings mein:
   - **Environment**: `Docker` (Dockerfile automatically FFmpeg aur Java setup karega)
   - Ya agar **Python** select karein:
     - **Build Command**: `pip install -r requirements.txt`
     - **Start Command**: `python bot.py`
5. **Environment Variables (Advanced -> Add Environment Variable)**:
   - `DISCORD_BOT_TOKEN`: *Apna Discord Bot Token*
   - `OWNER_ID`: *Apna Discord User ID*
   - `DEFAULT_PREFIX`: `!`
   - (Baki keys `.env.example` se copy kar sakte hain)
6. **Deploy** par click karein. Bot 24/7 online ho jayega!

---

## 🚂 Option 2: Railway.app (Fastest 1-Click Deploy)

1. [Railway.app](https://railway.app/) par login karein.
2. **New Project** -> **Deploy from GitHub repo**.
3. Railway automatically `Dockerfile` detect kar lega aur FFmpeg ke saath container build kar dega.
4. **Variables** tab mein jakar `DISCORD_BOT_TOKEN` aur `.env` ke variables add karein.
5. Deploy complete hote hi bot Discord par online show karega.

---

## 📦 Option 3: VPS / Ubuntu Server / Linux (Dedicated)

```bash
# 1. Update system & install dependencies
sudo apt update && sudo apt install -y python3 python3-pip python3-venv ffmpeg libopus-dev openjdk-17-jre-headless git

# 2. Clone repo & navigate
git clone <YOUR_REPO_URL>
cd <REPO_FOLDER>

# 3. Create virtualenv
python3 -m venv venv
source venv/bin/activate

# 4. Install requirements
pip install -r requirements.txt

# 5. Setup .env
cp .env.example .env
nano .env  # Add your Bot Token

# 6. Run with PM2 (24/7 Background Process)
sudo npm install -g pm2
pm2 start bot.py --name "crownx-bot" --interpreter python3
pm2 save
pm2 startup
```

---

## 🎮 Option 4: Pterodactyl / Bot Hosting Panel (Discord Bot Hosting)

1. Panel par **Python** egg select karein (Python 3.10 ya 3.11).
2. Files tab mein saari files upload karein.
3. `.env` file create karein aur `DISCORD_BOT_TOKEN` paste karein.
4. **Startup Command**: `python bot.py`
5. Server **Start** karein.

---

## 🔑 Required Environment Variables
| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Discord Developer Portal se Bot Token |
| `OWNER_ID` | Owner ka Discord ID |
| `DEFAULT_PREFIX` | Bot Prefix (e.g. `!`) |
| `GEMINI_API_KEY` | Gemini AI Key (Optional) |
