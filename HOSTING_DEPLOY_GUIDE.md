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

## 🎮 Option 4: Nexcloud / Pterodactyl Panel (Discord Bot Hosting)
Yeh guide **Nexcloud Hosting** aur sabhi Pterodactyl panels ke liye hai:

1. **Panel Login**: Nexcloud / Pterodactyl hosting panel par login karein.
2. **Server Create / Egg**: **Python 3.10 ya Python 3.11** egg select karein (jisme FFmpeg available ho).
3. **Files Upload**:
   - Repository ki saari files (ya `bot.zip`) upload karke extract karein.
4. **Environment Variables (.env)**:
   - Panel ke **File Manager** mein `.env` file banayein aur apna `DISCORD_BOT_TOKEN`, `OWNER_ID`, etc. paste karein.
   - Bot mein **Multi-Tier Audio Engine** laga hua hai (JioSaavn 320kbps CD Lossless + Multi-Client YouTube Android/iOS + SoundCloud), jo cloud datacenter par YouTube IP block nahi hone deta aur Spotify ke sabhi gane seamlessly play karta hai!
5. **(Optional) Public Lavalink Setup**:
   - Agar aap external Public Lavalink node use karna chahein, toh `.env` mein yeh add kar sakte hain:
     ```env
     LAVALINK_HOST=lava-v4.ajieblogs.eu.org
     LAVALINK_PORT=443
     LAVALINK_PASSWORD=https://dsc.gg/ajidevserver
     LAVALINK_SECURE=true
     ```
6. **Startup Command**:
   - `python bot.py`
7. **Console**: Server ko **Start** karein. Console mein `CrownX Bot is online!` aate hi bot ready ho jayega.

---

## 🔑 Required Environment Variables
| Variable | Description |
|---|---|
| `DISCORD_BOT_TOKEN` | Discord Developer Portal se Bot Token |
| `OWNER_ID` | Owner ka Discord ID |
| `DEFAULT_PREFIX` | Bot Prefix (e.g. `!`) |
| `GEMINI_API_KEY` | Gemini AI Key (Optional) |
| `LAVALINK_HOST` | Lavalink Host (Optional, default: 127.0.0.1 ya Public Node) |
| `LAVALINK_PORT` | Lavalink Port (Optional, default: 2333 ya 443) |
| `LAVALINK_PASSWORD` | Lavalink Password |
| `LAVALINK_SECURE` | true / false |
