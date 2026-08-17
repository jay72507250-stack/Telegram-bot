import telebot
from telebot import types
import sqlite3
import datetime

# ⚠️ YAHAN APNA TELEGRAM BOT TOKEN DAALO
API_TOKEN = '8505897253:AAGliSrXAa2nh-TzIEMdAm8sR2UcWnbt1dI'
bot = telebot.TeleBot(API_TOKEN)

ADMIN_ID = 8310681464  # Aapki Admin User ID

# --- DATABASE SETUP (NO DUMMY PROFILES) ---
def init_db():
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, gender TEXT, city TEXT, bio TEXT, photo_id TEXT, username TEXT, is_vip INTEGER DEFAULT 0, vip_expiry TEXT, referrer_id INTEGER, is_verified INTEGER DEFAULT 0)''')
    
    for col in [("city", "TEXT"), ("vip_expiry", "TEXT"), ("referrer_id", "INTEGER"), ("is_verified", "INTEGER DEFAULT 0")]:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col[0]} {col[1]}")
        except:
            pass

    c.execute('''CREATE TABLE IF NOT EXISTS swipes 
                 (user_id INTEGER, target_id INTEGER, action TEXT, UNIQUE(user_id, target_id))''')

    # Delete existing fake profiles if any
    c.execute("DELETE FROM users WHERE user_id >= 9990")

    conn.commit()
    conn.close()

init_db()

user_states = {}
active_chats = {}
waiting_queue = []

# --- HELPER FUNCTIONS ---
def check_vip_status(user_id):
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT is_vip, vip_expiry FROM users WHERE user_id = ?", (user_id,))
    res = c.fetchone()
    if res and res[0] == 1:
        if res[1]:
            try:
                expiry_date = datetime.datetime.strptime(res[1], "%Y-%m-%d")
                if datetime.datetime.now() > expiry_date:
                    c.execute("UPDATE users SET is_vip = 0 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    conn.close()
                    return 0
            except:
                pass
        conn.close()
        return 1
    conn.close()
    return 0

def main_keyboard(user_id):
    is_vip = check_vip_status(user_id)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔥 Find Match", "💬 Instant Chat")
    markup.row("👤 My Profile", "🎁 Invite & Earn VIP")
    if not is_vip:
        markup.row("⭐ Buy Premium VIP (20 Stars)")
    return markup

# --- REGISTRATION FLOW ---
@bot.message_handler(commands=['start'])
def start_cmd(message):
    user_id = message.from_user.id
    args = message.text.split()
    referrer = int(args[1].replace('ref_', '')) if len(args) > 1 and args[1].startswith('ref_') else None

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        bot.send_message(user_id, "Welcome back! Choose an option:", reply_markup=main_keyboard(user_id))
    else:
        user_states[user_id] = {'step': 'NAME', 'referrer': referrer}
        bot.send_message(user_id, "Welcome to Dating Bot! 🎉\n\nWhat is your Name?", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda msg: msg.from_user.id in user_states)
def registration_flow(message):
    user_id = message.from_user.id
    step = user_states[user_id].get('step')

    if step == 'NAME':
        user_states[user_id]['name'] = message.text
        user_states[user_id]['step'] = 'AGE'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("18", "19", "20", "21")
        markup.row("22", "23", "24", "25")
        bot.send_message(user_id, "Select or Type your Age:", reply_markup=markup)

    elif step == 'AGE':
        if not message.text.isdigit():
            bot.send_message(user_id, "Please select or enter a valid age in numbers:")
            return
        user_states[user_id]['age'] = int(message.text)
        user_states[user_id]['step'] = 'GENDER'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("👨 Male", "👩 Female")
        bot.send_message(user_id, "Select your Gender:", reply_markup=markup)

    elif step == 'GENDER':
        gender_text = "Male" if "Male" in message.text else "Female"
        user_states[user_id]['gender'] = gender_text
        user_states[user_id]['step'] = 'CITY'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("Mumbai", "Delhi", "Ahmedabad", "Rajkot")
        markup.row("Bangalore", "Pune", "Surat", "Jaipur")
        bot.send_message(user_id, "Select or type your City:", reply_markup=markup)

    elif step == 'CITY':
        user_states[user_id]['city'] = message.text
        user_states[user_id]['step'] = 'BIO'
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.row("⏩ Skip Bio")
        bot.send_message(user_id, "Write a short Bio about yourself (or click Skip):", reply_markup=markup)

    elif step == 'BIO':
        bio = "" if message.text == "⏩ Skip Bio" else message.text
        user_states[user_id]['bio'] = bio
        user_states[user_id]['step'] = 'PHOTO'
        bot.send_message(user_id, "Now send a Photo of yourself:", reply_markup=types.ReplyKeyboardRemove())

# --- PHOTO & DOCUMENT HANDLER (FIXED) ---
@bot.message_handler(content_types=['photo', 'document'], func=lambda msg: msg.from_user.id in user_states and user_states[msg.from_user.id].get('step') == 'PHOTO')
def get_photo(message):
    user_id = message.from_user.id
    
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
        photo_id = message.document.file_id
    else:
        bot.send_message(user_id, "⚠️ Please send a valid Image/Photo file!")
        return

    data = user_states[user_id]
    username = message.from_user.username or ""

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO users (user_id, name, age, gender, city, bio, photo_id, username, is_vip, referrer_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
    """, (user_id, data['name'], data['age'], data['gender'], data['city'], data['bio'], photo_id, username, data.get('referrer')))
    
    if data.get('referrer'):
        ref_id = data['referrer']
        c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (ref_id,))
        ref_count = c.fetchone()[0]
        if ref_count >= 3:
            expiry = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            c.execute("UPDATE users SET is_vip = 1, vip_expiry = ? WHERE user_id = ?", (expiry, ref_id))
            try:
                bot.send_message(ref_id, "🎉 Congratulations! You referred 3 friends and unlocked 1 Month FREE VIP Pass! ⭐")
            except:
                pass

    conn.commit()
    conn.close()

    del user_states[user_id]
    bot.send_message(user_id, "Profile created successfully! 🎉", reply_markup=main_keyboard(user_id))

# --- VIP STARS PAYMENT ---
@bot.message_handler(func=lambda msg: msg.text in ["⭐ Buy Premium VIP", "⭐ Buy Premium VIP (20 Stars)"])
def send_stars_invoice(message):
    prices = [types.LabeledPrice(label="VIP Membership (1 Month)", amount=20)]
    bot.send_invoice(
        message.chat.id,
        title="⭐ VIP Premium Pass (1 Month)",
        description="Unlimited Swiping, Priority Matching & VIP Badge for 30 Days!",
        invoice_payload="vip_subscription_payload",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="vip-membership"
    )

@bot.pre_checkout_query_handler(func=lambda query: True)
def process_pre_checkout(pre_checkout_query):
    bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def process_successful_payment(message):
    user_id = message.from_user.id
    expiry = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("UPDATE users SET is_vip = 1, vip_expiry = ? WHERE user_id = ?", (expiry, user_id))
    conn.commit()
    conn.close()
    bot.send_message(user_id, "🎉 Payment Successful! You are now a ⭐ VIP Member for 30 Days!", reply_markup=main_keyboard(user_id))

# --- REFERRAL SYSTEM ---
@bot.message_handler(func=lambda msg: msg.text == "🎁 Invite & Earn VIP")
def invite_earn(message):
    user_id = message.from_user.id
    bot_name = bot.get_me().username
    ref_link = f"https://t.me/{bot_name}?start=ref_{user_id}"
    
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()

    msg = f"🎁 **Invite & Earn Free VIP!**\n\nInvite 3 friends to get **1 Month Free VIP Pass**!\n\nYour Referral Count: **{count}/3**\nYour Referral Link:\n`{ref_link}`"
    bot.send_message(user_id, msg, parse_mode="Markdown")

# --- MY PROFILE ---
@bot.message_handler(func=lambda msg: msg.text == "👤 My Profile")
def my_profile(message):
    user_id = message.from_user.id
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT name, age, gender, city, bio, photo_id, is_vip, is_verified FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        is_vip = check_vip_status(user_id)
        badge = "👑 [VIP MEMBER]" if is_vip == 1 else "🆓 [FREE USER]"
        v_badge = "🔵 Verified" if user[7] == 1 else ""
        caption = f"{badge} {v_badge}\n\n👤 Name: {user[0]}, Age: {user[1]}\n📍 City: {user[3]}\nGender: {user[2]}\nBio: {user[4]}"
        bot.send_photo(user_id, user[5], caption=caption)

# --- MATCHING SYSTEM (ONLY REAL USERS & 20 SWIPE LIMIT) ---
def find_match(chat_id):
    is_vip = check_vip_status(chat_id)

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM swipes WHERE user_id = ?", (chat_id,))
    swipe_count = c.fetchone()[0]

    if not is_vip and swipe_count >= 20:
        conn.close()
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row("⭐ Buy Premium VIP (20 Stars)")
        markup.row("🎁 Invite & Earn VIP", "👤 My Profile")
        bot.send_message(
            chat_id, 
            "⚠️ **Daily Profile Limit Reached!**\n\nAapne apne free 20 profiles dekh liye hain. VIP Membership kharidein ya 3 Dosto ko Invite karke Free VIP unlock karein! ⭐", 
            reply_markup=markup,
            parse_mode="Markdown"
        )
        return

    c.execute("SELECT city FROM users WHERE user_id = ?", (chat_id,))
    u_city = c.fetchone()
    user_city = u_city[0] if u_city else ""

    c.execute("""
        SELECT user_id, name, age, gender, city, bio, photo_id, is_vip, is_verified FROM users 
        WHERE user_id IN (SELECT user_id FROM swipes WHERE target_id = ? AND action = 'like')
        AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = ?)
        LIMIT 1
    """, (chat_id, chat_id))
    target = c.fetchone()

    if not target:
        c.execute("""
            SELECT user_id, name, age, gender, city, bio, photo_id, is_vip, is_verified FROM users 
            WHERE user_id != ? AND city = ?
            AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = ?)
            ORDER BY RANDOM() LIMIT 1
        """, (chat_id, user_city, chat_id))
        target = c.fetchone()

    if not target:
        c.execute("""
            SELECT user_id, name, age, gender, city, bio, photo_id, is_vip, is_verified FROM users 
            WHERE user_id != ?
            AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = ?)
            ORDER BY RANDOM() LIMIT 1
        """, (chat_id, chat_id))
        target = c.fetchone()

    conn.close()

    if not target:
        bot.send_message(chat_id, "Abhi koi naye real profiles nahi hain! Thodi der me try karein.")
        return

    target_id, name, age, gender, city, bio, photo_id, is_vip_target, is_verified = target
    badge = "👑 VIP User" if is_vip_target == 1 else ""
    v_badge = "🔵 Verified" if is_verified == 1 else ""
    caption = f"🔥 Profile Card {badge} {v_badge}\n\nName: {name}, Age: {age}\n📍 City: {city}\nGender: {gender}\nBio: {bio}"
    
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("Like ❤️", callback_data=f"like_{target_id}"),
        types.InlineKeyboardButton("Pass ❌", callback_data=f"pass_{target_id}")
    )
    markup.row(types.InlineKeyboardButton("🚩 Report", callback_data=f"report_{target_id}"))
    bot.send_photo(chat_id, photo_id, caption=caption, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🔥 Find Match")
def find_match_handler(message):
    find_match(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(("like_", "pass_", "report_")))
def match_callbacks(call):
    user_id = call.from_user.id
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except:
        pass

    action_type = call.data.split("_")[0]
    target_id = int(call.data.split("_")[1])

    if action_type == "report":
        bot.answer_callback_query(call.id, "Report submitted!")
        find_match(user_id)
        return

    action = "like" if action_type == "like" else "pass"

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

# --- INSTANT CHAT ---
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

        bot.send_message(user_id, "Connected with a real partner! Say hi 👋", reply_markup=markup)
        bot.send_message(partner_id, "Connected with a real partner! Say hi 👋", reply_markup=markup)
    else:
        if user_id not in waiting_queue:
            waiting_queue.append(user_id)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🚫 End Chat")
        bot.send_message(user_id, "Searching for a partner... Please wait ⏳", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == "🚫 End Chat")
def end_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)
        bot.send_message(partner_id, "Partner ended the chat.", reply_markup=main_keyboard(partner_id))
        bot.send_message(user_id, "Chat ended successfully.", reply_markup=main_keyboard(user_id))
    elif user_id in waiting_queue:
        waiting_queue.remove(user_id)
        bot.send_message(user_id, "Stopped searching.", reply_markup=main_keyboard(user_id))
    else:
        bot.send_message(user_id, "You are not in any chat.", reply_markup=main_keyboard(user_id))

@bot.message_handler(func=lambda msg: msg.from_user.id in active_chats)
def relay_message(message):
    user_id = message.from_user.id
    partner_id = active_chats[user_id]

    if message.text:
        bot.send_message(partner_id, message.text)
    elif message.photo:
        bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)

bot.infinity_polling()

