import telebot
from telebot import types
import sqlite3

# ⚠️ YAHAN APNA BOT TOKEN REPLACE KARO
API_TOKEN = '8505897253:AAH9mpVj6H5C8OSMtsvhl1UzHuEwJeVBKn4'  
bot = telebot.TeleBot(API_TOKEN)

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

bot.infinity_polling()

