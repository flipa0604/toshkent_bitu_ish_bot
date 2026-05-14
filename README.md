# Toshkent BITU Ish Bot

Telegram orqali ishga nomzodlardan avtomatik anketa yig'adigan bot. Nomzod botga `/start` bossa, bosqichma-bosqich savollarga javob beradi, ovoz va video xabar yuboradi. Barcha javoblar avtomatik ravishda **SQLite bazaga**, **Google Sheets jadvaliga** va **HR chatga** yetkaziladi.

## Imkoniyatlari

- 24 ta savoldan iborat to'liq anketa (FSM asosida)
- Shaxsiy ma'lumotlar, ish tajribasi, refleksiya va tibbiyot bloki
- Ovozli va video xabar qabul qilish
- Telefon raqamini tugma orqali yoki qo'lda kiritish
- Sana va telefon validatsiyasi
- Ikki til: o'zbek va rus (`.env` orqali sozlanadi)
- SQLite bazaga zaxira yozish
- Google Sheets jadvaliga avtomatik eksport (fayl URL'lari bilan)
- HR chatga formatlangan xulosa + media fayllar
- Polling va Webhook rejimlari

## Texnologiyalar

- Python 3.10+
- aiogram 3.22 (Telegram Bot API)
- SQLite (lokal saqlash)
- Google Sheets API (gspread)
- aiohttp (webhook server)

## O'rnatish

### 1. Repositoriyni klonlash

```bash
git clone https://github.com/flipa0604/toshkent_bitu_ish_bot.git
cd toshkent_bitu_ish_bot
```

### 2. Virtual muhit yaratish

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**
```powershell
python -m venv venv
venv\Scripts\activate
```

### 3. Kutubxonalarni o'rnatish

```bash
pip install -r requirements.txt
```

### 4. Konfiguratsiya

`.env.example` faylini `.env` deb nusxalang va o'z qiymatlaringiz bilan to'ldiring:

```bash
cp .env.example .env
```

Keyin `.env` faylini tahrirlang:
- `TELEGRAM_API_TOKEN` — [@BotFather](https://t.me/BotFather)'dan oling
- `HR_CHAT_ID` — botni HR guruhga qo'shing, `/here` buyrug'i bilan ID ni oling
- `GSHEET_SPREADSHEET_ID` — Google Sheets jadval URL'idan
- `GOOGLE_SERVICE_ACCOUNT_JSON` — Google Cloud Console'da service account yaratib, JSON kalitini yuklab oling

### 5. Google Sheets'ni sozlash

1. [Google Cloud Console](https://console.cloud.google.com/)'da yangi loyiha yarating
2. **Google Sheets API** va **Google Drive API** ni yoqing
3. **Service Account** yarating va JSON kalitini yuklab oling
4. Yuklangan JSON faylni loyiha papkasiga `service_account.json` nomi bilan qo'ying
5. Service account email'iga (JSON ichidagi `client_email`) Google Sheets jadvalga **Editor** huquqini bering

### 6. Ishga tushirish

```bash
python hr_bot.py
```

## Ubuntu serverda doimiy ishlash uchun

`systemd` xizmati yarating: `/etc/systemd/system/hr-bot.service`

```ini
[Unit]
Description=Toshkent BITU HR Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/toshkent_bitu_ish_bot
Environment="PATH=/opt/toshkent_bitu_ish_bot/venv/bin"
ExecStart=/opt/toshkent_bitu_ish_bot/venv/bin/python hr_bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Keyin:

```bash
sudo systemctl daemon-reload
sudo systemctl enable hr-bot
sudo systemctl start hr-bot
sudo systemctl status hr-bot
```

## Loyiha tuzilishi

```
toshkent_bitu_ish_bot/
├── hr_bot.py              # Asosiy bot kodi
├── requirements.txt       # Python kutubxonalari
├── .env.example           # Konfiguratsiya namunasi
├── .gitignore
├── README.md
├── ask_voice.ogg          # Ovozli savol namunasi
├── ask_video.mp4          # Video savol namunasi
├── starter_note.mp4       # /start bosilgandagi tanishtiruv videosi
└── data/                  # SQLite bazaga avtomatik yaratiladi
    └── hr.db
```

## Bot buyruqlari

- `/start` — anketani boshlash
- `/cancel` — anketani bekor qilish
- `/here` — joriy chat ID ni ko'rsatish (HR_CHAT_ID ni topish uchun)

## Litsenziya

Ichki foydalanish uchun.
