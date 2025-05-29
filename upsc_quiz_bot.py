import datetime
import schedule
import time
import gspread
import requests
import random
from bs4 import BeautifulSoup
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, PollAnswerHandler, ChatMemberHandler

# === CONFIG ===
BOT_TOKEN = '7331418623:AAFtHkoABNXsob7eM9wDPPVD7wwYq2l5weA'
CHAT_ID = -1002600042907  # Your group chat ID
GOOGLE_SHEET_NAME = 'UPSC_Answers'
CREDENTIALS_FILE = 'hale-entry-461210-k3-cc040adbe19f.json'

# === Google Sheets Setup ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).worksheet("responses")

app = ApplicationBuilder().token(BOT_TOKEN).build()
user_data = {}  # poll_id -> metadata

# === Utility: Scrape headlines (PIB, PRS, etc.) ===
def fetch_headlines():
    urls = [
        "https://pib.gov.in/PressRelese.aspx",  # PIB
        "https://prsindia.org/theprsblog",       # PRS blog
        "https://timesofindia.indiatimes.com/briefs"  # ToI briefs
    ]
    headlines = []
    for url in urls:
        try:
            r = requests.get(url, timeout=10)
            soup = BeautifulSoup(r.text, 'html.parser')
            text = soup.get_text()
            lines = [line.strip() for line in text.split('\n') if 60 < len(line) < 180]
            headlines.extend(lines[:5])
        except:
            continue
    return random.sample(headlines, min(10, len(headlines)))

# === Utility: Generate MCQs from headlines ===
def generate_mcqs_from_current_affairs():
    headlines = fetch_headlines()
    mcqs = []
    for i, headline in enumerate(headlines):
        q = f"Which of the following best relates to: '{headline[:70]}...?"  # reframe headline as context
        options = [
            "Economy-related policy",
            "International agreement",
            "Government scheme",
            "Parliamentary procedure"
        ]
        correct = random.randint(0, 3)
        mcqs.append({"question": q, "options": options, "correct": correct})
    return mcqs

# === Function to Post MCQs ===
async def post_mcqs():
    global user_data
    mcqs = generate_mcqs_from_current_affairs()
    for idx, mcq in enumerate(mcqs):
        poll = await app.bot.send_poll(
            chat_id=CHAT_ID,
            question=f"Q{idx+1}: {mcq['question']}",
            options=mcq['options'],
            type="quiz",
            correct_option_id=mcq['correct'],
            is_anonymous=True
        )
        user_data[poll.poll.id] = mcq

# === Handle User Answers ===
async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    answer = update.poll_answer
    poll_id = answer.poll_id
    user_id = answer.user.id
    username = answer.user.username or answer.user.first_name or "Anonymous"
    selected = answer.option_ids[0]
    if poll_id in user_data:
        mcq = user_data[poll_id]
        correct = mcq['correct']
        is_correct = selected == correct
        score = 1 if is_correct else 0
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.append_row([
            timestamp,
            username,
            str(user_id),
            mcq['question'],
            mcq['options'][selected],
            str(is_correct),
            score
        ])

# === Command: /start (manual trigger) ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=update.message.message_id)
    except:
        pass
    await post_mcqs()

# === Welcome message ===
async def greet_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.chat_member.new_chat_members:
        welcome = (
            f"👋 Welcome *{member.first_name}* to the UPSC MCQ Practice Group!\n\n"
            "🧠 Daily MCQs are posted at *8 AM*.\n"
            "✅ Answer by tapping options.\n"
            "📳 Phone vibrates on correct answers.\n"
            "🏆 Weekly leaderboard is coming soon!"
        )
        await context.bot.send_message(chat_id=update.chat_member.chat.id, text=welcome, parse_mode="Markdown")

# === Schedule Bot Task ===
def run_scheduler():
    schedule.every().day.at("08:00").do(lambda: app.create_task(post_mcqs()))
    while True:
        schedule.run_pending()
        time.sleep(30)

# === Bot Handlers ===
app.add_handler(CommandHandler("start", start))
app.add_handler(PollAnswerHandler(handle_poll_answer))
app.add_handler(ChatMemberHandler(greet_new_member, ChatMemberHandler.CHAT_MEMBER))

if __name__ == '__main__':
    import threading
    threading.Thread(target=run_scheduler).start()
    app.run_polling()
