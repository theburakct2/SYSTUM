from pyrogram.types import InlineKeyboardButton

def track_markup(_, videoid, user_id, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{channel}")
        ]
    ]
    return buttons

def stream_markup(_, chat_id):
    buttons = [
        [
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}")
        ]
    ]
    return buttons

def stream_markup_timer(_, chat_id, played, dur):
    buttons = [
        [
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{chat_id}")
        ]
    ]
    return buttons

def playlist_markup(_, videoid, user_id, ptype, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{channel}")
        ]
    ]
    return buttons

def livestream_markup(_, videoid, user_id, mode, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{channel}")
        ]
    ]
    return buttons

def slider_markup(_, videoid, user_id, query, query_type, channel, fplay):
    buttons = [
        [
            InlineKeyboardButton(text="▢", callback_data=f"ADMIN Stop|{channel}")
        ]
    ]
    return buttons
