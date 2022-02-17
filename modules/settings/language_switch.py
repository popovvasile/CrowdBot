#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from pprint import pprint

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CallbackQueryHandler, Dispatcher

from database import chatbots_table
from helper_funcs.helper import get_help
from helper_funcs.misc import delete_messages


class SwitchLanguage(object):
    @staticmethod
    def set_lang(update, context):
        delete_messages(update, context)
        # take lang from inline button and set new user_data
        lang = update.callback_query.data.split('/')[1]
        with open('languages.json') as f:
            lang_dicts = json.load(f)
        if lang == "ru":
            context.bot.lang_dict = lang_dicts["ru"]
        elif lang == "en":
            context.bot.lang_dict = lang_dicts["en"]
        elif lang == "de":
            context.bot.lang_dict = lang_dicts["de"]

        Dispatcher(bot=context.bot, update_queue=update).update_persistence()
        # change bots language
        chatbots_table.update_one({'bot_id': context.bot.id},
                                  {'$set': {'lang': lang}})
        # send main menu keyboard
        return get_help(update, context)

    @staticmethod
    def lang_menu(update, context):
        delete_messages(update, context)
        lang_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict['en'],
                                  callback_data='language/en')],
            [InlineKeyboardButton(text=context.bot.lang_dict['ru'],
                                  callback_data='language/ru')],
            [InlineKeyboardButton(text=context.bot.lang_dict["de"],
                                  callback_data='language/de')]
        ])
        # send language keyboard
        context.user_data['to_delete'].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=context.bot.lang_dict['language_menu'],
                reply_markup=lang_keyboard))
        return ConversationHandler.END


LANG_MENU = CallbackQueryHandler(callback=SwitchLanguage().lang_menu,
                                 pattern=r"langmenu")

SET_LANG = CallbackQueryHandler(callback=SwitchLanguage().set_lang,
                                pattern=r"language")
