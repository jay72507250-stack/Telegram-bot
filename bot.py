import telebot
from telebot import types
import sqlite3
import datetime
import traceback

# ⚠️ ENTER YOUR TELEGRAM BOT TOKEN HERE
API_TOKEN = '8505897253:AAGliSrXAa2nh-TzIEMdAm8sR2UcWnbt1dI'
bot = telebot.TeleBot(API_TOKEN)

ADMIN_ID = 8310681464

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, name TEXT, age INTEGER, gender TEXT, city TEXT, bio TEXT, photo_id TEXT, username TEXT, is_vip INTEGER DEFAULT 0, vip_expiry TEXT, referrer_id INTEGER, is_verified INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS user_states 
                 (user_id INTEGER PRIMARY KEY, step TEXT, name TEXT, age INTEGER, gender TEXT, city TEXT, bio TEXT, referrer_id INTEGER)''')

    c.execute('''CREATE TABLE IF NOT EXISTS swipes 
                 (user_id INTEGER, target_id INTEGER, action TEXT, UNIQUE(user_id, target_id))''')

    columns = ["city TEXT", "vip_expiry TEXT", "referrer_id INTEGER", "is_verified INTEGER DEFAULT 0", "username TEXT", "is_vip INTEGER DEFAULT 0"]
    for col in columns:
        try:
            c.execute(f"ALTER TABLE users ADD COLUMN {col}")
        except:
            pass

    c.execute("DELETE FROM users WHERE user_id >= 9990")
    conn.commit()
    conn.close()

init_db()

# State memory for instant chat filters: {user_id: 'Female'/'Male'/'Any'}
chat_gender_pref = {}
active_chats = {}
waiting_queue = {'Male': [], 'Female': [], 'Any': []}

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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("🔥 Find Match", "💬 Instant Chat")
    markup.row("👤 My Profile", "✏️ Edit Profile")
    markup.row("🎁 Invite Friends", "⭐ Buy VIP Pass")
    return markup

def match_filter_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("👩 Match with Girls (⭐ VIP)", "👨 Match with Boys (⭐ VIP)")
    markup.row("🔀 Match Randomly (🆓 Free)")
    markup.row("🔙 Main Menu")
    return markup

def chat_filter_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    markup.row("👩 Chat with Girls (⭐ VIP)", "👨 Chat with Boys (⭐ VIP)")
    markup.row("🔀 Chat Randomly (🆓 Free)")
    markup.row("🔙 Main Menu")
    return markup

# --- REGISTRATION / RESET START ---
@bot.message_handler(commands=['start', 'reset'])
def start_cmd(message):
    user_id = message.from_user.id
    args = message.text.split()
    referrer = int(args[1].replace('ref_', '')) if len(args) > 1 and args[1].startswith('ref_') else None

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    
    if message.text.startswith('/reset'):
        c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "🔄 Profile reset! What is your Name?", reply_markup=types.ReplyKeyboardRemove())
        
        conn = sqlite3.connect('dating.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_states (user_id, step, referrer_id) VALUES (?, 'NAME', ?)", (user_id, referrer))
        conn.commit()
        conn.close()
        return

    c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = c.fetchone()
    
    if user:
        conn.close()
        bot.send_message(user_id, "Welcome back! Choose an option:", reply_markup=main_keyboard(user_id))
    else:
        c.execute("INSERT OR REPLACE INTO user_states (user_id, step, referrer_id) VALUES (?, 'NAME', ?)", (user_id, referrer))
        conn.commit()
        conn.close()
        bot.send_message(user_id, "Welcome to Dating Bot! 🎉\n\nWhat is your Name?", reply_markup=types.ReplyKeyboardRemove())

# --- PHOTO HANDLER ---
@bot.message_handler(content_types=['photo', 'document'])
def handle_photo(message):
    user_id = message.from_user.id

    if user_id in active_chats:
        partner_id = active_chats[user_id]
        if message.photo:
            bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
        return

    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT step, name, age, gender, city, bio, referrer_id FROM user_states WHERE user_id = ?", (user_id,))
    state = c.fetchone()

    if not state or state[0] != 'PHOTO':
        conn.close()
        bot.send_message(user_id, "⚠️ Please select an option from the menu or type /reset.")
        return

    try:
        photo_id = None
        if message.photo:
            photo_id = message.photo[-1].file_id
        elif message.document and message.document.mime_type and message.document.mime_type.startswith('image/'):
            photo_id = message.document.file_id
        else:
            conn.close()
            bot.send_message(user_id, "⚠️ Please send a valid photo file!")
            return

        username = message.from_user.username or ""
        _, name, age, gender, city, bio, referrer_id = state

        c.execute("""
            INSERT OR REPLACE INTO users (user_id, name, age, gender, city, bio, photo_id, username, is_vip, referrer_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """, (user_id, name, age, gender, city, bio, photo_id, username, referrer_id))

        c.execute("DELETE FROM user_states WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()

        bot.send_message(user_id, "Profile created successfully! 🎉", reply_markup=main_keyboard(user_id))

    except Exception as e:
        conn.close()
        bot.send_message(user_id, f"⚠️ Error saving photo. Type /reset to try again.")

# --- TEXT FLOW & MENU ---
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    text = message.text

    if user_id in active_chats:
        if text in ["🚫 End Chat", "Chat Khatam Karein"]:
            end_chat(message)
        else:
            bot.send_message(active_chats[user_id], text)
        return

    # Check Registration State
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT step FROM user_states WHERE user_id = ?", (user_id,))
    state = c.fetchone()

    if state:
        step = state[0]
        if step == 'NAME':
            c.execute("UPDATE user_states SET step = 'AGE', name = ? WHERE user_id = ?", (text, user_id))
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.row("18", "19", "20", "21")
            markup.row("22", "23", "24", "25")
            bot.send_message(user_id, "Select or type your Age:", reply_markup=markup)

        elif step == 'AGE':
            if not text.isdigit():
                bot.send_message(user_id, "Please enter a valid age number:")
                conn.close()
                return
            c.execute("UPDATE user_states SET step = 'GENDER', age = ? WHERE user_id = ?", (int(text), user_id))
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.row("👨 Male", "👩 Female")
            bot.send_message(user_id, "Select your Gender:", reply_markup=markup)

        elif step == 'GENDER':
            gender_text = "Male" if "Male" in text else "Female"
            c.execute("UPDATE user_states SET step = 'CITY', gender = ? WHERE user_id = ?", (gender_text, user_id))
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.row("Mumbai", "Delhi", "Ahmedabad", "Rajkot")
            markup.row("Bangalore", "Pune", "Surat", "Jaipur")
            bot.send_message(user_id, "Select or type your City:", reply_markup=markup)

        elif step == 'CITY':
            c.execute("UPDATE user_states SET step = 'BIO', city = ? WHERE user_id = ?", (text, user_id))
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            markup.row("⏩ Skip Bio")
            bot.send_message(user_id, "Write a short Bio (or click Skip):", reply_markup=markup)

        elif step == 'BIO':
            bio = "" if "Skip" in text else text
            c.execute("UPDATE user_states SET step = 'PHOTO', bio = ? WHERE user_id = ?", (bio, user_id))
            bot.send_message(user_id, "Now send a Photo of yourself:", reply_markup=types.ReplyKeyboardRemove())
        
        conn.commit()
        conn.close()
        return

    conn.close()

    # --- MAIN MENU NAVIGATION ---
    if text == "🔥 Find Match":
        bot.send_message(user_id, "Select your preferred match option:", reply_markup=match_filter_keyboard())
    elif text == "💬 Instant Chat":
        bot.send_message(user_id, "Select your instant chat option:", reply_markup=chat_filter_keyboard())
    elif text == "🔙 Main Menu":
        bot.send_message(user_id, "Main Menu:", reply_markup=main_keyboard(user_id))

    # --- MATCH FILTERS ---
    elif text in ["👩 Match with Girls (⭐ VIP)", "👨 Match with Boys (⭐ VIP)"]:
        target_gender = "Female" if "Girls" in text else "Male"
        if check_vip_status(user_id) == 1:
            find_match(user_id, target_gender)
        else:
            prompt_vip(user_id, f"Matching specifically with {target_gender}s is a ⭐ VIP feature!")

    elif text == "🔀 Match Randomly (🆓 Free)":
        find_match(user_id, gender_filter=None)

    # --- INSTANT CHAT FILTERS ---
    elif text in ["👩 Chat with Girls (⭐ VIP)", "👨 Chat with Boys (⭐ VIP)"]:
        target_gender = "Female" if "Girls" in text else "Male"
        if check_vip_status(user_id) == 1:
            start_instant_chat(message, target_gender)
        else:
            prompt_vip(user_id, f"Filtering chat for {target_gender}s is a ⭐ VIP feature!")

    elif text == "🔀 Chat Randomly (🆓 Free)":
        start_instant_chat(message, target_gender=None)

    # --- OTHER BUTTONS ---
    elif text == "👤 My Profile":
        my_profile(message)
    elif text == "✏️ Edit Profile":
        bot.send_message(user_id, "🔄 Send /reset to edit your profile.")
    elif text == "🎁 Invite Friends":
        invite_earn(message)
    elif text in ["⭐ Buy VIP Pass", "⭐ Buy Premium VIP (20 Stars)"]:
        send_stars_invoice(message)
    elif text == "🚫 End Chat":
        end_chat(message)
    else:
        bot.send_message(user_id, "Select an option from the menu:", reply_markup=main_keyboard(user_id))

# --- VIP PROMPT helper ---
def prompt_vip(user_id, reason):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("⭐ Buy VIP Pass", "🎁 Invite Friends")
    markup.row("🔙 Main Menu")
    bot.send_message(user_id, f"🔒 **VIP Feature Required!**\n\n{reason}\n\nUpgrade to VIP or Invite 3 friends to unlock gender filtering!", reply_markup=markup, parse_mode="Markdown")

# --- MATCHING ENGINE WITH GENDER FILTER ---
def find_match(chat_id, gender_filter=None):
    is_vip = check_vip_status(chat_id)
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM swipes WHERE user_id = ?", (chat_id,))
    swipe_count = c.fetchone()[0]

    if not is_vip and swipe_count >= 20:
        conn.close()
        prompt_vip(chat_id, "You have reached your daily limit of 20 profile views!")
        return

    query = """
        SELECT user_id, name, age, gender, city, bio, photo_id, is_vip, is_verified FROM users 
        WHERE user_id != ? AND user_id NOT IN (SELECT target_id FROM swipes WHERE user_id = ?)
    """
    params = [chat_id, chat_id]

    if gender_filter:
        query += " AND gender = ?"
        params.append(gender_filter)

    query += " ORDER BY RANDOM() LIMIT 1"
    c.execute(query, tuple(params))
    target = c.fetchone()
    conn.close()

    if not target:
        bot.send_message(chat_id, "No new profiles found with this criteria right now! Try Random or check back later.")
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

# --- INSTANT CHAT WITH FILTER ---
def start_instant_chat(message, target_gender=None):
    user_id = message.from_user.id
    if user_id in active_chats:
        bot.send_message(user_id, "You are already in an active chat!")
        return

    q_key = target_gender if target_gender else 'Any'

    # Check for matching queue
    found_partner = None
    for queue_name, queue_list in waiting_queue.items():
        if queue_list and queue_list[0] != user_id:
            found_partner = queue_list.pop(0)
            break

    if found_partner:
        active_chats[user_id] = found_partner
        active_chats[found_partner] = user_id
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🚫 End Chat")
        bot.send_message(user_id, "Connected with a real partner! Say hi 👋", reply_markup=markup)
        bot.send_message(found_partner, "Connected with a real partner! Say hi 👋", reply_markup=markup)
    else:
        if user_id not in waiting_queue[q_key]:
            waiting_queue[q_key].append(user_id)
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("🚫 End Chat")
        bot.send_message(user_id, f"Searching for a partner ({q_key})... Please wait ⏳", reply_markup=markup)

def end_chat(message):
    user_id = message.from_user.id
    if user_id in active_chats:
        partner_id = active_chats.pop(user_id)
        active_chats.pop(partner_id, None)
        bot.send_message(partner_id, "Partner ended the chat.", reply_markup=main_keyboard(partner_id))
        bot.send_message(user_id, "Chat ended successfully.", reply_markup=main_keyboard(user_id))
    else:
        for q in waiting_queue.values():
            if user_id in q:
                q.remove(user_id)
        bot.send_message(user_id, "Stopped searching.", reply_markup=main_keyboard(user_id))

# --- PROFILE & VIP ---
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

def invite_earn(message):
    user_id = message.from_user.id
    bot_name = bot.get_me().username
    ref_link = f"https://t.me/{bot_name}?start=ref_{user_id}"
    conn = sqlite3.connect('dating.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    msg = f"🎁 **Invite & Earn Free VIP!**\n\nInvite 3 friends to get **1 Month Free VIP Pass**!\nUnlock Gender Filter for Match & Chat!\n\nYour Referrals: **{count}/3**\nLink:\n`{ref_link}`"
    bot.send_message(user_id, msg, parse_mode="Markdown")

def send_stars_invoice(message):
    prices = [types.LabeledPrice(label="VIP Membership (1 Month)", amount=20)]
    bot.send_invoice(
        message.chat.id,
        title="⭐ VIP Premium Pass (1 Month)",
        description="Unlock Gender Filters (Boys/Girls) & Unlimited Swiping!",
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
    bot.send_message(user_id, "🎉 Payment Successful! VIP Unlocked for 30 Days!", reply_markup=main_keyboard(user_id))

bot.infinity_polling()

