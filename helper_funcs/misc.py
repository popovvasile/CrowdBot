#!/usr/bin/env python
# -*- coding: utf-8 -*-
import html
import traceback
from typing import List, Dict
from uuid import uuid4
from threading import Thread

from telegram import InlineKeyboardButton, ParseMode
from telegram.ext import CallbackContext, run_async
from telegram.error import TelegramError, Unauthorized
from babel.dates import format_datetime
from bson.objectid import ObjectId
from telegram.utils.promise import Promise

from database import chatbots_table, users_table
from logs import logger

LOAD = []
NO_LOAD = ['translation', 'rss']


def dismiss(update, context):
    try:
        context.bot.delete_message(update.effective_chat.id,
                                   update.effective_message.message_id)
    except TelegramError:
        pass


# never run it async
def delete_messages(update, context, message_from_update=True):
    if context and type(context.user_data) is dict:
        try:
            Thread(target=async_delete,
                   args=(update, context, context.user_data.copy(), message_from_update)).start()
            context.user_data['to_delete'] = list()
        except Exception as err:
            err_string = str(err) + "\nException in delete_message func" + traceback.format_exc()
            print(err_string)
            logger.error(err_string)


def async_delete(update, context, user_data, message_from_update=True):
    if message_from_update:
        try:
            context.bot.delete_message(update.effective_chat.id,
                                       update.effective_message.message_id)
        except TelegramError:
            pass
    # todo use map
    # https://book.pythontips.com/en/latest/map_filter.html
    if user_data:
        if 'to_delete' in user_data:
            for msg in user_data['to_delete']:
                msg = get_promise_msg(msg)
                if type(msg) is list:
                    for ms in msg:
                        try:
                            if ms.message_id != update.effective_message.message_id:
                                context.bot.delete_message(update.effective_chat.id, ms.message_id)
                        except TelegramError:
                            continue
                else:
                    if update.effective_message and msg:
                        try:
                            if msg.message_id != update.effective_message.message_id:
                                context.bot.delete_message(update.effective_chat.id,
                                                           msg.message_id)
                        except TelegramError:
                            continue

# Regular old delete
"""
def delete_messages(update, context, message_from_update=False):
    if message_from_update:
        try:
            context.bot.delete_message(update.effective_chat.id,
                                       update.effective_message.message_id)
        except TelegramError:
            pass
    if context.user_data:
        if 'to_delete' in context.user_data:
            for msg in context.user_data['to_delete']:
                if type(msg) is Promise:
                    msg = msg.result()
                if type(msg) is list:
                    for ms in msg:
                        try:
                            if ms.message_id != update.effective_message.message_id:
                                context.bot.delete_message(
                                    update.effective_chat.id, ms.message_id)
                        except TelegramError:
                            continue
                else:
                    if update.effective_message and msg:
                        try:
                            if msg.message_id != update.effective_message.message_id:
                                context.bot.delete_message(
                                    update.effective_chat.id, msg.message_id)
                        except TelegramError:
                            continue

            context.user_data['to_delete'] = list()
        else:
            context.user_data['to_delete'] = list()
    else:
        context.user_data['to_delete'] = list()
"""


# todo OVERKILL
# http://babel.pocoo.org/en/latest/dates.html
def lang_timestamp(bot_lang: (CallbackContext, str), timestamp,
                   pattern="d, MMM yyyy, hh:mm"):
    if timestamp is None:
        return ""
    # lang_keys = {"ENG": "en", "RUS": "ru", "DE": "de"}
    if isinstance(bot_lang, CallbackContext):
        bot_lang = chatbots_table.find_one({"bot_id": bot_lang.bot.id})["lang"]
    # return format_datetime(timestamp, pattern, locale=lang_keys[bot_lang])
    return format_datetime(timestamp, pattern, locale=bot_lang)


# May raise Exception and bson.errors.InvalidId
def get_obj(table, obj: (ObjectId, dict, str)):
    # if type(obj) is Promise:
    #     obj = obj.result()
    if not obj:
        return {}
    if type(obj) is dict:
        return obj
    elif type(obj) is ObjectId:
        return table.find_one({"_id": obj}) or {}
    elif type(obj) is str:
        return table.find_one({"_id": ObjectId(obj)})
    else:
        raise Exception


def get_promise_msg(msg):
    # if isinstance(msg, Promise):
    if type(msg) is Promise:
        # todo maybe add timeout arg here
        msg = msg.result()
    return msg


def user_mention(username, string):
    """Users that have blocked the bot or never start it
    can't be shown as the url mention using "tg://bots?id=".

    But can be showing using "https://t.me/"
    but in this case we use username which must exist and be correct
    """
    return f'<a href="https://t.me/{username}">{html.escape(string, quote=False)}</a>'


def update_user_fields(context, user):
    """Update bots full_name, username and unsubscribed status.
    Used for showing users list, admins, users in shop order"""
    telegram_user = context.bot.get_chat_member(user["chat_id"],
                                                user["user_id"]).user
    new_user_fields = dict()
    if telegram_user.username != user["username"]:
        new_user_fields["username"] = telegram_user.username
        user["username"] = telegram_user.username

    if telegram_user.full_name != user["full_name"]:
        new_user_fields["full_name"] = telegram_user.full_name
        user["full_name"] = telegram_user.full_name

    # if the bots has unsubscribed set it as unsubscribed
    try:
        context.bot.send_chat_action(user["chat_id"], action="typing")
        if user["unsubscribed"]:
            new_user_fields["unsubscribed"] = False
            user["unsubscribed"] = False
    except Unauthorized:
        if not user["unsubscribed"]:
            new_user_fields["unsubscribed"] = True
            user["unsubscribed"] = True

    if new_user_fields:
        users_table.update_one({"_id": user["_id"]},
                               {"$set": new_user_fields})


def update_user_unsubs(context):
    print(f"Start updating users for bot: {context.bot.first_name}")
    users_list = users_table.find({"bot_id": context.bot.id})
    for user in users_list:
        update_user_fields(context, user)
    print(f"Finish updating users for bot: {context.bot.first_name}. "
          f"{users_list.count()} users checked")


def create_content_dict(update):
    """Creates content_dict from update.
    # todo use this function for all content_dict (messages, shop products, buttons)
    "id" field coz of -
    https://github.com/python-telegram-bot/python-telegram-bot/issues/1267
    """

    content_dict = {}
    if update.message.text:
        content_dict = {"file_id": update.message.text,
                        "type": "text",
                        "id": str(uuid4())}

    if update.message.photo:
        photo_file = update.message.photo[-1].file_id
        content_dict = {"file_id": photo_file,
                        "type": "photo_file",
                        "id": str(uuid4())}

    if update.message.audio:
        audio_file = update.message.audio.file_id
        content_dict = {"file_id": audio_file,
                        "type": "audio_file",
                        "id": str(uuid4()),
                        "name": update.message.audio.title}

    if update.message.voice:
        voice_file = update.message.voice.file_id
        content_dict = {"file_id": voice_file,
                        "type": "voice_file",
                        "id": str(uuid4())}

    if update.message.document:
        document_file = update.message.document.file_id
        content_dict = {"file_id": document_file,
                        "type": "document_file",
                        "id": str(uuid4()),
                        "name": update.message.document.file_name}

    if update.message.video:
        video_file = update.message.video.file_id
        content_dict = {"file_id": video_file,
                        "type": "video_file",
                        "id": str(uuid4())}

    if update.message.animation:
        animation_file = update.message.animation.file_id
        content_dict = {"file_id": animation_file,
                        "type": "animation_file",
                        "id": str(uuid4())}

    if update.message.video_note:
        video_note_file = update.message.video_note.file_id
        content_dict = {"file_id": video_note_file,
                        "type": "video_note_file",
                        "id": str(uuid4())}

    if update.message.sticker:
        sticker_file = update.message.sticker.file_id
        content_dict = {"file_id": sticker_file,
                        "type": "sticker_file",
                        "id": str(uuid4()),
                        "name": update.message.sticker.emoji}
    return content_dict


def send_content_dict(chat_id, context, content_dict,
                      caption=None, parse_mode=ParseMode.HTML, reply_markup=None):
    # todo use this function for all content_dict (shop products, buttons, messages)
    """Sends one content_dict"""
    if content_dict["type"] == "text":
        context.user_data["to_delete"].append(
            context.bot.send_message(chat_id,
                                     content_dict["file_id"],
                                     parse_mode=parse_mode,
                                     reply_markup=reply_markup))

    if content_dict["type"] == "audio_file":
        context.user_data["to_delete"].append(
            context.bot.send_audio(chat_id,
                                   content_dict["file_id"],
                                   caption=caption,
                                   parse_mode=parse_mode,
                                   reply_markup=reply_markup))

    if content_dict["type"] == "voice_file":
        context.user_data["to_delete"].append(
            context.bot.send_voice(chat_id,
                                   content_dict["file_id"],
                                   caption=caption,
                                   parse_mode=parse_mode,
                                   reply_markup=reply_markup))

    if content_dict["type"] == "video_file":
        context.user_data["to_delete"].append(
            context.bot.send_video(chat_id,
                                   content_dict["file_id"],
                                   caption=caption,
                                   parse_mode=parse_mode,
                                   reply_markup=reply_markup))

    if content_dict["type"] == "document_file":
        if (".png" in content_dict["file_id"] or
                ".jpg" in content_dict["file_id"]):
            context.user_data["to_delete"].append(
                context.bot.send_photo(chat_id,
                                       content_dict["file_id"],
                                       caption=caption,
                                       parse_mode=parse_mode,
                                       reply_markup=reply_markup))
        else:
            context.user_data["to_delete"].append(
                context.bot.send_document(chat_id,
                                          content_dict["file_id"],
                                          caption=caption,
                                          parse_mode=parse_mode,
                                          reply_markup=reply_markup))

    if content_dict["type"] == "photo_file":
        context.user_data["to_delete"].append(
            context.bot.send_photo(chat_id,
                                   content_dict["file_id"],
                                   caption=caption,
                                   parse_mode=parse_mode,
                                   reply_markup=reply_markup,
                                   # mime_type="image"
                                   ))

    if content_dict["type"] == "animation_file":
        context.user_data["to_delete"].append(
            context.bot.send_animation(chat_id,
                                       content_dict["file_id"],
                                       caption=caption,
                                       parse_mode=parse_mode,
                                       reply_markup=reply_markup))

    elif content_dict["type"] == "video_note_file":
        context.user_data["to_delete"].append(
            context.bot.send_video_note(chat_id,
                                        content_dict["file_id"],
                                        reply_markup=reply_markup))

    elif content_dict["type"] == "sticker_file":
        context.user_data["to_delete"].append(
            context.bot.send_sticker(chat_id,
                                     content_dict["file_id"],
                                     reply_markup=reply_markup))


def content_dict_as_string(content_dict, context):
    string = ""
    if not content_dict:
        return string

    if content_dict['type'] == "photo_file":
        string += context.bot.lang_dict["photo_file"]

    if content_dict['type'] == "voice_file":
        string += context.bot.lang_dict["voice_file"]

    if (content_dict['type'] == "audio_file" or
            content_dict['type'] == "document_file" or
            content_dict['type'] == "sticker_file"):
        string += f"• {content_dict['name']}\n"

    if content_dict['type'] == "video_file":
        string += context.bot.lang_dict["video_file"]

    if content_dict['type'] == "video_note_file":
        string += context.bot.lang_dict["video_note_file"]

    if content_dict['type'] == "animation_file":
        string += context.bot.lang_dict["animation_file"]
    return string


class EqInlineKeyboardButton(InlineKeyboardButton):
    def __eq__(self, other):
        return self.text == other.text

    def __lt__(self, other):
        return self.text < other.text

    def __gt__(self, other):
        return self.text > other.text


def paginate_modules(module_dict: Dict, prefix, bot_id, chat=None) -> List:
    buttons = []

    if not chat:
        modules = [[
            EqInlineKeyboardButton(x,
                                   callback_data="{}_module({})".format(prefix, module_dict[x]))]
                      for x in module_dict] + buttons
    else:
        modules = [[
            EqInlineKeyboardButton(x,
                                   callback_data="{}_module({},{})"
                                   .format(prefix, chat, module_dict[x]))] for x in module_dict]
    pairs = modules

    return pairs


def build_keyboard(buttons):
    keyb = []
    for btn in buttons:
        if btn.same_line and keyb:
            keyb[-1].append(InlineKeyboardButton(btn.name, url=btn.url))
        else:
            keyb.append([InlineKeyboardButton(btn.name, url=btn.url)])

    return keyb


def revert_buttons(buttons):
    res = ""
    for btn in buttons:
        if btn.same_line:
            res += "\n[{}](buttonurl://{}:same)".format(btn.name, btn.url)
        else:
            res += "\n[{}](buttonurl://{})".format(btn.name, btn.url)

    return res


def is_module_loaded(name):
    return (not LOAD or name in LOAD) and name not in NO_LOAD
