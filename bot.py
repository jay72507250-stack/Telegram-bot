import sqlite3
import telebot
from telebot import types

# -------------------------------------------------------------
# CONFIGURATION
API_TOKEN = '8505897253:AAExQeMNObtuvJidNxJgU62P27DqYUk7_p0'  # Replace with your BotFather Token
ADMIN_ID = 8505897253              # Replace with your numeric Telegram ID
# -------------------------------------------------------------

bot = telebot.TeleBot(API_TOKEN)

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    name TEXT,
                    age INTEGER,
                    gender TEXT,
                    bio TEXT,
                    photo_id TEXT,
                    is_premium INTEGER DEFAULT 0
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
                    user_id INTEGER,
                    liked_user_id INTEGER,
                    PRIMARY KEY (user_id, liked_user_id)
                )''')
    conn.commit()
    conn.close()

init_db()

# Memory state tracking
user_states = {}
active_chats = {}       # {user1: user2, user2: user1}
waiting_queue = []      # Free random chat queue

def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Find Match", "Instant Chat")
    markup.row("Find by Gender (20 Stars)", "My Profile")
    if user_id == ADMIN_ID:
        markup.row("Admin Panel")
    return markup

# --- START COMMAND ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        bot.send_message(user_id, "Welcome back! Main Menu:", reply_markup=main_keyboard(user_id))
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("Create Profile")
        bot.send_message(user_id, "Welcome to Dating Bot!\n\nClick the button below to setup your profile.", reply_markup=markup)

# --- REGISTRATION ---
@bot.message_handler(func=lambda msg: msg.text == "Create Profile")
def start_registration(message):
    user_id = message.from_user.id
    user_states[user_id] = {'step': 'NAME'}
    bot.send_message(user_id, "Registration started! What is your name?", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') != 'ADMIN_BC')
def registration_flow(message):
    user_id = message.from_user.id
    state = user_states[user_id]['step']

    if state == 'NAME':
        user_states[user_id]['name'] = message.text
        user_states[user_id]['step'] = 'AGE'
        bot.send_message(user_id, "How old are you?")

    elif state == 'AGE':
        if not message.text.isdigit():
            bot.send_message(user_id, "Please enter your age in numbers only (e.g., 21):")
            return
        user_states[user_id]['age'] = int(message.text)
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add("Male", "Female")
        user_states[user_id]['step'] = 'GENDER'
        bot.send_message(user_id, "What is your gender?", reply_markup=markup)

    elif state == 'GENDER':
        user_states[user_id]['gender'] = message.text
        user_states[user_id]['step'] = 'BIO'
        bot.send_message(user_id, "Write a short bio about yourself:", reply_markup=types.ReplyKeyboardRemove())

    elif state == 'BIO':
        user_states[user_id]['bio'] = message.text
        user_states[user_id]['step'] = 'PHOTO'
        bot.send_message(user_id, "Now send a photo of yourself:")

@bot.message_handler(content_types=['photo'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'PHOTO')
def get_photo(message):
    user_id = message.from_user.id
    photo_id = message.photo[-1].file_id
    data = user_states[user_id]
    
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (user_id, name, age, gender, bio, photo_id) VALUES (?, ?, ?, ?, ?, ?)",
              (user_id, data['name'], data['age'], data['gender'], data['bio'], photo_id))
    conn.commit()
    conn.close()
    
    del user_states[user_id]
    bot.send_message(user_id, "Profile saved successfully!", reply_markup=main_keyboard(user_id))

# --- MY PROFILE ---
@bot.message_handler(func=lambda msg: msg.text == "My Profile")
def my_profile(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT name, age, gender, bio, photo_id, is_premium FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    
    if user:
        status = "Premium User" if user[5] == 1 else "Free User"
        caption = f"Name: {user[0]}, Age: {user[1]}\nGender: {user[2]}\nStatus: {status}\nBio: {user[3]}"
        bot.send_photo(user_id, user[4], caption=caption)
    else:
        bot.send_message(user_id, "Please set up your profile first.")

# --- FIND MATCH (LIKE / PASS) ---
@bot.message_handler(func=lambda msg: msg.text == "Find Match")
def find_match(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT user_id, name, age, gender, bio, photo_id FROM users WHERE user_id != ? ORDER BY RANDOM() LIMIT 1", (user_id,))
    target = c.fetchone()
    conn.close()
    
    if not target:
        bot.send_message(user_id, "No profiles available right now! Check back later.")
        return
    
    target_id, name, age, gender, bio, photo_id = target
    caption = f"Profile Card\n\nName: {name}, Age: {age}\nGender: {gender}\nBio: {bio}"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Like ❤️", callback_data=f"like_{target_id}"),
        types.InlineKeyboardButton("Pass ❌", callback_data="pass_next")
    )
    bot.send_photo(user_id, photo_id, caption=caption, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("like_") or call.data == "pass_next")
def match_callbacks(call):
    user_id = call.from_user.id
    if call.data.startswith("like_"):
        liked_id = int(call.data.split("_")[1])
        conn = sqlite3.connect('dating.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO likes VALUES (?, ?)", (user_id, liked_id))
        c.execute("SELECT * FROM likes WHERE user_id = ? AND liked_user_id = ?", (liked_id, user_id))
        mutual = c.fetchone()
        conn.commit()
        conn.close()
        
        bot.answer_callback_query(call.id, "Liked!")
        try:
            bot.send_message(liked_id, "💖 Kisi ne aapki profile Like ki hai!")
        except Exception as e:
            print(e)

        if mutual:
            bot.send_message(user_id, "IT'S A MATCH! 🎉 You both liked each other.")
            bot.send_message(liked_id, "IT'S A MATCH! 🎉 Someone liked you back.")
        find_match(call.message)
    else:
        bot.answer_callback_query(call.id, "Passed")
        find_match(call.message)

# --- INSTANT RANDOM CHAT (FREE) ---
@bot.message_handler(func=lambda msg: msg.text == "Instant Chat")
def instant_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        bot.send_message(user_id, "You are already in an active chat! Tap 'End Chat' to leave.")
        return

    if waiting_queue and waiting_queue[0] != user_id:
        partner_id = waiting_queue.pop(0)
        active_chats[user_id] = partner_id
        active_chats[partner_id] = user_id
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("End Chat")
        
        bot.send_message(user_id, "Connected! You can now chat anonymously with your partner.", reply_markup=markup)
        bot.send_message(partner_id, "Connected! You can now chat anonymously with your partner.", reply_markup=markup)
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
        
        bot.send_message(user_id, "Chat ended successfully.", reply_markup=main_keyboard(user_id))
        bot.send_message(partner_id, "Your partner ended the chat.", reply_markup=main_keyboard(partner_id))
    elif user_id in waiting_queue:
        waiting_queue.remove(user_id)
        bot.send_message(user_id, "Search cancelled.", reply_markup=main_keyboard(user_id))

# --- TELEGRAM STARS PAYMENT (FIND BY GENDER) ---
@bot.message_handler(func=lambda msg: msg.text == "Find by Gender (20 Stars)")
def find_by_gender(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT is_premium FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    conn.close()

    if res and res[0] == 1:
        bot.send_message(user_id, "You are a Premium user! Starting match search...")
        instant_chat(message)
    else:
        # Send Telegram Stars Invoice
        prices = [types.LabeledPrice(label="Premium Gender Search", amount=20)]
        bot.send_invoice(
            user_id,
            title="Unlock Gender Filter",
            description="Pay 20 Telegram Stars to unlock gender-based matching.",
            invoice_payload="gender_premium",
            provider_token="",  # Telegram Stars uses an empty provider token
            currency="XTR",
            prices=prices
        )

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(query):
    bot.answer_pre_checkout_query(query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_payment(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_premium = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    
    bot.send_message(user_id, "Payment Successful! Premium features unlocked 🎉", reply_markup=main_keyboard(user_id))

# --- ADMIN PANEL ---
@bot.message_handler(func=lambda msg: msg.text == "Admin Panel" and msg.from_user.id == ADMIN_ID)
def admin_panel(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("Bot Stats", "Broadcast Message")
    markup.row("Back to Menu")
    bot.send_message(message.chat.id, "Welcome Admin! Select an option:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "Bot Stats" and msg.from_user.id == ADMIN_ID)
def bot_stats(message):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE is_premium = 1")
    premium_users = c.fetchone()[0]
    conn.close()
    
    stats_msg = f"--- BOT STATS ---\nTotal Users: {total_users}\nPremium Users: {premium_users}"
    bot.send_message(ADMIN_ID, stats_msg)

@bot.message_handler(func=lambda msg: msg.text == "Broadcast Message" and msg.from_user.id == ADMIN_ID)
def ask_broadcast(message):
    user_states[ADMIN_ID] = {'step': 'ADMIN_BC'}
    bot.send_message(ADMIN_ID, "Type the message you want to broadcast to all users:")

@bot.message_handler(func=lambda msg: msg.from_user.id == ADMIN_ID and user_states.get(ADMIN_ID, {}).get('step') == 'ADMIN_BC')
def send_broadcast(message):
    text_to_send = message.text
    del user_states[ADMIN_ID]
    
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    all_users = c.fetchall()
    conn.close()
    
    count = 0
    for u in all_users:
        try:
            bot.send_message(u[0], f"[Announcement]\n\n{text_to_send}")
            count += 1
        except:
            pass
    
    bot.send_message(ADMIN_ID, f"Broadcast complete! Message sent to {count} users.", reply_markup=main_keyboard(ADMIN_ID))

@bot.message_handler(func=lambda msg: msg.text == "Back to Menu")
def back_menu(message):
    bot.send_message(message.chat.id, "Main Menu:", reply_markup=main_keyboard(message.from_user.id))

# --- LIVE RELAY CHAT MESSAGES ---
@bot.message_handler(func=lambda msg: msg.from_user.id in active_chats)
def relay_messages(message):
    partner_id = active_chats[message.from_user.id]
    if message.text:
        bot.send_message(partner_id, message.text)
    elif message.photo:
        bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)

print("Bot is running...")
bot.infinity_polling()

