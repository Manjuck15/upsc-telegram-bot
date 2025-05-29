import datetime
import schedule
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PollAnswerHandler

# === CONFIG ===
BOT_TOKEN = '7331418623:AAFtHkoABNXsob7eM9wDPPVD7wwYq2l5weA'
CHAT_ID = -1002600042907  # Your Telegram group chat ID
GOOGLE_SHEET_NAME = 'UPSC_Answers'
CREDENTIALS_FILE = 'hale-entry-461210-k3-cc040adbe19f.json'

# === MCQs for Today ===
mcqs = [
    {
        "question": "What key argument did PM Modi make regarding Pakistan's actions post-1947?",
        "options": [
            "Pakistan became democratic too late",
            "Terrorism by Pakistan is a form of proxy war",
            "Pakistan has waged a sustained military strategy through terrorism",
            "Kashmir was never disputed"
        ],
        "correct": 2
    },
    {
        "question": "Which organisation is reported to be involved in a blast in Punjab?",
        "options": [
            "Hizbul Mujahideen",
            "Jaish-e-Mohammed",
            "Lashkar-e-Taiba",
            "Babbar Khalsa International (BKI)"
        ],
        "correct": 3
    }
]

# === Google Sheets Setup ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet("responses")

# === Bot Setup ===
app = ApplicationBuilder().token(BOT_TOKEN).build()
user_data = {}  # store poll_id to question map

# === Function to Post Daily Quiz ===
async def post_mcqs(context: ContextTypes.DEFAULT_TYPE = None):
    for idx, mcq in enumerate(mcqs):
        poll_message = await app.bot.send_poll(
            chat_id=CHAT_ID,
            question=f"Q{idx+1}. {mcq['question']}",
            options=mcq["options"],
            type="quiz",
            correct_option_id=mcq["correct"],
            is_anonymous=True
        )
        # Store question info by poll_id
        user_data[poll_message.poll.id] = {
            "question": mcq["question"],
            "options": mcq["options"],
            "correct": mcq["correct"]
        }

# === Handle User Answer ===
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    username = answer.user.username or answer.user.first_name or "Anonymous"
    selected = answer.option_ids[0]

    if poll_id in user_data:
        qdata = user_data[poll_id]
        correct = qdata["correct"]
        selected_text = qdata["options"][selected]
        is_correct = selected == correct
        score = 1 if is_correct else 0

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([
            timestamp,
            username,
            str(user_id),
            qdata["question"],
            selected_text,
            str(is_correct),
            score
        ])

# === Manual Trigger (/start) ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await post_mcqs()

# === Bind Handlers ===
app.add_handler(CommandHandler("start", start))
app.add_handler(PollAnswerHandler(handle_poll_answer))

# === Schedule for 8:00 AM daily ===
def run_scheduler():
    schedule.every().day.at("08:00").do(lambda: app.create_task(post_mcqs()))
    while True:
        schedule.run_pending()
        time.sleep(30)

# === Main Entry Point ===
if __name__ == '__main__':
    import threading
    threading.Thread(target=run_scheduler).start()
    app.run_polling()