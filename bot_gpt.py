import os
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, ContextTypes, filters
from openai import OpenAI

# ====== 读取环境变量（不要写死KEY）======
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN 没设置")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY 没设置")

client = OpenAI(api_key=OPENAI_API_KEY)

DICT_FILE = "custom_dict.json"
LOG_FILE = "log.txt"

# ====== 初始化词库 ======
if os.path.exists(DICT_FILE):
    with open(DICT_FILE, "r", encoding="utf-8") as f:
        custom_dict = json.load(f)
else:
    custom_dict = {
        "我要下班": "tôi đi tan làm đây",
        "我快下班": "tôi sắp tan làm",
        "下班": "tan làm",
        "上班": "đi làm",
        "可以去": "đi đi",
        "幫掃": "Quét mặt để xác minh ngay",
        "注意掃臉": "Đơn nhiều, phải quét mặt đầy đủ",
        "目前單多注意掃臉": "Đơn nhiều, phải quét mặt đầy đủ",
        "辛苦": "Cảm ơn nhé"
    }

last_text = None

def save_dict():
    with open(DICT_FILE, "w", encoding="utf-8") as f:
        json.dump(custom_dict, f, ensure_ascii=False, indent=2)

def write_log(src, dst):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} | {src} -> {dst}\n")

def is_chinese(text):
    return any('\u4e00' <= c <= '\u9fff' for c in text)

# ====== GPT提示（优化语义）======
def build_prompt(text, zh_to_vi):
    if zh_to_vi:
        return f"""
把中文翻译成越南人日常讲话方式（自然口语）：

规则：
1. 不要逐字翻译
2. 要像越南人平常讲话
3. “辛苦”要表达成感谢，不要翻成 mệt
4. 语气自然（员工/管理都适用）
5. 只输出翻译结果

内容：
{text}
"""
    else:
        return f"""
把越南文翻译成自然中文：

规则：
1. 不要直译
2. 要像真人讲话
3. 保留语气（提醒/命令/礼貌）
4. 只输出翻译结果

内容：
{text}
"""

# ====== 主逻辑 ======
async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global last_text

    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()

    try:
        # 不翻机器人
        if update.message.from_user and update.message.from_user.is_bot:
            return

        # 不翻确认类
        if text in ["1", "1️⃣", "１", "ok", "OK", "好", "收到"]:
            return

        # ===== 修正学习 =====
        if text.startswith("修正：") or text.startswith("修正:"):
            fix = text.split("：")[-1] if "：" in text else text.split(":")[-1]
            if last_text:
                custom_dict[last_text] = fix.strip()
                save_dict()
                await update.message.reply_text(f"✅ 已学习：{last_text}")
            return

        # ===== 特殊命令 =====
        if text == "幫掃":
            reply = "🇻🇳 Quét mặt để xác minh ngay"
            await update.message.reply_text(reply)
            write_log(text, reply)
            last_text = text
            return

        if "注意" in text and "掃臉" in text:
            reply = "🇻🇳 Đơn nhiều, phải quét mặt đầy đủ"
            await update.message.reply_text(reply)
            write_log(text, reply)
            last_text = text
            return

        # ===== 词库（包含匹配🔥）=====
        for k, v in custom_dict.items():
            if k in text:
                if is_chinese(text):
                    reply = f"🇻🇳 {v}"
                else:
                    reply = f"🇨🇳 {v}"

                await update.message.reply_text(reply)
                write_log(text, reply)
                last_text = text
                return

        # ===== GPT翻译 =====
        zh_to_vi = is_chinese(text)
        prompt = build_prompt(text, zh_to_vi)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt
        )

        result = response.output_text.strip()

        if zh_to_vi:
            reply = f"🇻🇳 {result}"
        else:
            reply = f"🇨🇳 {result}"

        await update.message.reply_text(reply)

        write_log(text, reply)
        last_text = text

    except Exception as e:
        await update.message.reply_text(f"❌ {e}")

# ====== 启动 ======
app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

print("🤖 GPT翻译机器人已启动...")
app.run_polling()
print("🔥 FINAL VERSION RUNNING 🔥")