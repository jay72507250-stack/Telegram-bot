import telebot
from telebot import types
import sqlite3

# ⚠️ YAHAN APNA ORIGINAL BOT TOKEN DAALO
API_TOKEN = '8505897253:AAGliSrXAa2nh-TzIEMdAm8sR2UcWnbt1dI'
bot = telebot.TeleBot(API_TOKEN)

ADMIN_ID = 8310681464  # Aapki Admin Telegram User ID

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, gender TEXT, bio TEXT, photo_id TEXT, username TEXT, is_vip INTEGER DEFAULT 0)''')
    try:
        c.execute("ALTER TABLE users ADD COLUMN username TEXT")
    except:
        pass
    try:
        c.execute("ALTER TABLE users ADD COLUMN is_vip INTEGER DEFAULT 0")
    except:
        pass

    c.execute('''CREATE TABLE IF NOT EXISTS swipes 
                 (user_id INTEGER, target_id INTEGER, action TEXT, UNIQUE(user_id, target_id))''')
    conn.commit()
    conn.close()

init_db()

user_states = {}
active_chats = {}
waiting_queue = []

def main_keyboard(user_id):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT is_vip FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()
    
    is_vip = res[0] if res else 0

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔥 Find Match", "💬 Instant Chat")
    markup.row("👤 My Profile", "✏️ Edit Profile")
    if not is_vip:
        markup.row("⭐ Buy Premium VIP (20 Stars)")
    return markup

# --- ADMIN COMMAND TO MANUAL VIP ---
@bot.message_handler(commands=['addvip'])
def add_vip_cmd(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        target_user = int(message.text.split()[1])
        conn = sqlite3.connect('dating.db')
        c = conn.cursor()
        c.execute("UPDATE users SET is_vip = 1 WHERE user_id = ?", (target_user,))
        conn.commit()
        conn.close()
        bot.send_message(message.chat.id, f"✅ User {target_user} is now VIP!")
        bot.send_message(target_user, "🎉 Congratulations! You have been upgraded to VIP Member!")
    except Exception:
        bot.send_message(message.chat.id, "Usage: /addvip USER_ID")

# --- REGISTRATION & START ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        bot.send_message(user_id, "Welcome back! Choose an option:", reply_markup=main_keyboard(user_id))
    else:
        user_states[user_id] = {'step': 'NAME'}
        bot.send_message(user_id, "Welcome to the Dating & Chat Bot! 🎉\n\nWhat is your Name?")

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states)
def registration_flow(message):
    user_id = message.from_user.id
    step = user_states[user_id].get('step')

    if step == 'NAME':
        user_states[user_id]['name'] = message.text
        user_states[user_id]['step'] = 'AGE'
        bot.send_message(user_id, "Enter your Age (in numbers):")
    elif step == 'AGE':
        if not message.text.isdigit():
            bot.send_message(user_id, "Please enter a valid number:")
            return
        user_states[user_id]['age'] = int(message.text)
        user_states[user_id]['step'] = 'GENDER'
        bot.send_message(user_id, "Enter your Gender (e.g., Male / Female):")
    elif step == 'GENDER':
        user_states[user_id]['gender'] = message.text
        user_states[user_id]['step'] = 'BIO'
        bot.send_message(user_id, "Write a short Bio about yourself:")
    elif step == 'BIO':
        user_states[user_id]['bio'] = message.text
        user_states[user_id]['step'] = 'PHOTO'
        bot.send_message(user_id, "Now send a Photo of yourself:")

@bot.message_handler(content_types=['photo'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'PHOTO')
def get_photo(message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    data = user_states[user_id]
    username = message.from_user.username or ""

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO users (user_id, name, age, gender, bio, photo_id, username, is_vip)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0)
    """, (user_id, data['name'], data['age'], data['gender'], data['bio'], photo_id, username))
    conn.commit()
    conn.close()

    del user_states[user_id]
    bot.send_message(user_id, "Profile created successfully! 🎉", reply_markup=main_keyboard(user_id))

# --- TELEGRAM STARS PAYMENT SYSTEM ---
@bot.message_handler(func=lambda msg: msg.text in ["⭐ Buy Premium VIP", "⭐ Buy Premium VIP (20 Stars)"])
def send_stars_invoice(message):
    prices = [types.LabeledPrice(label="VIP Membership (1 Month)", amount=20)]
    bot.send_invoice(
        message.chat.id,
        title="⭐ VIP Premium Pass",
        description="Unlock VIP Crown Badge, Unlimited Swiping, and Direct Matches Access!",
        invoice_payload="vip_subscription_payload",
        provider_token="",  # Telegram Stars ke liye token empty rehta hai
        currency="XTR",     # XTR is the currency code for Telegram Stars
        prices=prices,
        start_parameter="vip-membership"
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_vip = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    bot.send_message(
        user_id,
        "🎉 Payment Successful!\n\nCongratulations, you are now a ⭐ VIP Member! Enjoy your premium perks.",
        reply_markup=main_keyboard(user_id)
    )

# --- MY PROFILE ---
@bot.message_handler(func=lambda msg: msg.text in ["👤 My Profile", "✏️ Edit Profile"])
def my_profile(message):
    user_id = message.from_user.id
    if message.text == "✏️ Edit Profile":
        user_states[user_id] = {'step': 'NAME'}
        bot.send_message(user_id, "Let's update your profile!\nEnter your Name:")
        return

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT name, age, gender, bio, photo_id, is_vip FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        badge = "👑 [VIP MEMBER]" if user[5] == 1 else "🆓 [FREE USER]"
        caption = f"{badge}\n\n👤 Name: {user[0]}, Age: {user[1]}\nGender: {user[2]}\nBio: {user[3]}"
        bot.send_photo(user_id, user[4], caption=caption)
    else:
        bot.send_message(user_id, "Type /start to set up your profile.")

# --- MATCHING SYSTEM ---
def find_match(chat_id):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("""
        SELECT user_id, name, age, gender, bio, photo_id, username, is_vip FROM users 
        WHERE user_id != ? 
        AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = ?)
        ORDER BY RANDOM() LIMIT 1
    """, (chat_id, chat_id))
    target = c.fetchone()
    conn.close()

    if not target:
        bot.send_message(chat_id, "No more new profiles right now! Check back later.")
        return

    target_id, name, age, gender, bio, photo_id, username, is_vip = target
    badge = "👑 VIP User" if is_vip == 1 else ""
    caption = f"🔥 Profile Card {badge}\n\nName: {name}, Age: {age}\nGender: {gender}\nBio: {bio}"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Like ❤️", callback_data=f"like_{target_id}"),
        types.InlineKeyboardButton("Pass ❌", callback_data=f"pass_{target_id}")
    )
    bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🔥 Find Match")
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
                bot.send_message(target_id, "💖 Someone liked your profile! Click 'Find Match' to explore profiles.")
            except:
                pass
    else:
        bot.answer_callback_query(call.id, "Passed")

    conn.close()
    find_match(user_id)

# --- INSTANT RANDOM CHAT ---
@bot.message_handler(func=lambda msg: msg.text == "💬 Instant Chat")
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
        markup.add("🚫 End Chat")

        bot.send_message(user_id, "Connected! You can now chat anonymously.", reply_markup=markup)
        bot.send_message(partner_id, "Connected! You can now chat anonymously.", reply_markup=markup)
    else:
        if user_id not in waiting_queue:
            waiting_queue.append(user_id)
        bot.send_message(user_id, "Searching for a partner... Please wait.")

@bot.message_handler(func=lambda msg: msg.text == "🚫 End Chat")
def end_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)

        bot.send_message(user_id, "Chat ended successfully.", reply_markup=main_keyboard(user_id))
        bot.send_message(partner_id, "Partner ended the chat.", reply_markup=main_keyboard(partner_id))
    elif user_id in waiting_queue:
        waiting_queue.remove(user_id)
        bot.send_message(user_id, "Stopped searching.", reply_markup=main_keyboard(user_id))
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

bot.infinity_polling()

