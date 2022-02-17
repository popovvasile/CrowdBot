#!/usr/bin/env python
# -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import MessageHandler, Filters, ConversationHandler, CallbackQueryHandler

from database import chatbots_table
from helper_funcs.helper import get_help, back_to_modules, dismiss_button
from helper_funcs.misc import delete_messages


MESSAGE = 1
MESSAGE_TO_USERS = 1


class EditBotDescription(object):
    def send_message(self, update, context):
        delete_messages(update, context, True)
        buttons = list()
        buttons.append([InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                             callback_data="back_to_module_settings")])
        reply_markup = InlineKeyboardMarkup(buttons)
        context.user_data["to_delete"].append(
            context.bot.send_message(update.effective_chat.id,
                                     context.bot.lang_dict["edit_button_str_1"],
                                     reply_markup=reply_markup))
        return MESSAGE

    def received_message(self, update, context):
        context.bot.send_message(update.message.chat_id,
                                 context.bot.lang_dict["done_button"],
                                 reply_markup=dismiss_button(context))

        chatbots_table.update_one({"bot_id": context.bot.id},
                                  {"$set": {"welcomeMessage": update.message.text}})
        get_help(update, context)
        return ConversationHandler.END

    def back(self, update, context):
        context.bot.delete_message(chat_id=update.effective_chat.id,
                                   message_id=update.effective_message.message_id)
        get_help(update, context)
        return ConversationHandler.END


"""
class EditBotPicture(object):
    @staticmethod
    def info_menu(update, context):
        delete_messages(update, context, True)
        buttons = list()
        buttons.append([InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                             callback_data="back_to_module_settings")])
        reply_markup = InlineKeyboardMarkup(buttons)
        context.user_data["to_delete"].append(
            context.bot.send_message(update.effective_chat.id,
                                     context.bot.lang_dict["edit_bot_pic_text"],
                                     reply_markup=reply_markup))
        return ConversationHandler.END


EDIT_PICTURE_HANDLER = CallbackQueryHandler(callback=EditBotPicture.info_menu,
                                            pattern="edit_bot_pic")
"""


EDIT_BOT_DESCRIPTION_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(pattern="edit_bot_description",
                                       callback=EditBotDescription().send_message)],

    states={
        MESSAGE: [MessageHandler(Filters.text, EditBotDescription().received_message)],

    },

    fallbacks=[
        CallbackQueryHandler(callback=back_to_modules,
                             pattern="back_to_module_settings")
    ]
)
