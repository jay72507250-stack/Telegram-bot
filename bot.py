import telebot
from telebot import types
import sqlite3

# ⚠️ YAHAN APNA BOT TOKEN REPLACE KARO
API_TOKEN = '8505897253:AAH9mpVj6H5C8OSMtsvhl1UzHuEwJeVBKn4'
bot = telebot.TeleBot(API_TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, gender TEXT, bio TEXT, photo_id TEXT, username TEXT)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except:
        pass
    c.execute('''CREATE TABLE IF NOT EXISTS swipes 
                 (user_id INTEGER, target_id INTEGER, action TEXT, UNIQUE(user_id, target_id))''')
    conn.commit()
    conn.close()

init_db()

# Global variables
user_states = {}
active_chats = {}
waiting_queue = []

def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Find Match", "Instant Chat")
    markup.row("My Profile", "Edit Profile")
    return markup

# --- START & PROFILE REGISTRATION ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    if is_blocked(user_id):
        bot.send_message(user_id, "🚫 Aapko block kar diya gaya hai.")
        return
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        bot.send_message(user_id, "Welcome back!", reply_markup=main_keyboard())
    else:
        user_states[user_id] = {'step': 'NAME'}
        bot.send_message(user_id, "Welcome! Let's set up your profile.\n\nPlease enter your Name:")

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states)
def registration_flow(message):
    user_id = message.from_user.id
    step = user_states[user_id].get('step')

    if step == 'NAME':
        user_states[user_id]['name'] = message.text
        user_states[user_id]['step'] = 'AGE'
        bot.send_message(user_id, "Great! Now enter your Age:")
    elif step == 'AGE':
        if not message.text.isdigit():
            bot.send_message(user_id, "Please enter a valid number for Age:")
            return
        user_states[user_id]['age'] = int(message.text)
        user_states[user_id]['step'] = 'GENDER'
        bot.send_message(user_id, "Enter your Gender (e.g., Male/Female):")
    elif step == 'GENDER':
        user_states[user_id]['gender'] = message.text
        user_states[user_id]['step'] = 'BIO'
        bot.send_message(user_id, "Write a short Bio about yourself:")
    elif step == 'BIO':
        user_states[user_id]['bio'] = message.text
        user_states[user_id]['step'] = 'PHOTO'
        bot.send_message(user_id, "Now send a photo of yourself:")

@bot.message_handler(content_types=['photo'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'PHOTO')
def get_photo(message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    data = user_states[user_id]
    username = message.from_user.username or ""

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO users (user_id, name, age, gender, bio, photo_id, username)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, data['name'], data['age'], data['gender'], data['bio'], photo_id, username))
    conn.commit()
    conn.close()

    del user_states[user_id]
    bot.send_message(user_id, "Profile saved successfully! 🎉", reply_markup=main_keyboard())

# --- MY PROFILE ---
@bot.message_handler(func=lambda msg: msg.text in ["My Profile", "Edit Profile"])
def my_profile(message):
    user_id = message.from_user.id
    if message.text == "Edit Profile":
        user_states[user_id] = {'step': 'NAME'}
        bot.send_message(user_id, "Let's update your profile!\n\nPlease enter your Name:")
        return

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT name, age, gender, bio, photo_id FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        caption = f"👤 Your Profile\n\nName: {user[0]}, Age: {user[1]}\nGender: {user[2]}\nBio: {user[3]}"
        bot.send_photo(user_id, user[4], caption=caption)
    else:
        bot.send_message(user_id, "Please set up your profile first by typing /start")

# --- FIND MATCH ---
def find_match(chat_id):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("""
        SELECT user_id, name, age, gender, bio, photo_id, username FROM users 
        WHERE user_id != ? 
        AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = ?)
        ORDER BY RANDOM() LIMIT 1
    """, (chat_id, chat_id))
    target = c.fetchone()
    conn.close()

    if not target:
        bot.send_message(chat_id, "No more new profiles right now! Try again later.")
        return

    target_id, name, age, gender, bio, photo_id, username = target
    caption = f"🔥 Profile Card\n\nName: {name}, Age: {age}\nGender: {gender}\nBio: {bio}"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Like ❤️", callback_data=f"like_{target_id}"),
        types.InlineKeyboardButton("Pass ❌", callback_data=f"pass_{target_id}")
    )
    bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "Find Match")
def find_match_handler(message):
    find_match(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("like_", "pass_")))
def match_callbacks(call):
    user_id = call.from_user.id
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    target_id = int(call.data.split("_")[1])
    action = "like" if call.data.startswith("like_") else "pass"

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO swipes VALUES (?, ?, ?)", (user_id, target_id, action))
    conn.commit()

    if action == "like":
        bot.answer_callback_query(call.id, "Liked!")
        c.execute("SELECT * FROM swipes WHERE user_id = ? AND target_id = ? AND action = 'like'", (target_id, user_id))
        mutual = c.fetchone()
        
        if mutual:
            c.execute("SELECT name, username FROM users WHERE user_id = ?", (target_id,))
            target_info = c.fetchone()
            target_name = target_info[0] if target_info else "Partner"
            target_uname = target_info[1] if target_info and target_info[1] else None

            user_link = f"@{target_uname}" if target_uname else f"tg://user?id={target_id}"
            bot.send_message(user_id, f"🎉 IT'S A MATCH!\n\nYou matched with {target_name}.\n💬 Start Chat: {user_link}")

            my_link = f"@{call.from_user.username}" if call.from_user.username else f"tg://user?id={user_id}"
            bot.send_message(target_id, f"🎉 IT'S A MATCH!\n\nSomeone matched with you!\n💬 Start Chat: {my_link}")
        else:
            try:
                bot.send_message(target_id, "💖 Someone liked your profile! Click 'Find Match' to see profiles.")
            except:
                pass
    else:
        bot.answer_callback_query(call.id, "Passed")

    conn.close()
    find_match(user_id)

# --- INSTANT RANDOM CHAT ---
@bot.message_handler(func=lambda msg: msg.text == "Instant Chat")
def instant_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        bot.send_message(user_id, "You are already in an active chat!")
        return

    if waiting_queue and waiting_queue[0] != user_id:
        partner_id = waiting_queue.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("End Chat")

        bot.send_message(user_id, "Connected! You can now chat anonymously.", reply_markup=markup)
        bot.send_message(partner_id, "Connected! You can now chat anonymously.", reply_markup=markup)
    else:
        if user_id not in waiting_queue:
            waiting_queue.append(user_id)
        bot.send_message(user_id, "Searching for a partner... Please wait.")

@bot.message_handler(func=lambda msg: msg.text == "End Chat")
def end_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)

        bot.send_message(user_id, "Chat ended successfully.", reply_markup=main_keyboard())
        bot.send_message(partner_id, "Partner ended the chat.", reply_markup=main_keyboard())
    elif user_id in waiting_queue:
        waiting_queue.remove(user_id)
        bot.send_message(user_id, "Stopped searching.", reply_markup=main_keyboard())
    else:
        bot.send_message(user_id, "You are not in any chat.")

@bot.message_handler(func=lambda msg: msg.from_user.id in active_chats)
def relay_message(message):
    user_id = message.from_user.id
    partner_id = active_chats[user_id]
    if message.text:
        bot.send_message(partner_id, message.text)
    elif message.photo:
        bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
 =========================================================
# PASTE EVERYTHING BELOW THIS LINE INTO YOUR bot.py
# — insert it right BEFORE the line: bot.infinity_polling()
# =========================================================

ADMIN_IDS = {8310681464}          # your Telegram ID — only this ID can use admin commands
PREMIUM_STARS_PRICE = 20          # cost in Telegram Stars

# --- one-time DB upgrade: add block/premium columns if missing ---
def upgrade_db():
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_blocked INTEGER DEFAULT 0")
    except:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_premium INTEGER DEFAULT 0")
    except:
        pass
    conn.commit()
    conn.close()

upgrade_db()

def is_blocked(user_id):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT is_blocked FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return bool(row and row[0])

def is_admin(user_id):
    return user_id in ADMIN_IDS

# --- ADMIN COMMANDS ---
@bot.message_handler(commands=['block'])
def block_user(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Usage: /block <user_id>")
        return
    target = int(parts[1])
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked=1 WHERE user_id=?", (target,))
    if c.rowcount == 0:
        c.execute("INSERT INTO users (user_id, is_blocked) VALUES (?, 1)", (target,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ User {target} block kar diya gaya.")

@bot.message_handler(commands=['unblock'])
def unblock_user(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "Usage: /unblock <user_id>")
        return
    target = int(parts[1])
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_blocked=0 WHERE user_id=?", (target,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, f"✅ User {target} unblock kar diya gaya.")

@bot.message_handler(commands=['users'])
def list_users(message):
    if not is_admin(message.from_user.id):
        return
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT user_id, name, is_blocked FROM users ORDER BY user_id DESC LIMIT 30")
    rows = c.fetchall()
    conn.close()
    if not rows:
        bot.send_message(message.chat.id, "Koi users nahi hain.")
        return
    lines = [f"{r[0]} - {r[1]} {'🚫' if r[2] else ''}" for r in rows]
    bot.send_message(message.chat.id, "Latest Users:\n" + "\n".join(lines))

@bot.message_handler(commands=['stats'])
def stats(message):
    if not is_admin(message.from_user.id):
        return
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_blocked=1")
    blocked = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_premium=1")
    premium = c.fetchone()[0]
    conn.close()
    bot.send_message(message.chat.id, f"📊 Bot Stats\nTotal Users: {total}\nPremium: {premium}\nBlocked: {blocked}")

# --- PREMIUM (Telegram Stars) ---
@bot.message_handler(commands=['premium'])
@bot.message_handler(func=lambda msg: msg.text == "Premium")
def premium(message):
    bot.send_invoice(
        message.chat.id,
        title="Premium Membership",
        description="Unlimited likes aur profile boost unlock karein.",
        invoice_payload="premium_upgrade",
        provider_token="",        # Stars payments need no provider token
        currency="XTR",           # XTR = Telegram Stars
        prices=[types.LabeledPrice("Premium Membership", PREMIUM_STARS_PRICE)],
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def got_payment(message):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_premium=1 WHERE user_id=?", (message.from_user.id,))
    conn.commit()
    conn.close()
    bot.send_message(message.chat.id, "🎉 Payment successful! Aap ab Premium member hain.")
    # Stars auto-credit to your bot's balance —
    # withdraw via @BotFather > My Bots > Bot Settings > Star Balance

# =========================================================
# END OF PATCH
# ===================================
bot.infinity_polling()

