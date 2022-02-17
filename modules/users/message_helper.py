#!/usr/bin/env python
# -*- coding: utf-8 -*-
import html

import requests
from requests.exceptions import RequestException
from telegram.error import Unauthorized
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, TelegramError
from bson.objectid import ObjectId

from logs import logger
from helper_funcs.misc import delete_messages
from helper_funcs.misc import lang_timestamp, get_obj
from database import users_messages_to_admin_table


class SenderHelper(object):
    @staticmethod
    def help_receive(update, context, reply_markup, state):
        """Help to create message for sending"""
        delete_messages(update, context, False)
        final_text = context.bot.lang_dict["send_message_4"]
        if "content" not in context.user_data:
            context.user_data["content"] = list()
        if "user_input" not in context.user_data:
            context.user_data["user_input"] = list()
        if len(context.user_data["content"]) < 10:
            context.user_data["user_input"].append(update.message)
            add_to_content(update, context)
        else:
            final_text = (context.bot.lang_dict["add_menu_buttons_str_11"])
            try:
                context.bot.delete_message(update.effective_chat.id,
                                           update.effective_message.message_id)
            except TelegramError:
                pass

        if len(context.user_data["user_input"]) == 10:
            final_text = (context.bot.lang_dict["add_menu_buttons_str_11"])
        elif len(context.user_data["user_input"]) > 10:
            final_text = (context.bot.lang_dict["so_many_content"]
                          + context.bot.lang_dict["add_menu_buttons_str_11"])

        msg_index = (len(context.user_data["user_input"])
                     - len(context.user_data["content"]))
        reply_to = context.user_data["user_input"][msg_index].message_id

        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.message.chat_id,
                text=final_text
                + context.bot.lang_dict["files_counter"].format(
                    len(context.user_data['content'])),
                reply_markup=reply_markup,
                reply_to_message_id=reply_to,
                parse_mode=ParseMode.HTML))
        return state


class AnswerToMessage(SenderHelper):
    """Handle answer to message from inbox and from users list

    The only difference is back button, state(it can be the same int)
    and final callback
    """
    def __init__(self, back_button: str, state: int, final_callback):
        """
        Args:
            back_button: callback_data of the back button
            state: State that handle answer content
            final_callback: callback to execute after sending answer
        """
        self.back_button = back_button
        self.STATE = state
        self.final_callback = final_callback

    def send_message(self, update, context):
        delete_messages(update, context, True)

        message = users_messages_to_admin_table.find_one(
            {"_id": ObjectId(update.callback_query.data.split("/")[1])})

        context.user_data["answer_to"] = message

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data=self.back_button)]
        ])
        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["send_message_3"],
                reply_markup=reply_markup))
        return self.STATE

    def received_message(self, update, context):
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["done_button"],
                                  callback_data="send_message_finish")],
            [InlineKeyboardButton(text=context.bot.lang_dict["cancel_button"],
                                  callback_data=self.back_button)]
        ])
        return self.help_receive(update, context, reply_markup, self.STATE)

    def send_message_finish(self, update, context):
        # context.user_data["to_delete"].extend(context.user_data["final_delete"])
        context.user_data["to_delete"].extend(context.user_data["user_input"])
        user_message_temp = context.bot.lang_dict["user_answer_notification"].format(
            content_string(context.user_data['answer_to']['content'], context),
            content_string(context.user_data['content'], context))

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=context.bot.lang_dict["show_btn"],
                callback_data="subscriber_open_message_true/"
                              + str(context.user_data["answer_to"]["_id"]))]
        ])
        try:
            context.bot.send_message(
                chat_id=context.user_data["answer_to"]["chat_id"],
                text=user_message_temp,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML)

            users_messages_to_admin_table.update_one(
                {"_id": context.user_data["answer_to"]["_id"]},
                {"$set": {"answer_content": context.user_data["content"],
                          # "answer_string": answer_string
                          }})
            logger.info("Admin {} on bot {}:{} sent an  answer to the bots".format(
                update.effective_user.first_name,
                context.bot.first_name, context.bot.id))
            update.callback_query.answer(context.bot.lang_dict["message_sent_blink"])

        except Unauthorized:
            update.callback_query.answer(context.bot.lang_dict["user_unauthorized"])

        return self.final_callback(update, context)


def send_deleted_message_content(context, content, chat_id, update,
                                 delete_key_name="to_delete"):
    """Sends content and add message to the 'to_delete' list"""

    for content_dict in content:
        if "text" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_message(chat_id, content_dict["text"]))
        if "audio_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_audio(chat_id, content_dict["audio_file"]))
        if "voice_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_voice(chat_id, content_dict["voice_file"]))
        if "video_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_video(chat_id, content_dict["video_file"]))
        if "video_note_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_video_note(chat_id,
                                            content_dict["video_note_file"]))
        if "document_file" in content_dict:
            if (".png" in content_dict["document_file"] or
                    ".jpg" in content_dict["document_file"]):
                context.user_data[delete_key_name].append(
                    context.bot.send_photo(chat_id,
                                           content_dict["document_file"]))
            else:
                context.user_data[delete_key_name].append(
                    context.bot.send_document(chat_id,
                                              content_dict["document_file"]))
        if "photo_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_photo(chat_id, content_dict["photo_file"]))
        if "animation_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_animation(chat_id,
                                           content_dict["animation_file"]))
        if "sticker_file" in content_dict:
            context.user_data[delete_key_name].append(
                context.bot.send_sticker(chat_id,
                                         content_dict["sticker_file"]))
        if "poll_file" in content_dict:
            poll = content_dict["poll_file"]
            context.bot.forward_message(chat_id=chat_id,  # the poll should not be deleted
                                        from_chat_id=update.effective_chat.id,
                                        message_id=poll.id)


def send_not_deleted_message_content(context, content, chat_id, update):
    """Sends content without adding message to the 'to_delete' list"""

    for content_dict in content:
        if "text" in content_dict:
            context.bot.send_message(chat_id, content_dict["text"])
        if "audio_file" in content_dict:
            context.bot.send_audio(chat_id, content_dict["audio_file"])
        if "voice_file" in content_dict:
            context.bot.send_voice(chat_id, content_dict["voice_file"])
        if "video_file" in content_dict:
            context.bot.send_video(chat_id, content_dict["video_file"])
        if "video_note_file" in content_dict:
            context.bot.send_video_note(chat_id,
                                        content_dict["video_note_file"])
        if "document_file" in content_dict:
            if (".png" in content_dict["document_file"] or
                    ".jpg" in content_dict["document_file"]):
                context.bot.send_photo(chat_id, content_dict["document_file"])
            else:
                context.bot.send_document(chat_id,
                                          content_dict["document_file"])
        if "photo_file" in content_dict:
            context.bot.send_photo(chat_id, content_dict["photo_file"])
        if "animation_file" in content_dict:
            context.bot.send_animation(chat_id,
                                       content_dict["animation_file"])
        if "sticker_file" in content_dict:
            context.bot.send_sticker(chat_id, content_dict["sticker_file"])

        if "poll_file" in content_dict:
            poll = content_dict["poll_file"]
            context.bot.forward_message(chat_id=chat_id,  # the poll should not be deleted
                                        from_chat_id=update.effective_chat.id,
                                        message_id=poll.message_id)


def send_request_content_dict(update, context, chat_id, token, content_dict):
    url = "https://api.telegram.org/bot{}/".format(token)
    try:
        if "text" in content_dict:
            requests.get(url + "sendMessage",
                         params={"chat_id": chat_id,
                                 "text": content_dict["text"]})

        if "audio_file" in content_dict:
            requests.get(url + "sendAudio",
                         params={"chat_id": chat_id,
                                 "audio": content_dict["audio_file"]})

        if "voice_file" in content_dict:
            requests.get(url + "sendVoice",
                         params={"chat_id": chat_id,
                                 "voice": content_dict["voice_file"]})

        if "video_file" in content_dict:
            requests.get(url + "sendVideo",
                         params={"chat_id": chat_id,
                                 "video": content_dict["video_file"]})

        if "video_note_file" in content_dict:
            requests.get(url + "sendVideoNote",
                         params={"chat_id": chat_id,
                                 "video_note": content_dict["video_note_file"]})

        if "document_file" in content_dict:
            if ".png" in content_dict["document_file"] or ".jpg" in content_dict["document_file"]:
                requests.get(url + "sendPhoto",
                             params={"chat_id": chat_id,
                                     "photo": content_dict["document_file"]})
            else:
                requests.get(url + "sendDocument",
                             params={"chat_id": chat_id,
                                     "document": content_dict["document_file"]})

        if "photo_file" in content_dict:
            requests.get(url + "sendPhoto",
                         params={"chat_id": chat_id,
                                 "photo": content_dict["photo_file"]})

        if "animation_file" in content_dict:
            requests.get(url + "sendAnimation",
                         params={"chat_id": chat_id,
                                 "animation": content_dict["animation_file"]})

        if "sticker_file" in content_dict:
            requests.get(url + "sendSticker",
                         params={"chat_id": chat_id,
                                 "sticker": content_dict["sticker_file"]})

        if "poll_file" in content_dict:
            poll = content_dict["poll_file"]
            context.bot.forward_message(chat_id=chat_id,
                                        # the poll should not be deleted
                                        from_chat_id=update.effective_chat.id,
                                        message_id=poll.message_id)
    except (RequestException, TelegramError):
        pass


def add_to_content(update, context):
    """Adds message to the user_data 'content' key"""

    if "content" not in context.user_data:
        context.user_data["content"] = list()

    content_dict = {}
    if update.message.text:
        content_dict = {"text": update.message.text}

    elif update.message.photo:
        photo_file = update.message.photo[-1].file_id
        content_dict = {"photo_file": photo_file}

    elif update.message.audio:
        audio_file = update.message.audio.file_id
        content_dict = {"audio_file": audio_file, "name": update.message.audio.title}

    elif update.message.voice:
        voice_file = update.message.voice.file_id
        content_dict = {"voice_file": voice_file}

    elif update.message.document:
        document_file = update.message.document.file_id
        content_dict = {"document_file": document_file,
                        "name": update.message.document.file_name}

    elif update.message.video:
        video_file = update.message.video.file_id
        content_dict = {"video_file": video_file}

    elif update.message.video_note:
        video_note_file = update.message.video_note.file_id
        content_dict = {"video_note_file": video_note_file}

    elif update.message.animation:
        animation_file = update.message.animation.file_id
        content_dict = {"animation_file": animation_file}

    elif update.message.sticker:
        sticker_file = update.message.sticker.file_id
        content_dict = {"sticker_file": sticker_file,
                        "name": update.message.sticker.emoji}
    elif update.message.poll:  # todo idea --- double forward- first to our crowdbot account and
        # from there to the users
        poll_file = update.message
        content_dict = {"poll_file": poll_file,
                        # "mes""poll.message_id",
                        # "poll.id"
        }

    if content_dict:
        context.user_data["content"].append(content_dict)


def content_string(content, context):
    """Makes message content as string for the message template"""
    string = ""
    for content_dict in content:
        if "text" in content_dict:
            str_for_text = content_dict['text'][:20]
            if len(content_dict['text']) > 20:
                str_for_text += "..."
            string += f"• {html.escape(str_for_text, quote=False)}\n"

        if "photo_file" in content_dict:
            string += context.bot.lang_dict["photo_file"]

        if "voice_file" in content_dict:
            string += context.bot.lang_dict["voice_file"]

        if ("audio_file" in content_dict or
                "document_file" in content_dict or
                "sticker_file" in content_dict):
            string += f"• {content_dict['name']}\n"

        if "video_file" in content_dict:
            string += context.bot.lang_dict["video_file"]

        if "video_note_file" in content_dict:
            string += context.bot.lang_dict["video_note_file"]

        if "animation_file" in content_dict:
            string += context.bot.lang_dict["animation_file"]
        if "poll_file" in content_dict:
            string += context.bot.lang_dict["poll_file"]
    return string[:-1]


class MessageTemplate(object):
    def __init__(self, obj: (ObjectId, dict, str), context):
        self.context = context
        message_obj = get_obj(users_messages_to_admin_table, obj)
        self.chat_id = message_obj["chat_id"]
        self.user_id = message_obj["user_id"]
        # self.is_new = message_obj["is_new"]
        # self.anonim = message_obj["anonim"]
        self.timestamp = message_obj["timestamp"]
        self.content = message_obj["content"]
        self.answer_content = message_obj["answer_content"]
        self.user_full_name = message_obj["user_full_name"]
        # Get chat member to get bots information
        # because database data can be incorrect
        user = context.bot.get_chat_member(self.chat_id, self.user_id).user
        # Create bots html mention
        if message_obj["anonim"]:
            self.user_mention = f"<code>{self.user_full_name}</code>"
        # elif bots.username:
        #     self.user_mention = user_mention(bots.username, bots.full_name)
        else:
            self.user_mention = user.mention_html()
        # If message is new - add emoji near it
        if message_obj["is_new"]:
            self.title_emoji = "🆕" + "\n"
        else:
            self.title_emoji = ""

    def super_short_temp(self):
        return "\n" + self.context.bot.lang_dict["from"] + self.user_mention

    def short_temp(self):
        return (self.title_emoji
                + self.context.bot.lang_dict["short_message_temp"].format(
                    self.user_mention,
                    lang_timestamp(self.context, self.timestamp)))

    def full_temp(self):
        template = (self.title_emoji
                    + self.context.bot.lang_dict["message_temp"].format(
                        self.user_mention,
                        lang_timestamp(self.context, self.timestamp),
                        content_string(self.content, self.context)))

        if self.answer_content:
            answer = content_string(self.answer_content, self.context)
        else:
            answer = "🚫"  # emoji here
        template += self.context.bot.lang_dict["answer_field"].format(answer)

        return template

    def send(self, chat_id, temp="full", reply_markup=None, text=""):
        if temp == "short":
            template = self.short_temp()
        elif temp == "super_short":
            template = self.super_short_temp()
        else:
            template = self.full_temp()

        self.context.user_data["to_delete"].append(
            self.context.bot.send_message(
                chat_id=chat_id,
                text=template + "\n\n" + text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML))
