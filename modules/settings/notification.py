#!/usr/bin/env python
# -*- coding: utf-8 -*-
import logging
from pprint import pprint

from telegram.error import BadRequest, TelegramError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from bson.objectid import ObjectId

from database import users_table
from helper_funcs.auth import initiate_chat_id
from helper_funcs.misc import (delete_messages, create_content_dict, send_content_dict,
                               content_dict_as_string)
from helper_funcs.helper import get_help, back_to_modules


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)


class NotificationSetting(object):
    def notification_menu_markup(self, admin, context):
        buttons = []
        if admin["order_notification"]:
            buttons.append(
                [InlineKeyboardButton(text="🔕" + context.bot.lang_dict["order_notification"],
                                      callback_data="notification_edit_order_off")])
        else:
            buttons.append(
                [InlineKeyboardButton(text="🔔" + context.bot.lang_dict["order_notification"],
                                      callback_data="notification_edit_order_on")])

        if admin["messages_notification"]:
            buttons.append(
                [InlineKeyboardButton(text="🔕" + context.bot.lang_dict["message_notification"],
                                      callback_data="notification_edit_messages_off")])
        else:
            buttons.append(
                [InlineKeyboardButton(text="🔔" + context.bot.lang_dict["message_notification"],
                                      callback_data="notification_edit_messages_on")])
        buttons.append(
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_module_settings")])
        return InlineKeyboardMarkup(buttons)

    def notification_setting(self, update, context):
        delete_messages(update, context, True)
        admin = users_table.find_one({"bot_id": context.bot.id,
                                      "user_id": update.effective_user.id}) or {}
        if not admin:
            get_help(update, context)
        else:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    update.effective_chat.id,
                    text=context.bot.lang_dict["notification_btn_str"],
                    reply_markup=self.notification_menu_markup(admin, context)))
        return ConversationHandler.END

    def edit_notification(self, update, context):
        if "off" in update.callback_query.data:
            new_status = False
        elif "on" in update.callback_query.data:
            new_status = True
        else:
            update.callback_query.data = "back_to_module_settings"
            back_to_modules(update, context)
            return ConversationHandler.END

        if "order" in update.callback_query.data:
            field = "order_notification"
        elif "messages" in update.callback_query.data:
            field = "messages_notification"
        else:
            update.callback_query.data = "back_to_module_settings"
            back_to_modules(update, context)
            return ConversationHandler.END
        admin = users_table.find_and_modify({"bot_id": context.bot.id,
                                             "user_id": update.effective_user.id},
                                            {"$set": {field: new_status}}, new=True)
        update.effective_message.edit_reply_markup(
            reply_markup=self.notification_menu_markup(admin, context))

        blink = ""
        if new_status and field == "order_notification":
            blink = context.bot.lang_dict["order_notification_on_blink"]
        elif not new_status and field == "order_notification":
            blink = context.bot.lang_dict["order_notification_off_blink"]
        elif new_status and field == "messages_notification":
            blink = context.bot.lang_dict["messages_notification_on_blink"]
        elif not new_status and field == "messages_notification":
            blink = context.bot.lang_dict["messages_notification_off_blink"]
        if blink:
            update.callback_query.answer(blink)
        return ConversationHandler.END


NOTIFICATION_MENU = CallbackQueryHandler(
    pattern="notification_setting",
    callback=NotificationSetting().notification_setting)

NOTIFICATION_EDIT = CallbackQueryHandler(
    pattern=r"notification_edit",
    callback=NotificationSetting().edit_notification)
