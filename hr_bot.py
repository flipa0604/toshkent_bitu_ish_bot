from __future__ import annotations
import asyncio
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ChatAction
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile,
)
from dotenv import load_dotenv

# --- Google Sheets ---
# pip install gspread google-auth
import gspread
from google.oauth2.service_account import Credentials

# ====== CONFIG ======
load_dotenv()
TOKEN = os.getenv("TELEGRAM_API_TOKEN")
HR_CHAT_ID = int(os.getenv("HR_CHAT_ID", "0"))  # 0 = не отправлять
RUN_MODE = os.getenv("RUN_MODE", "POLLING").upper()  # POLLING | WEBHOOK

# Язык интерфейса: 'uz' или 'ru'
LANG = os.getenv("LANG", "uz").lower()
if LANG not in {"uz", "ru"}:
    LANG = "uz"

# Файлы медиа-подсказок (можно задать в .env)
ASK_VOICE_PATH = os.getenv("ASK_VOICE_PATH", "ask_voice.ogg")            # OGG/Opus
ASK_VIDEO_NOTE_PATH = os.getenv("ASK_VIDEO_NOTE_PATH", "ask_video.mp4")  # квадратное mp4 (кружок)

# Google Sheets env
GSHEETS_ENABLE = os.getenv("GSHEETS_ENABLE", "1") == "1"
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "service_account.json")
GSHEET_SPREADSHEET_ID = os.getenv("GSHEET_SPREADSHEET_ID", "")
GSHEET_WORKSHEET_NAME = os.getenv("GSHEET_WORKSHEET_NAME", "Applications")

if not TOKEN:
    raise RuntimeError("TELEGRAM_API_TOKEN is missing in .env")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ====== I18N ======
T = {
    "uz": {
        "hello": "<b>Assalomu alaykum!</b>\nBu HR-anketa.\n\nQaysi yo'nalish bo'yicha ishga kirmoqchisiz?",
        "ask_full_name": "Iltimos, <b>FISH</b> (Ism Familiya) yozing.",
        "need_full_name": "Iltimos, kamida Ism va Familiyani kiriting.",
        "ask_phone": "Telefon raqamingizni yuboring",
        "share_phone": "Raqamni ulashish",
        "phone_bad": "Raqam noto'g'ri ko'rinadi. \"Raqamni ulashish\" tugmasini bosing yoki +998XXXXXXXXX formatida kiriting.",
        "ask_birth": "Tug'ilgan sanangizni <b>DD.MM.YYYY</b> formatida yuboring (masalan, 12.06.2000).",
        "birth_bad": "Sana formati noto'g'ri. Misol: 12.06.2000",
        "ask_edu": "Ma'lumotingizni tanlang:",
        "edu_oliy": "Oliy",
        "edu_orta": "O'rta",
        "edu_orta_maxsus": "O'rta-maxsus",
        "ask_study_place": "Qayerda o'qigansiz? (muassasa nomi)",
        "ask_prev_dir": "Oldin qaysi yo'nalishda ishlagansiz?",
        "ask_family": "Oilangiz bormi (turmush o'rtog'i, farzandlar va h.k.)? Qisqacha yozing.",

        "ask_voice": "Iltimos, <b>ovozli xabar</b> (voice) yuboring va o'zingizni qisqacha tanishtiring.",
        "need_voice": "Aynan ovozli xabar kerak (mikrofon belgisi). Iltimos, yana yuboring.",

        # Убрали вопрос о языках (qaysi tillarni bilasiz)
        # "ask_langs": ...

        "ask_video": "Iltimos, o'zingiz haqingizda <b>video xabar</b> yuboring (video note yoki oddiy video).",
        "need_video": "Video xabar (dumaloq yoki oddiy video) yuborish kerak. Iltimos, qayta yuboring.",

        "ask_ref": "Oxirgi ish joyingizda siz haqingizda so'rasak bo'ladimi?",
        # Убрали: oxirgi ish joyida kim sizga taklif bergan
        # "ask_referrer": ...
        "ask_prob": "Qancha <b>sinov muddati</b> bilan bizda ishlashni xohlaysiz? (masalan: 1 oy)",
        "ask_overtime": "Ish kuni tugagandan keyin ishlash imkoniyatingiz bormi?",
        "ask_health": "Iltimos, sog'lig'ingiz haqida yozing (cheklovlar/qarshi ko'rsatmalar bo'lsa).",

        # Refleksiya savollari
        "ask_why_late": "Nega ba'zi odamlar ishga kechikadi? Fikringiz:",
        "ask_why_steal": "Nega ba'zi odamlar ish joyida o‘g‘irlik qiladi? Fikringiz:",
        "ask_why_perf": "Nega ba'zi xodimlar yaxshi, ba'zilari yomon ishlaydi? Bunga sabab nima?",
        "ask_last_salary": "Oxirgi ish joyingizda oyligingiz qancha edi? (so'mda yoki valyutada yozing)",
        "ask_desired_salary": "Bizning kompaniyada qancha maosh olishni xohlaysiz?",
        # Убрали: kurslar

        # Yangi tibbiyot-blok
        "ask_med_inst": "Qaysi tibbiyot muassasani tamomlagansiz va qaysi yil?",
        "ask_years_exp": "Necha yillik ish tajribangiz bor?",
        "ask_where_duration": "Qayerlarda va qancha muddat ishlagansiz? (joylar + muddatlar)",
        "ask_current_job": "Hozirda qayerda va qaysi lavozimda ishlaysiz?",
        "ask_med_opinion": "Sizningcha, tibbiyot xodimi qanday bo‘lishi kerak?",

        "thanks": "Rahmat! Anketangiz qabul qilindi. HR ko'rib chiqadi va siz bilan bog'lanadi.\n\n/start — qayta boshlash",
        "here": "chat_id: <code>{chat_id}</code>",
        "cancel": "Anketa bekor qilindi. Qayta o'tish uchun /start yozing.",
        "send_fail": "⚠️ HR chatga yuborib bo'lmadi. Bot qo'shilgan/adminga aylantirilganini va HR_CHAT_ID to'g'ri ekanini tekshiring.",

        "direction_categories": {
            "Rahbariyat": ["Tyutor", "Texnik xodim", "Rahbarlik", "O'quv bo'limi", "Boshqa"],
            "O'qituvchi": ["Umumta'lim Fanlar", "Klinik oldi Fanlar", "Klinik Fanlar"],
        },
        "ask_sub_direction": "<b>{cat}</b> bo'limidan qaysi yo'nalish?",
        "back": "◀ Orqaga",
        "yes": "Ha",
        "no": "Yo'q",

        "summary_title": "<b>Yangi anketa #{id}</b>",
        "summary_time": "Vaqt: <code>{time}</code>",
        "summary_user": "Foydalanuvchi: <a href='tg://user?id={uid}'>#{uid}</a> @{uname}",
        "summary_dir": "Yo'nalish: {v}",
        "summary_fio": "FISH: {v}",
        "summary_phone": "Telefon: {v}",
        "summary_birth": "Tug'ilgan sana: {v}",
        "summary_edu": "Ma'lumoti: {v}",
        "summary_study": "O'qigan joyi: {v}",
        "summary_prev": "Oldingi yo'nalish: {v}",
        "summary_family": "Oila: {v}",
        # removed languages
        "summary_ref": "Tavsiyalarni tekshirishga rozilik: {v}",
        # removed last_job_referrer
        "summary_prob": "Sinov muddati: {v}",
        "summary_overtime": "Ishdan keyin ishlash: {v}",
        "summary_health": "Salomatlik: {v}",
        "summary_why_late": "Nega kechikishadi: {v}",
        "summary_why_steal": "Nega o‘g‘irlik qilishadi: {v}",
        "summary_why_perf": "Yaxshi/yomon ishlash sababi: {v}",
        "summary_last_salary": "Oxirgi oylik: {v}",
        "summary_desired_salary": "Kutilayotgan oylik: {v}",
        # new medical summaries
        "summary_med_inst": "Tibbiyot muassasasi (yil): {v}",
        "summary_years_exp": "Tajriba (yil): {v}",
        "summary_where_duration": "Ish joylari va muddatlar: {v}",
        "summary_current_job": "Hozirgi ish va lavozim: {v}",
        "summary_med_opinion": "Tibbiyot xodimi qanday bo‘lishi kerak: {v}",

        "voice_caption": "Nomzod ovozi #{id}",
        "video_caption": "Nomzod videosi #{id}",
        "starter_hint": "(Eslatma: starter_note.mp4 faylini skript yoniga qo'ying — dumaloq video jo'natiladi)",
    },
    "ru": {
        "hello": "<b>Здравствуйте!</b>\nЭто HR-анкета.\n\nНа какое направление вы хотите зайти на эту работу?",
        "ask_full_name": "Пожалуйста, укажите ваше <b>ФИО</b> (Имя Фамилия).",
        "need_full_name": "Пожалуйста, укажите как минимум Имя и Фамилию.",
        "ask_phone": "Отправьте ваш номер телефона",
        "share_phone": "Поделиться номером",
        "phone_bad": "Номер выглядит некорректно. Нажмите \"Поделиться номером\" или введите вручную в формате +998XXXXXXXXX.",
        "ask_birth": "Укажите дату рождения в формате <b>DD.MM.YYYY</b> (например, 12.06.2000).",
        "birth_bad": "Формат даты неверный. Пример: 12.06.2000",
        "ask_edu": "Выберите ваше образование:",
        "edu_oliy": "Oliy (Высшее)",
        "edu_orta": "O'rta (Среднее)",
        "edu_orta_maxsus": "O'rta-maxsus (Среднее-специальное)",
        "ask_study_place": "Где вы учились? (название учебного заведения)",
        "ask_prev_dir": "На каком направлении вы раньше работали?",
        "ask_family": "Есть ли у вас семья (супруг/супруга, дети и т.д.)? Кратко опишите.",

        "ask_voice": "Отправьте, пожалуйста, <b>голосовое сообщение</b> (voice) с кратким представлением.",
        "need_voice": "Нужно именно голосовое сообщение (иконка микрофона). Попробуйте ещё раз, пожалуйста.",

        # removed languages

        "ask_video": "Отправьте, пожалуйста, <b>видео-сообщение</b> о себе (video note или обычное видео).",
        "need_video": "Нужно отправить видео-сообщение (кружочек или обычное видео). Попробуйте ещё раз.",

        "ask_ref": "Можно ли спросить о вас в последнем месте, где вы работали?",
        # removed last_job_referrer
        "ask_prob": "Какой <b>испытательный срок</b> вы хотите у нас? (например: 1 месяц)",
        "ask_overtime": "Есть ли у вас возможность работать <b>после окончания рабочего дня</b>?",
        "ask_health": "Расскажите, пожалуйста, о вашем <b>здоровье</b> (есть ли ограничения/противопоказания?).",

        # Рефлексия
        "ask_why_late": "Почему некоторые люди опаздывают на работу? Ваше мнение:",
        "ask_why_steal": "Почему некоторые люди воруют на работе? Ваше мнение:",
        "ask_why_perf": "Почему одни сотрудники работают хорошо, а другие плохо? В чём причина?",
        "ask_last_salary": "Сколько вы зарабатывали на прошлой работе? (укажите валюту)",
        "ask_desired_salary": "Сколько хотите зарабатывать в нашей компании?",

        # Медицинский блок
        "ask_med_inst": "Какое мед. учреждение вы окончили и в каком году?",
        "ask_years_exp": "Сколько у вас лет рабочего стажа?",
        "ask_where_duration": "Где и сколько времени вы работали? (места + сроки)",
        "ask_current_job": "Где и в какой должности вы работаете сейчас?",
        "ask_med_opinion": "Каким, на ваш взгляд, должен быть медработник?",

        "thanks": "Спасибо! Ваша анкета принята. HR свяжется с вами после рассмотрения.\n\n/start — начать заново",
        "here": "chat_id: <code>{chat_id}</code>",
        "cancel": "Анкета сброшена. Наберите /start, чтобы пройти заново.",
        "send_fail": "⚠️ Не удалось отправить анкету в HR-чат. Проверьте, что бот добавлен/админ и HR_CHAT_ID верный.",

        "direction_categories": {
            "Rahbariyat": ["Tyutor", "Texnik xodim", "Rahbarlik", "O'quv bo'limi", "Boshqa"],
            "O'qituvchi": ["Umumta'lim Fanlar", "Klinik oldi Fanlar", "Klinik Fanlar"],
        },
        "ask_sub_direction": "<b>{cat}</b> — какое направление?",
        "back": "◀ Назад",
        "yes": "Да",
        "no": "Нет",

        "summary_title": "<b>Новая анкета #{id}</b>",
        "summary_time": "Время: <code>{time}</code>",
        "summary_user": "Пользователь: <a href='tg://user?id={uid}'>#{uid}</a> @{uname}",
        "summary_dir": "Направление: {v}",
        "summary_fio": "ФИО: {v}",
        "summary_phone": "Телефон: {v}",
        "summary_birth": "Дата рождения: {v}",
        "summary_edu": "Образование: {v}",
        "summary_study": "Где учился: {v}",
        "summary_prev": "Пред. направление: {v}",
        "summary_family": "Семья: {v}",
        # removed languages and last_job_referrer
        "summary_ref": "Согласие на проверку: {v}",
        "summary_prob": "Испытательный срок: {v}",
        "summary_overtime": "Работа после дня: {v}",
        "summary_health": "Здоровье: {v}",
        "summary_why_late": "Почему опаздывают: {v}",
        "summary_why_steal": "Почему воруют: {v}",
        "summary_why_perf": "Причины хорошей/плохой работы: {v}",
        "summary_last_salary": "Прошлый доход: {v}",
        "summary_desired_salary": "Ожидаемый доход: {v}",
        # new medical summaries
        "summary_med_inst": "Мед. учреждение (год): {v}",
        "summary_years_exp": "Стаж (лет): {v}",
        "summary_where_duration": "Места работы и сроки: {v}",
        "summary_current_job": "Текущая работа и должность: {v}",
        "summary_med_opinion": "Каковым должен быть медработник: {v}",

        "voice_caption": "Голос кандидата #{id}",
        "video_caption": "Видео кандидата #{id}",
        "starter_hint": "(Подсказка: положите starter_note.mp4 рядом со скриптом, чтобы отправлять кружочек-видео)",
    },
}

def t(key: str, **kwargs) -> str:
    return T[LANG][key].format(**kwargs)

# ====== DB ======
DB_PATH = os.path.join("data", "hr.db")
os.makedirs("data", exist_ok=True)
with sqlite3.connect(DB_PATH) as conn:
    cur = conn.cursor()
    # создаём таблицу (колонки старые + новые)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            created_at TEXT,
            direction TEXT,
            full_name TEXT,
            phone TEXT,
            birth_date TEXT,
            education TEXT,
            study_place TEXT,
            prev_direction TEXT,
            family TEXT,
            voice_file_id TEXT,
            languages TEXT,
            self_video_file_id TEXT,
            ref_check_consent TEXT,
            last_job_referrer TEXT,
            probation TEXT,
            after_hours TEXT,
            health TEXT,
            late_opinion TEXT,
            theft_opinion TEXT,
            performance_opinion TEXT,
            last_salary TEXT,
            desired_salary TEXT,
            courses TEXT,
            med_institution_year TEXT,
            years_experience TEXT,
            where_duration TEXT,
            current_job TEXT,
            med_worker_opinion TEXT
        )
        """
    )
    # миграция: добавляем новые колонки, если их нет
    cur.execute("PRAGMA table_info(applications)")
    existing_cols = {row[1] for row in cur.fetchall()}
    new_cols = [
        ("late_opinion", "TEXT"),
        ("theft_opinion", "TEXT"),
        ("performance_opinion", "TEXT"),
        ("last_salary", "TEXT"),
        ("desired_salary", "TEXT"),
        ("courses", "TEXT"),
        ("med_institution_year", "TEXT"),
        ("years_experience", "TEXT"),
        ("where_duration", "TEXT"),
        ("current_job", "TEXT"),
        ("med_worker_opinion", "TEXT"),
    ]
    for col, coltype in new_cols:
        if col not in existing_cols:
            cur.execute(f"ALTER TABLE applications ADD COLUMN {col} {coltype}")
    conn.commit()

# ====== MODELS ======
class YesNo(str, Enum):
    YES = "yes"
    NO = "no"

@dataclass
class Application:
    user_id: int
    username: Optional[str]
    created_at: str
    direction: Optional[str] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    birth_date: Optional[str] = None
    education: Optional[str] = None
    study_place: Optional[str] = None
    prev_direction: Optional[str] = None
    family: Optional[str] = None
    voice_file_id: Optional[str] = None
    languages: Optional[str] = None  # оставлено для совместимости, не спрашиваем
    self_video_file_id: Optional[str] = None
    ref_check_consent: Optional[str] = None
    last_job_referrer: Optional[str] = None  # оставлено, не спрашиваем
    probation: Optional[str] = None
    after_hours: Optional[str] = None
    health: Optional[str] = None
    # новые/старые поля
    late_opinion: Optional[str] = None
    theft_opinion: Optional[str] = None
    performance_opinion: Optional[str] = None
    last_salary: Optional[str] = None
    desired_salary: Optional[str] = None
    courses: Optional[str] = None  # оставлено, не спрашиваем
    # тмб блок
    med_institution_year: Optional[str] = None
    years_experience: Optional[str] = None
    where_duration: Optional[str] = None
    current_job: Optional[str] = None
    med_worker_opinion: Optional[str] = None
    # ссылки на файлы
    voice_url: Optional[str] = None
    video_url: Optional[str] = None

# ====== FSM ======
class HRForm(StatesGroup):
    DIRECTION = State()
    FULL_NAME = State()
    PHONE = State()
    BIRTHDATE = State()
    EDUCATION = State()
    STUDY_PLACE = State()
    PREV_DIRECTION = State()
    FAMILY = State()
    VOICE = State()
    # LANGUAGES removed
    SELF_VIDEO = State()
    REF_CONSENT = State()
    # LAST_JOB_REFERRER removed
    PROBATION = State()
    AFTER_HOURS = State()
    HEALTH = State()
    # refleksiya
    WHY_LATE = State()
    WHY_STEAL = State()
    WHY_PERF = State()
    LAST_SALARY = State()
    DESIRED_SALARY = State()
    # COURSES removed
    # medical block
    MED_INST = State()
    YEARS_EXP = State()
    WHERE_DURATION = State()
    CURRENT_JOB = State()
    MED_OPINION = State()
    DONE = State()

# ====== KEYBOARDS ======

def _chunk2(items):
    return [items[i:i+2] for i in range(0, len(items), 2)]

def kbd_directions() -> InlineKeyboardMarkup:
    cats = list(T[LANG]["direction_categories"].keys())
    rows = []
    for pair in _chunk2(cats):
        rows.append([InlineKeyboardButton(text=c, callback_data=f"cat:{c}") for c in pair])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kbd_subdirections(category: str) -> InlineKeyboardMarkup:
    subs = T[LANG]["direction_categories"].get(category, [])
    rows = []
    for pair in _chunk2(subs):
        rows.append([InlineKeyboardButton(text=s, callback_data=f"dir:{category}|{s}") for s in pair])
    rows.append([InlineKeyboardButton(text=T[LANG]["back"], callback_data="cat_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kbd_edu() -> InlineKeyboardMarkup:
    keys = ["edu_oliy", "edu_orta", "edu_orta_maxsus"]
    rows = [[InlineKeyboardButton(text=T[LANG][k], callback_data=f"edu:{T[LANG][k]}")] for k in keys]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kbd_yesno(prefix: str = "yn") -> InlineKeyboardMarkup:
    rows = [[
        InlineKeyboardButton(text=T[LANG]["yes"], callback_data=f"{prefix}:{YesNo.YES.value}"),
        InlineKeyboardButton(text=T[LANG]["no"], callback_data=f"{prefix}:{YesNo.NO.value}"),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kbd_share_contact() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=T[LANG]["share_phone"], request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
    )

# ====== HELPERS ======

def valid_date_ddmmyyyy(text: str) -> bool:
    try:
        datetime.strptime(text, "%d.%m.%Y")
        return True
    except ValueError:
        return False

def clean_phone(text: str) -> str:
    return re.sub(r"[^0-9+]+", "", text or "")

# --- Google Sheets helpers ---
GS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _get_worksheet():
    if not GSHEETS_ENABLE:
        return None
    if not GSHEET_SPREADSHEET_ID or not GOOGLE_SERVICE_ACCOUNT_JSON:
        print("GSHEETS disabled: missing GSHEET_SPREADSHEET_ID or GOOGLE_SERVICE_ACCOUNT_JSON")
        return None
    creds = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_JSON, scopes=GS_SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GSHEET_SPREADSHEET_ID)
    try:
        ws = sh.worksheet(GSHEET_WORKSHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=GSHEET_WORKSHEET_NAME, rows=1, cols=60)
    return ws

# Обновлённые заголовки (без Languages/LastJobReferrer/Courses, с мед-блоком)
GS_HEADERS: List[str] = [
    "ID", "CreatedAt", "UserID", "Username",
    "Direction", "FullName", "Phone", "BirthDate", "Education", "StudyPlace",
    "PrevDirection", "Family",
    "RefConsent", "Probation", "AfterHours", "Health",
    "WhyLate", "WhySteal", "WhyPerf",
    "LastSalary", "DesiredSalary",
    "MedInstitutionYear", "YearsExperience", "WhereDuration", "CurrentJob", "MedWorkerOpinion",
    "VoiceFileID", "VideoFileID", "VoiceURL", "VideoURL",
]

def _ensure_headers(ws):
    try:
        values = ws.get_all_values()
        if not values:
            ws.append_row(GS_HEADERS, value_input_option="USER_ENTERED")
        else:
            first = values[0] if values else []
            if not first or (len(first) > 0 and first[0] != "ID"):
                ws.insert_row(GS_HEADERS, index=1, value_input_option="USER_ENTERED")
    except Exception as e:
        print("ensure_headers failed:", e)

import traceback

def _append_to_sheet_sync(app: Application, record_id: int):
    ws = _get_worksheet()
    if not ws:
        return
    _ensure_headers(ws)
    row = [
        record_id,
        app.created_at,
        app.user_id,
        app.username or "",
        app.direction or "",
        app.full_name or "",
        app.phone or "",
        app.birth_date or "",
        app.education or "",
        app.study_place or "",
        app.prev_direction or "",
        app.family or "",
        app.ref_check_consent or "",
        app.probation or "",
        app.after_hours or "",
        app.health or "",
        app.late_opinion or "",
        app.theft_opinion or "",
        app.performance_opinion or "",
        app.last_salary or "",
        app.desired_salary or "",
        app.med_institution_year or "",
        app.years_experience or "",
        app.where_duration or "",
        app.current_job or "",
        app.med_worker_opinion or "",
        app.voice_file_id or "",
        app.self_video_file_id or "",
        app.voice_url or "",
        app.video_url or "",
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")

async def append_to_sheet(app: Application, record_id: int):
    try:
        await asyncio.to_thread(_append_to_sheet_sync, app, record_id)
    except Exception as e:
        print("append_to_sheet failed:", e)
        traceback.print_exc()


def save_application(app: Application) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO applications (
                user_id, username, created_at, direction, full_name, phone, birth_date,
                education, study_place, prev_direction, family, voice_file_id, languages,
                self_video_file_id, ref_check_consent, last_job_referrer, probation, after_hours, health,
                late_opinion, theft_opinion, performance_opinion, last_salary, desired_salary, courses,
                med_institution_year, years_experience, where_duration, current_job, med_worker_opinion
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                app.user_id, app.username, app.created_at, app.direction, app.full_name, app.phone,
                app.birth_date, app.education, app.study_place, app.prev_direction, app.family,
                app.voice_file_id, app.languages, app.self_video_file_id, app.ref_check_consent,
                app.last_job_referrer, app.probation, app.after_hours, app.health,
                app.late_opinion, app.theft_opinion, app.performance_opinion,
                app.last_salary, app.desired_salary, app.courses,
                app.med_institution_year, app.years_experience, app.where_duration,
                app.current_job, app.med_worker_opinion,
            ),
        )
        conn.commit()
        return cur.lastrowid


def fmt_summary(app: Application, record_id: int) -> str:
    uname = app.username or "-"
    lines = [
        t("summary_title", id=record_id),
        t("summary_time", time=app.created_at),
        t("summary_user", uid=app.user_id, uname=uname),
        t("summary_dir", v=app.direction),
        t("summary_fio", v=app.full_name),
        t("summary_phone", v=app.phone),
        t("summary_birth", v=app.birth_date),
        t("summary_edu", v=app.education),
        t("summary_study", v=app.study_place),
        t("summary_prev", v=app.prev_direction),
        t("summary_family", v=app.family),
        t("summary_ref", v=app.ref_check_consent),
        t("summary_prob", v=app.probation),
        t("summary_overtime", v=app.after_hours),
        t("summary_health", v=app.health),
        t("summary_why_late", v=app.late_opinion),
        t("summary_why_steal", v=app.theft_opinion),
        t("summary_why_perf", v=app.performance_opinion),
        t("summary_last_salary", v=app.last_salary),
        t("summary_desired_salary", v=app.desired_salary),
        t("summary_med_inst", v=app.med_institution_year),
        t("summary_years_exp", v=app.years_experience),
        t("summary_where_duration", v=app.where_duration),
        t("summary_current_job", v=app.current_job),
        t("summary_med_opinion", v=app.med_worker_opinion),
    ]
    return "\n".join(lines)

# === Прямые ссылки на файлы Telegram ===
async def get_file_url(file_id: Optional[str]) -> str:
    if not file_id:
        return ""
    try:
        f = await bot.get_file(file_id)
        return f"https://api.telegram.org/file/bot{TOKEN}/{f.file_path}"
    except Exception as e:
        print("get_file_url failed:", e)
        return ""

async def send_voice_prompt(chat_id: int):
    if os.path.exists(ASK_VOICE_PATH):
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VOICE)
        except Exception:
            pass
        try:
            await bot.send_voice(chat_id=chat_id, voice=FSInputFile(ASK_VOICE_PATH))
        except Exception as e:
            print("send_voice_prompt failed:", e)

async def send_video_note_prompt(chat_id: int):
    if os.path.exists(ASK_VIDEO_NOTE_PATH):
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.UPLOAD_VIDEO_NOTE)
        except Exception:
            pass
        try:
            await bot.send_video_note(chat_id=chat_id, video_note=FSInputFile(ASK_VIDEO_NOTE_PATH))
        except Exception as e:
            print("send_video_note_prompt failed:", e)

# ====== HANDLERS ======
@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    try:
        await bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.UPLOAD_VIDEO_NOTE)
    except Exception:
        pass

    video_path = "starter_note.mp4"
    if os.path.exists(video_path):
        try:
            await bot.send_video_note(chat_id=message.chat.id, video_note=FSInputFile(video_path))
        except Exception as e:
            print("starter video_note failed:", e)
    else:
        await message.answer(t("starter_hint"))

    await message.answer(t("hello"), reply_markup=kbd_directions())
    await state.set_state(HRForm.DIRECTION)

@dp.message(Command("here"))
async def here(message: Message):
    await message.answer(t("here", chat_id=message.chat.id))

@dp.callback_query(HRForm.DIRECTION, F.data.startswith("cat:"))
async def choose_category(cb: CallbackQuery, state: FSMContext):
    category = cb.data.split(":", 1)[1]
    await cb.message.edit_text(
        t("ask_sub_direction", cat=category),
        reply_markup=kbd_subdirections(category),
    )
    await cb.answer()

@dp.callback_query(HRForm.DIRECTION, F.data == "cat_back")
async def category_back(cb: CallbackQuery, state: FSMContext):
    await cb.message.edit_text(t("hello"), reply_markup=kbd_directions())
    await cb.answer()

@dp.callback_query(F.data.startswith("dir:"))
async def choose_direction(cb: CallbackQuery, state: FSMContext):
    payload = cb.data.split(":", 1)[1]
    if "|" in payload:
        category, sub = payload.split("|", 1)
        direction = f"{category} → {sub}"
    else:
        direction = payload
    await state.update_data(direction=direction)
    await cb.message.edit_reply_markup()
    await cb.message.answer(t("ask_full_name"))
    await state.set_state(HRForm.FULL_NAME)
    await cb.answer()

@dp.message(HRForm.FULL_NAME)
async def full_name_step(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if len(text.split()) < 2:
        await msg.answer(t("need_full_name"))
        return
    await state.update_data(full_name=text)
    await msg.answer(t("ask_phone"), reply_markup=kbd_share_contact())
    await state.set_state(HRForm.PHONE)

@dp.message(HRForm.PHONE, F.contact)
async def phone_from_button(msg: Message, state: FSMContext):
    phone = clean_phone(msg.contact.phone_number)
    await state.update_data(phone=phone)
    await after_phone(msg, state)

@dp.message(HRForm.PHONE)
async def phone_text(msg: Message, state: FSMContext):
    phone = clean_phone(msg.text)
    if len(phone) < 7:
        await msg.answer(t("phone_bad"))
        return
    await state.update_data(phone=phone)
    await after_phone(msg, state)

async def after_phone(msg: Message, state: FSMContext):
    await msg.answer(t("ask_birth"), reply_markup=None)
    await state.set_state(HRForm.BIRTHDATE)

@dp.message(HRForm.BIRTHDATE)
async def birthdate_step(msg: Message, state: FSMContext):
    text = (msg.text or "").strip()
    if not valid_date_ddmmyyyy(text):
        await msg.answer(t("birth_bad"))
        return
    await state.update_data(birth_date=text)
    await msg.answer(t("ask_edu"), reply_markup=kbd_edu())
    await state.set_state(HRForm.EDUCATION)

@dp.callback_query(HRForm.EDUCATION, F.data.startswith("edu:"))
async def education_step(cb: CallbackQuery, state: FSMContext):
    edu = cb.data.split(":", 1)[1]
    await state.update_data(education=edu)
    await cb.message.edit_reply_markup()
    await cb.message.answer(t("ask_study_place"))
    await state.set_state(HRForm.STUDY_PLACE)
    await cb.answer()

@dp.message(HRForm.STUDY_PLACE)
async def study_place_step(msg: Message, state: FSMContext):
    await state.update_data(study_place=(msg.text or "").strip())
    await msg.answer(t("ask_prev_dir"))
    await state.set_state(HRForm.PREV_DIRECTION)

@dp.message(HRForm.PREV_DIRECTION)
async def prev_direction_step(msg: Message, state: FSMContext):
    await state.update_data(prev_direction=(msg.text or "").strip())
    await msg.answer(t("ask_family"))
    await state.set_state(HRForm.FAMILY)

@dp.message(HRForm.FAMILY)
async def family_step(msg: Message, state: FSMContext):
    await state.update_data(family=(msg.text or "").strip())
    # СНАЧАЛА образец voice, ПОТОМ вопрос
    await send_voice_prompt(msg.chat.id)
    await msg.answer(t("ask_voice"))
    await state.set_state(HRForm.VOICE)

@dp.message(HRForm.VOICE, F.voice)
async def voice_step(msg: Message, state: FSMContext):
    await state.update_data(voice_file_id=msg.voice.file_id)
    # сразу к видео (языки убраны)
    await send_video_note_prompt(msg.chat.id)
    await msg.answer(t("ask_video"))
    await state.set_state(HRForm.SELF_VIDEO)

@dp.message(HRForm.VOICE)
async def voice_need_voice(msg: Message, state: FSMContext):
    await msg.answer(t("need_voice"))

@dp.message(HRForm.SELF_VIDEO, F.video_note | F.video)
async def self_video_step(msg: Message, state: FSMContext):
    file_id = msg.video_note.file_id if msg.video_note else msg.video.file_id
    await state.update_data(self_video_file_id=file_id)
    await msg.answer(t("ask_ref"), reply_markup=kbd_yesno("ref"))
    await state.set_state(HRForm.REF_CONSENT)

@dp.message(HRForm.SELF_VIDEO)
async def need_video(msg: Message, state: FSMContext):
    await msg.answer(t("need_video"))

@dp.callback_query(HRForm.REF_CONSENT, F.data.startswith("ref:"))
async def ref_consent_step(cb: CallbackQuery, state: FSMContext):
    yn = cb.data.split(":", 1)[1]  # "yes" | "no"
    yn_label = T[LANG]["yes"] if yn == YesNo.YES.value else T[LANG]["no"]
    await state.update_data(ref_check_consent=yn_label)
    await cb.message.edit_reply_markup()
    # last_job_referrer убрали -> сразу probation
    await cb.message.answer(t("ask_prob"))
    await state.set_state(HRForm.PROBATION)
    await cb.answer()

@dp.message(HRForm.PROBATION)
async def probation_step(msg: Message, state: FSMContext):
    await state.update_data(probation=(msg.text or "").strip())
    await msg.answer(t("ask_overtime"), reply_markup=kbd_yesno("overtime"))
    await state.set_state(HRForm.AFTER_HOURS)

@dp.callback_query(HRForm.AFTER_HOURS, F.data.startswith("overtime:"))
async def after_hours_step(cb: CallbackQuery, state: FSMContext):
    yn = cb.data.split(":", 1)[1]  # "yes" | "no"
    yn_label = T[LANG]["yes"] if yn == YesNo.YES.value else T[LANG]["no"]
    await state.update_data(after_hours=yn_label)
    await cb.message.edit_reply_markup()
    await cb.message.answer(t("ask_health"))
    await state.set_state(HRForm.HEALTH)
    await cb.answer()

@dp.message(HRForm.HEALTH)
async def health_step(msg: Message, state: FSMContext):
    await state.update_data(health=(msg.text or "").strip())
    # Рефлексия
    await msg.answer(t("ask_why_late"))
    await state.set_state(HRForm.WHY_LATE)

@dp.message(HRForm.WHY_LATE)
async def why_late_step(msg: Message, state: FSMContext):
    await state.update_data(late_opinion=(msg.text or "").strip())
    await msg.answer(t("ask_why_steal"))
    await state.set_state(HRForm.WHY_STEAL)

@dp.message(HRForm.WHY_STEAL)
async def why_steal_step(msg: Message, state: FSMContext):
    await state.update_data(theft_opinion=(msg.text or "").strip())
    await msg.answer(t("ask_why_perf"))
    await state.set_state(HRForm.WHY_PERF)

@dp.message(HRForm.WHY_PERF)
async def why_perf_step(msg: Message, state: FSMContext):
    await state.update_data(performance_opinion=(msg.text or "").strip())
    await msg.answer(t("ask_last_salary"))
    await state.set_state(HRForm.LAST_SALARY)

@dp.message(HRForm.LAST_SALARY)
async def last_salary_step(msg: Message, state: FSMContext):
    await state.update_data(last_salary=(msg.text or "").strip())
    await msg.answer(t("ask_desired_salary"))
    await state.set_state(HRForm.DESIRED_SALARY)

@dp.message(HRForm.DESIRED_SALARY)
async def desired_salary_step(msg: Message, state: FSMContext):
    await state.update_data(desired_salary=(msg.text or "").strip())
    # Курслар убран -> переходим к мед-блоку
    await msg.answer(t("ask_med_inst"))
    await state.set_state(HRForm.MED_INST)

@dp.message(HRForm.MED_INST)
async def med_inst_step(msg: Message, state: FSMContext):
    await state.update_data(med_institution_year=(msg.text or "").strip())
    await msg.answer(t("ask_years_exp"))
    await state.set_state(HRForm.YEARS_EXP)

@dp.message(HRForm.YEARS_EXP)
async def years_exp_step(msg: Message, state: FSMContext):
    await state.update_data(years_experience=(msg.text or "").strip())
    await msg.answer(t("ask_where_duration"))
    await state.set_state(HRForm.WHERE_DURATION)

@dp.message(HRForm.WHERE_DURATION)
async def where_duration_step(msg: Message, state: FSMContext):
    await state.update_data(where_duration=(msg.text or "").strip())
    await msg.answer(t("ask_current_job"))
    await state.set_state(HRForm.CURRENT_JOB)

@dp.message(HRForm.CURRENT_JOB)
async def current_job_step(msg: Message, state: FSMContext):
    await state.update_data(current_job=(msg.text or "").strip())
    await msg.answer(t("ask_med_opinion"))
    await state.set_state(HRForm.MED_OPINION)

@dp.message(HRForm.MED_OPINION)
async def med_opinion_step(msg: Message, state: FSMContext):
    data = await state.update_data(med_worker_opinion=(msg.text or "").strip())

    app = Application(
        user_id=msg.from_user.id,
        username=msg.from_user.username,
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        direction=data.get("direction"),
        full_name=data.get("full_name"),
        phone=data.get("phone"),
        birth_date=data.get("birth_date"),
        education=data.get("education"),
        study_place=data.get("study_place"),
        prev_direction=data.get("prev_direction"),
        family=data.get("family"),
        voice_file_id=data.get("voice_file_id"),
        languages=None,
        self_video_file_id=data.get("self_video_file_id"),
        ref_check_consent=data.get("ref_check_consent"),
        last_job_referrer=None,
        probation=data.get("probation"),
        after_hours=data.get("after_hours"),
        health=data.get("health"),
        late_opinion=data.get("late_opinion"),
        theft_opinion=data.get("theft_opinion"),
        performance_opinion=data.get("performance_opinion"),
        last_salary=data.get("last_salary"),
        desired_salary=data.get("desired_salary"),
        courses=None,
        med_institution_year=data.get("med_institution_year"),
        years_experience=data.get("years_experience"),
        where_duration=data.get("where_duration"),
        current_job=data.get("current_job"),
        med_worker_opinion=data.get("med_worker_opinion"),
    )

    # Сначала сохраняем в БД
    record_id = save_application(app)

    # Получаем прямые ссылки на voice и video (если есть)
    app.voice_url = await get_file_url(app.voice_file_id)
    app.video_url = await get_file_url(app.self_video_file_id)

    # ---> Google Sheets
    if GSHEETS_ENABLE:
        await append_to_sheet(app, record_id)

    # ---> HR чат
    if HR_CHAT_ID:
        try:
            await bot.send_message(HR_CHAT_ID, fmt_summary(app, record_id))
            if app.voice_file_id:
                await bot.send_voice(HR_CHAT_ID, app.voice_file_id, caption=t("voice_caption", id=record_id))
            if app.self_video_file_id:
                try:
                    await bot.send_video_note(HR_CHAT_ID, app.self_video_file_id)
                except Exception:
                    await bot.send_video(HR_CHAT_ID, app.self_video_file_id, caption=t("video_caption", id=record_id))
        except Exception as e:
            await msg.answer(t("send_fail"))
            print("HR send failed:", e)

    await msg.answer(t("thanks"))
    await state.set_state(HRForm.DONE)

# Команды сервиса
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(t("cancel"))

# ====== RUN ======
async def main():
    if RUN_MODE == "WEBHOOK":
        from aiohttp import web
        PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
        WEBHOOK_PATH = os.getenv("WEBHOOK_PATH", "/webhook/telegram/")
        if not PUBLIC_BASE_URL:
            raise RuntimeError("PUBLIC_BASE_URL required for WEBHOOK mode")
        await bot.set_webhook(url=PUBLIC_BASE_URL.rstrip("/") + WEBHOOK_PATH)

        app = web.Application()
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler
        SimpleRequestHandler(dp, bot).register(app, path=WEBHOOK_PATH)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
        await site.start()
        print("Webhook server is running...")
        await asyncio.Event().wait()
    else:
        print("Bot started in POLLING mode")
        await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped")
