"""Ultra-optimized 90-second animated showcase video generator for CTO AI Copilot.

Renders 2700 frames @ 30fps (1920x1080 Full HD) with:
- Pre-rendered scene card templates for maximum Python throughput (100+ fps)
- Dynamic Ken Burns pan & zoom motion on each feature screenshot
- Ultra-modern dark glassmorphic UI frame & ambient lighting
- Crisp Arabic & English feature descriptions, badges, and metric pills
- Multithreaded FFmpeg with -preset ultrafast -threads 0
"""

import math
import os
import subprocess
import sys
import time

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH = 1920
HEIGHT = 1080
FPS = 30
TOTAL_DURATION = 90.0
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)  # 2700 frames

INTRO_FRAMES = 105
SCENE_FRAMES = 225
OUTRO_FRAMES = 120

PW, PH = 1320, 680
MX = (WIDTH - PW) // 2
MY = 110

FONT_BOLD_PATH = "C:/Windows/Fonts/segoeuib.ttf"
FONT_REG_PATH = "C:/Windows/Fonts/segoeui.ttf"
FONT_AR_PATH = "C:/Windows/Fonts/tahoma.ttf"

font_logo = ImageFont.truetype(FONT_BOLD_PATH, 24)
font_sm = ImageFont.truetype(FONT_REG_PATH, 16)
font_badge = ImageFont.truetype(FONT_BOLD_PATH, 14)
font_badge_sm = ImageFont.truetype(FONT_BOLD_PATH, 13)
font_title = ImageFont.truetype(FONT_BOLD_PATH, 36)
font_ar = ImageFont.truetype(FONT_AR_PATH, 22)
font_hero_title = ImageFont.truetype(FONT_BOLD_PATH, 68)
font_hero_sub = ImageFont.truetype(FONT_BOLD_PATH, 28)
font_hero_ar = ImageFont.truetype(FONT_AR_PATH, 30)

def create_static_bg() -> Image.Image:
    bg = Image.new("RGB", (WIDTH, HEIGHT), (9, 13, 23))
    orbs = [
        (250, 180, 420, (30, 58, 138)),
        (1720, 220, 380, (88, 28, 135)),
        (960, 920, 480, (14, 116, 144)),
        (1600, 850, 400, (30, 64, 175)),
    ]
    for cx, cy, r, col in orbs:
        layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        ldraw = ImageDraw.Draw(layer)
        ldraw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col + (75,))
        layer = layer.filter(ImageFilter.GaussianBlur(110))
        bg.paste(layer, (0, 0), layer)
    return bg

STATIC_BG = create_static_bg()

def ease_in_out(x: float) -> float:
    return 0.5 * (1.0 - math.cos(math.pi * x))

def shape_ar(text: str) -> str:
    return get_display(arabic_reshaper.reshape(text))

SCENES = [
    {
        "img_path": "video/photo_2_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/menu",
        "category": "CENTRAL ARCHITECTURE",
        "title": "Unified Workspace Hub",
        "ar_desc": "قائمة تحكم متكاملة تتيح التنقل السريع بين كافة أدوات المنظومة الهندسية بنقرة واحدة",
        "pills": ["🧭 8 Unified Services", "⚡ One-Click Navigation", "📱 Sleek Glassmorphism"],
        "start_crop": (0.2, 0.0, 1.0, 0.95),
        "end_crop": (0.0, 0.0, 1.0, 1.0),
    },
    {
        "img_path": "video/photo_1_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/chat",
        "category": "CONVERSATIONAL AI",
        "title": "CTO AI Copilot (Chatbot)",
        "ar_desc": "مساعد هندسي ذكي يفهم العامية المصرية والإنجليزية، ويجيب بدقة عن الـ PRs ونشاط المستودع",
        "pills": ["🗣️ Arabic & English", "🔍 Real-Time PR Data", "🧠 Grounded AI Answers"],
        "start_crop": (0.05, 0.05, 0.95, 0.95),
        "end_crop": (0.25, 0.15, 0.85, 0.85),
    },
    {
        "img_path": "video/photo_7_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/voice-copilot",
        "category": "REAL-TIME VOICE AI",
        "title": "Deepgram Live Voice Copilot",
        "ar_desc": "مساعد صوتي لحظي بدون استخدام اليدين يتيح إجراء محادثات صوتية طبيعية ومتابعة مؤشرات الـ SLA",
        "pills": ["🎙️ Deepgram Streaming", "⚡ Ultra-Low Latency", "📝 Live Audio Transcript"],
        "start_crop": (0.0, 0.0, 1.0, 1.0),
        "end_crop": (0.22, 0.20, 0.78, 0.80),
    },
    {
        "img_path": "video/photo_3_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/velocity",
        "category": "ENGINEERING PULSE",
        "title": "Team Velocity & SLA Health",
        "ar_desc": "مراقبة حية لصحة الـ SLA بنسبة 100% مع رسم بياني تفاعلي يوضح نشاط فتح ودمج الـ PRs أسبوعياً",
        "pills": ["🟢 100% SLA Health", "📈 7-Day Activity Chart", "⚡ Live PR Telemetry"],
        "start_crop": (0.15, 0.10, 0.85, 0.70),
        "end_crop": (0.20, 0.35, 0.80, 0.95),
    },
    {
        "img_path": "video/photo_4_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/pull-requests",
        "category": "PULL REQUEST INTELLIGENCE",
        "title": "Automated PR Intelligence Directory",
        "ar_desc": "جدول ذكي يسرد كافة الـ PRs مع تلخيص آلي بالذكاء الاصطناعي وتقييم درجة الأثر والتعقيد",
        "pills": ["🤖 AI Auto-Summaries", "⭐ Impact Score (1-10)", "🔄 Webhook Sync"],
        "start_crop": (0.05, 0.05, 0.95, 0.95),
        "end_crop": (0.20, 0.22, 0.80, 0.82),
    },
    {
        "img_path": "video/photo_5_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/engineer-impact",
        "category": "TEAM ANALYTICS",
        "title": "Engineer Impact & Output Dashboard",
        "ar_desc": "لوحة تحليلية تصنف المطورين وفق الأثر المعماري الحقيقي بدلاً من عدد الـ Commits التقليدي",
        "pills": ["🏆 Impact Ranking", "📅 30-Day Window", "🥇 Contributor Tiers"],
        "start_crop": (0.0, 0.05, 1.0, 0.95),
        "end_crop": (0.12, 0.30, 0.88, 0.90),
    },
    {
        "img_path": "video/photo_9_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/overdue-radar",
        "category": "SLA GOVERNANCE",
        "title": "Overdue PRs & SLA Alert Radar",
        "ar_desc": "رادار استباقي يراقب الـ PRs المتأخرة عن موعد الـ SLA المحدد (8 أيام) لمنع تراكم المهام",
        "pills": ["⏱️ 8-Day SLA Threshold", "🛡️ Zero-Stale Pipeline", "🔔 Instant Alerts"],
        "start_crop": (0.05, 0.05, 0.95, 0.95),
        "end_crop": (0.22, 0.30, 0.78, 0.85),
    },
    {
        "img_path": "video/photo_6_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/email-triage",
        "category": "INBOX TRIAGE",
        "title": "Intelligent Inbox Triage Agent",
        "ar_desc": "فرز وتلخيص تلقائي لرسائل البريد الإلكتروني مع تقييم درجة الأهمية وتحديد مستوى الاستعجال",
        "pills": ["✉️ Auto Inbox Polling", "🎯 Urgency Tagging", "📋 Executive Summary"],
        "start_crop": (0.08, 0.10, 0.92, 0.85),
        "end_crop": (0.15, 0.20, 0.85, 0.95),
    },
    {
        "img_path": "video/photo_8_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/daily-reports",
        "category": "EXECUTIVE AUTOMATION",
        "title": "Scheduled Daily CTO Reports",
        "ar_desc": "توليد تقارير يومية تلقائية في تمام الساعة 08:00 صباحاً تجمع مؤشرات الـ 24 ساعة السابقة مع ملف PDF",
        "pills": ["⏰ Celery Beat 08:00", "📄 Executive PDF Ready", "☁️ S3 / MinIO Storage"],
        "start_crop": (0.0, 0.05, 1.0, 0.95),
        "end_crop": (0.15, 0.25, 0.85, 0.85),
    },
    {
        "img_path": "video/photo_11_2026-10-13_10-13-25.jpg",
        "url": "https://slack.com/app/cto-briefing-channel",
        "category": "SLACK INTEGRATION",
        "title": "Slack Executive Briefing Delivery",
        "ar_desc": "إرسال تقرير الصباح التنفيذي مع مرفق الـ PDF وقائمة المؤشرات مباشرة إلى قناة الـ Slack",
        "pills": ["💬 Direct Slack Channel", "📎 Attached Daily PDF", "📊 24h Snapshot"],
        "start_crop": (0.0, 0.0, 1.0, 1.0),
        "end_crop": (0.05, 0.10, 0.65, 0.85),
    },
    {
        "img_path": "video/photo_10_2026-10-13_10-13-25.jpg",
        "url": "https://cto-copilot.internal/workspace/eval-lab",
        "category": "BENCHMARKS & MLFLOW",
        "title": "Eval Lab: Torture Tests & MLflow",
        "ar_desc": "بيئة اختبار متطورة بـ 122 سؤالاً مع بوابة LLM-as-a-Judge وتتبع في MLflow بدقة تتجاوز 97%",
        "pills": ["⚖️ LLM-as-a-Judge Gate", "📈 MLflow Experiment Hub", "🛡️ 0% Hallucination"],
        "start_crop": (0.05, 0.05, 0.95, 0.95),
        "end_crop": (0.10, 0.35, 0.90, 0.85),
    },
]

# Preload raw images
PRELOADED_IMAGES = [Image.open(s["img_path"]).convert("RGB") for s in SCENES]

# Pre-render base canvas for each scene
PRELOADED_SCENE_BASES = []

for idx, s in enumerate(SCENES):
    canvas = STATIC_BG.copy()
    draw = ImageDraw.Draw(canvas)

    # Top nav bar
    draw.rectangle([0, 0, WIDTH, 65], fill=(15, 23, 42))
    draw.line([(0, 65), (WIDTH, 65)], fill=(30, 41, 59), width=1)
    draw.ellipse([42, 26, 54, 38], fill=(16, 185, 129))
    draw.text((65, 20), "CTO AI COPILOT", font=font_logo, fill=(255, 255, 255))
    draw.text((275, 25), "• PRODUCTION READY", font=font_sm, fill=(52, 211, 153))

    # Center Badge
    badge_text = f"FEATURE {idx + 1:02d} / 11  •  {s['category']}"
    draw.rounded_rectangle([700, 14, 1220, 52], radius=19, fill=(30, 41, 59), outline=(59, 130, 246), width=1)
    draw.text((735, 23), badge_text, font=font_badge, fill=(147, 197, 253))

    # Mock Window Container
    draw.rounded_rectangle([MX - 10, MY - 36, MX + PW + 10, MY + PH + 10], radius=16, fill=(17, 24, 39), outline=(51, 65, 85), width=2)
    draw.ellipse([MX + 5, MY - 24, MX + 17, MY - 12], fill=(239, 68, 68))
    draw.ellipse([MX + 25, MY - 24, MX + 37, MY - 12], fill=(245, 158, 11))
    draw.ellipse([MX + 45, MY - 24, MX + 57, MY - 12], fill=(16, 185, 129))
    draw.rounded_rectangle([MX + 80, MY - 28, MX + PW - 30, MY - 8], radius=6, fill=(30, 41, 59))
    draw.text((MX + 100, MY - 25), s["url"], font=font_sm, fill=(148, 163, 184))

    # Bottom Info Card
    by = 835
    draw.rounded_rectangle([200, by, 1720, by + 195], radius=18, fill=(15, 23, 42), outline=(59, 130, 246), width=2)
    draw.rounded_rectangle([230, by + 18, 430, by + 48], radius=12, fill=(37, 99, 235))
    draw.text((245, by + 23), "CORE CAPABILITY", font=font_badge_sm, fill=(255, 255, 255))
    draw.text((455, by + 14), s["title"], font=font_title, fill=(255, 255, 255))
    ar_shaped = shape_ar(s["ar_desc"])
    draw.text((230, by + 68), ar_shaped, font=font_ar, fill=(226, 232, 240))

    px = 230
    for pill in s["pills"]:
        draw.rounded_rectangle([px, by + 128, px + 270, by + 168], radius=10, fill=(30, 41, 59), outline=(71, 85, 105), width=1)
        draw.text((px + 15, by + 138), pill, font=font_sm, fill=(147, 197, 253))
        px += 290

    PRELOADED_SCENE_BASES.append(canvas)


def render_intro_frame(frame_idx: int) -> Image.Image:
    t = frame_idx / float(INTRO_FRAMES)
    img = STATIC_BG.copy()
    draw = ImageDraw.Draw(img)

    cx, cy = WIDTH // 2, HEIGHT // 2 - 130
    emblem_r = int(70 + 6 * math.sin(t * math.pi * 3))
    draw.ellipse([cx - emblem_r - 20, cy - emblem_r - 20, cx + emblem_r + 20, cy + emblem_r + 20], fill=(30, 58, 138))
    draw.ellipse([cx - emblem_r, cy - emblem_r, cx + emblem_r, cy + emblem_r], fill=(59, 130, 246), outline=(147, 197, 253), width=4)
    draw.text((cx - 36, cy - 30), "CTO", font=ImageFont.truetype(FONT_BOLD_PATH, 34), fill=(255, 255, 255))

    t_y = HEIGHT // 2 - 20
    draw.text((WIDTH // 2 - 280, t_y), "CTO AI COPILOT", font=font_hero_title, fill=(255, 255, 255))
    draw.text((WIDTH // 2 - 470, t_y + 85), "Next-Gen Autonomous Engineering Operations & Multi-Agent Intelligence", font=font_hero_sub, fill=(147, 197, 253))
    ar_tag = shape_ar("المنظومة الذكية المتكاملة لقيادة الفرق الهندسية وتطوير البرمجيات")
    draw.text((WIDTH // 2 - 380, t_y + 135), ar_tag, font=font_hero_ar, fill=(226, 232, 240))

    pills = [
        "🚀 11 Core Modules",
        "🗣️ Bilingual Arabic & English",
        "🎙️ Deepgram Live Voice",
        "🛡️ Zero Hallucination (MLflow)",
    ]
    total_w = len(pills) * 280
    start_x = (WIDTH - total_w) // 2
    for i, p in enumerate(pills):
        px = start_x + i * 280
        py = t_y + 215
        draw.rounded_rectangle([px, py, px + 260, py + 48], radius=24, fill=(30, 41, 59), outline=(59, 130, 246), width=1)
        draw.text((px + 20, py + 14), p, font=font_badge, fill=(255, 255, 255))

    prog_w = int(WIDTH * (frame_idx / float(TOTAL_FRAMES)))
    draw.line([(0, HEIGHT - 6), (WIDTH, HEIGHT - 6)], fill=(30, 41, 59), width=6)
    if prog_w > 0:
        draw.line([(0, HEIGHT - 6), (prog_w, HEIGHT - 6)], fill=(59, 130, 246), width=6)

    return img


def render_outro_frame(frame_idx: int) -> Image.Image:
    t = frame_idx / float(OUTRO_FRAMES)
    img = STATIC_BG.copy()
    draw = ImageDraw.Draw(img)

    cy = HEIGHT // 2 - 120
    draw.text((WIDTH // 2 - 280, cy), "CTO AI COPILOT", font=font_hero_title, fill=(255, 255, 255))
    draw.text((WIDTH // 2 - 420, cy + 85), "Engineering Leadership Powered by Autonomous AI Agents", font=font_hero_sub, fill=(147, 197, 253))

    ar_end = shape_ar("جاهز للإنتاج بنسبة 100% • بنية تحتية هندسية فائقة السرعة والموثوقية")
    draw.text((WIDTH // 2 - 400, cy + 140), ar_end, font=font_hero_ar, fill=(52, 211, 153))

    stack = ["FastAPI", "LangChain", "Celery", "Deepgram Voice", "MinIO S3", "MLflow", "MySQL 8.0", "Redis"]
    sw = len(stack) * 160
    sx = (WIDTH - sw) // 2
    for i, s in enumerate(stack):
        bx = sx + i * 160
        by = cy + 220
        draw.rounded_rectangle([bx, by, bx + 145, by + 45], radius=12, fill=(15, 23, 42), outline=(59, 130, 246), width=1)
        draw.text((bx + 20, by + 12), s, font=font_badge, fill=(226, 232, 240))

    prog_w = int(WIDTH * ((INTRO_FRAMES + len(SCENES) * SCENE_FRAMES + frame_idx) / float(TOTAL_FRAMES)))
    draw.line([(0, HEIGHT - 6), (WIDTH, HEIGHT - 6)], fill=(30, 41, 59), width=6)
    draw.line([(0, HEIGHT - 6), (prog_w, HEIGHT - 6)], fill=(59, 130, 246), width=6)

    if frame_idx > OUTRO_FRAMES - 20:
        fade_t = (frame_idx - (OUTRO_FRAMES - 20)) / 20.0
        black = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, int(255 * fade_t)))
        img.paste(black, (0, 0), black)

    return img


def render_scene_frame(scene_idx: int, frame_in_scene: int, global_frame: int) -> Image.Image:
    s = SCENES[scene_idx]
    raw_img = PRELOADED_IMAGES[scene_idx]
    iw, ih = raw_img.size

    t = frame_in_scene / float(SCENE_FRAMES)
    eased_t = ease_in_out(t)

    sc = s["start_crop"]
    ec = s["end_crop"]
    x0 = sc[0] + (ec[0] - sc[0]) * eased_t
    y0 = sc[1] + (ec[1] - sc[1]) * eased_t
    x1 = sc[2] + (ec[2] - sc[2]) * eased_t
    y1 = sc[3] + (ec[3] - sc[3]) * eased_t

    crop_box = (
        max(0, int(x0 * iw)),
        max(0, int(y0 * ih)),
        min(iw, int(x1 * iw)),
        min(ih, int(y1 * ih)),
    )
    cropped = raw_img.crop(crop_box)
    resized_crop = cropped.resize((PW, PH), Image.Resampling.BILINEAR)

    # Use pre-rendered base!
    frame_canvas = PRELOADED_SCENE_BASES[scene_idx].copy()
    frame_canvas.paste(resized_crop, (MX, MY))

    draw = ImageDraw.Draw(frame_canvas)

    # Timecode
    sec_curr = int(global_frame / float(FPS))
    tc_text = f"{sec_curr // 60:02d}:{sec_curr % 60:02d} / 01:30"
    draw.rectangle([1710, 15, 1890, 55], fill=(15, 23, 42))
    draw.text((1720, 22), tc_text, font=font_logo, fill=(148, 163, 184))

    # Snappy 6-frame crossfade at start of scene
    if frame_in_scene < 6:
        fade_val = int(255 * (1.0 - (frame_in_scene / 6.0)))
        fade = Image.new("RGBA", (WIDTH, HEIGHT), (9, 13, 23, fade_val))
        frame_canvas.paste(fade, (0, 0), fade)

    # Bottom progress bar
    prog_w = int(WIDTH * (global_frame / float(TOTAL_FRAMES)))
    draw.line([(0, HEIGHT - 6), (WIDTH, HEIGHT - 6)], fill=(30, 41, 59), width=6)
    if prog_w > 0:
        draw.line([(0, HEIGHT - 6), (prog_w, HEIGHT - 6)], fill=(59, 130, 246), width=6)

    return frame_canvas


def main():
    print(f"Starting optimized showcase video generation: {TOTAL_FRAMES} frames @ {FPS} fps ({TOTAL_DURATION}s)...", flush=True)
    start_time = time.time()

    import imageio_ffmpeg
    local_output = "d:/CTO_MULTI_AGENT/video/cto_copilot_90s_showcase.mp4"
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    print(f"Using native FFmpeg binary: {ffmpeg_exe}", flush=True)

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{WIDTH}x{HEIGHT}",
        "-pix_fmt", "rgb24",
        "-r", str(FPS),
        "-i", "-",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "ultrafast",
        "-crf", "20",
        "-threads", "0",
        "-movflags", "+faststart",
        local_output,
    ]

    print("Launching Docker FFmpeg subprocess...", flush=True)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)

    try:
        current_frame = 0

        # 1. Render Intro
        print(f"Rendering Intro ({INTRO_FRAMES} frames)...", flush=True)
        for f in range(INTRO_FRAMES):
            frame_img = render_intro_frame(f)
            proc.stdin.write(frame_img.tobytes())
            current_frame += 1

        # 2. Render 11 Scenes
        for s_idx in range(len(SCENES)):
            print(f"[{s_idx + 1}/11] Rendering: {SCENES[s_idx]['title']} ({SCENE_FRAMES} frames)...", flush=True)
            for f in range(SCENE_FRAMES):
                frame_img = render_scene_frame(s_idx, f, current_frame)
                proc.stdin.write(frame_img.tobytes())
                current_frame += 1

        # 3. Render Outro
        print(f"Rendering Outro ({OUTRO_FRAMES} frames)...", flush=True)
        for f in range(OUTRO_FRAMES):
            frame_img = render_outro_frame(f)
            proc.stdin.write(frame_img.tobytes())
            current_frame += 1

        print("All 2700 frames rendered. Finalizing FFmpeg encoding...", flush=True)
        proc.stdin.close()
        proc.wait()

        if proc.returncode != 0:
            print("FFmpeg process failed with exit code:", proc.returncode, flush=True)
            sys.exit(proc.returncode)

        elapsed = time.time() - start_time
        fps_rendered = TOTAL_FRAMES / elapsed
        print(f"SUCCESS: Video generated in {elapsed:.1f}s ({fps_rendered:.1f} fps)!", flush=True)
        print(f"Saved to: {local_output}", flush=True)

    except Exception as exc:
        print("Exception during video generation:", exc, flush=True)
        proc.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
