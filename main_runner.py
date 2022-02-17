#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import logging
import os
import sys
from datetime import datetime
from pprint import pprint

import requests
import telegram
import telegram.ext as tg
from telegram import Bot
from telegram.error import Unauthorized
from telegram.ext import messagequeue as mq
from telegram.utils.request import Request
from telegram.ext import (CommandHandler, CallbackQueryHandler, MessageHandler, Filters,
                          PicklePersistence)

from database import chatbots_table
from logs import logger
from helper_funcs.misc import dismiss, update_user_unsubs
from helper_funcs.helper import (help_button, button_handler, get_help, WelcomeBot,
                                 back_from_button_handler, back_to_modules, error_callback,
                                 return_to_menu)

# SETTINGS
from modules.settings.language_switch import LANG_MENU, SET_LANG
from modules.settings.menu_description import EDIT_BOT_DESCRIPTION_HANDLER
from modules.settings.button_manage import (
    BUTTON_ADD_HANDLER, DELETE_BUTTON_HANDLER, LINK_BUTTON_ADD_HANDLER,
    CREATE_BUTTON_CHOOSE, BUTTONS_MENU, ONE_BUTTON_MENU, BACK_TO_BUTTONS_MENU,
    BACK_TO_ONE_BUTTON_MENU, CHANGE_BUTTON_NAME_HANDLER, EDIT_BUTTON_CONTENT_HANDLER,
    EDIT_BUTTON_LINK_HANDLER)
from modules.settings.user_mode import USER_MODE_OFF, USER_MODE_ON
from modules.settings.admins import ADMINS_LIST_HANDLER
from modules.settings.notification import NOTIFICATION_MENU, NOTIFICATION_EDIT

# USERS AND MESSAGES
# from modules.users.messages_admin import SEND_MESSAGE_ONLY_TO_ADMINS_HANDLER
# from modules.users.messages_donators import SEND_MESSAGE_TO_DONATORS_HANDLER
from modules.users.messages import (
    SEND_MESSAGE_TO_ADMIN_HANDLER, SEND_MESSAGE_TO_USERS_HANDLER,
    SEE_MESSAGES_HANDLER, ANSWER_TO_MESSAGE_HANDLER, DELETE_MESSAGES_HANDLER,
    SEE_MESSAGES_FINISH_HANDLER, BACK_TO_INBOX, MESSAGES_MENU,
    BACK_TO_INBOX_VIEW_MESSAGE, FINISH_BLOCK_ANONIM_MESSAGING,
    CONFIRM_BLOCK_ANONIM_MESSAGING, UNBLOCK_ANONIM_MESSAGING,
    CONFIRM_BLOCK_MESSAGING_FROM_INBOX, FINISH_BLOCK_MESSAGING_FROM_INBOX,
    FINISH_UNBLOCK_MESSAGING_FROM_INBOX, SHOW_MESSAGE_HANDLER,
    HIDE_MESSAGE_HANDLER, BACK_TO_MESSAGES_MENU, DELETE_MESSAGES_MENU_HANDLER)
from modules.users.users import (
    USERS_LIST_HANDLER, USER_MESSAGES_LIST, ANSWER_TO_MESSAGE_FROM_USER_LIST_HANDLER,
    CONFIRM_BLOCK_MESSAGING, FINISH_BLOCK_MESSAGING, FINISH_UNBLOCK_MESSAGING, BACK_TO_USERS_LIST,
    VIEW_USER_MESSAGE, BACK_TO_OPEN_MESSAGE, CONFIRM_BAN_USER, FINISH_BAN_USER, FINISH_UNBUN_USER,
    SEND_MESSAGE_TO_USER_HANDLER, BACK_TO_USER_MESSAGES_LIST, DELETE_USER_MESSAGE_HANDLER,
    OPEN_USER_HANDLER, BACK_TO_OPEN_USER, SEARCH_USER)

# STATISTIC
from modules.statistic.user_statistic import USERS_STATISTIC_HANDLER

# PAYMENTS
from modules.shop.admin_side.shop_config import (CONFIGS_SHOP_GENERAL, CHANGE_SHOP_CONFIG,
                                                 EDIT_SHOP_HANDLER)

# SHOP ADMIN SIDE
from modules.shop.admin_side.eshop_enable_disable import CREATE_SHOP_HANDLER
from modules.shop.admin_side.welcome import START_SHOP_HANDLER, BACK_TO_MAIN_MENU_HANDLER, Welcome
from modules.shop.admin_side.adding_product import ADD_PRODUCT_HANDLER
from modules.shop.admin_side.orders import ORDERS_HANDLER
from modules.shop.admin_side.products import PRODUCTS_HANDLER
from modules.shop.admin_side.trash import TRASH_START, ORDERS_TRASH, PRODUCTS_TRASH
from modules.shop.admin_side.categories import (
    ADD_CATEGORY_HANDLER, CATEGORIES_HANDLER, EDIT_CATEGORIES_HANDLER,
    RENAME_CATEGORY_HANDLER, DELETE_CATEGORY_HANDLER, BACK_TO_CATEGORIES_MENU)

# SHOP USER SIDE
from modules.shop.user_side.order_creator import OFFLINE_PURCHASE_HANDLER
from modules.shop.user_side.online_payment import HANDLE_SUCCES, HANDLE_PRECHECKOUT
from modules.shop.user_side.products import (
    USERS_PRODUCTS_LIST_HANDLER, ADD_TO_CART, REMOVE_FROM_CART, PRODUCTS_CATEGORIES,
    BACK_TO_CATEGORIES, VIEW_PRODUCT, BACK_TO_CUSTOMER_SHOP, SHOP_CONTACTS, MOVE_TO_CART)
from modules.shop.user_side.cart import (
    CART, REMOVE_FROM_CART_LIST, CHANGE_QUANTITY, BACK_TO_CART, MAKE_ORDER, VIEW_CART_PRODUCT)
from modules.shop.user_side.orders import (
    USERS_ORDERS_LIST_HANDLER, USER_ORDER_ITEMS_PAGINATION, BACK_TO_USER_ORDERS,
    ORDER_PAYMENT_MENU)


class MQBot(telegram.bot.Bot):
    """A subclass of Bot which delegates send method handling to MQ"""
    def __init__(self, *args, is_queued_def=True, mqueue=None, **kwargs):
        super(MQBot, self).__init__(*args, **kwargs)
        # below 2 attributes should be provided for decorator usage
        self._is_messages_queued_default = is_queued_def
        self._msg_queue = mqueue or mq.MessageQueue()

    def __del__(self):
        try:
            self._msg_queue.stop()
        except:
            pass

    @mq.queuedmessage
    def send_message(self, *args, **kwargs):
        """Wrapped method would accept new `queued` and `isgroup`
        OPTIONAL arguments

        @mq.queuedmessage is a decorator to be used with :attr:`telegram.Bot` send* methods.
        """
        return super(MQBot, self).send_message(*args, **kwargs)

    @mq.queuedmessage
    def send_audio(self, *args, **kwargs):
        return super(MQBot, self).send_audio(*args, **kwargs)

    @mq.queuedmessage
    def send_voice(self, *args, **kwargs):
        return super(MQBot, self).send_voice(*args, **kwargs)

    @mq.queuedmessage
    def send_video(self, *args, **kwargs):
        return super(MQBot, self).send_video(*args, **kwargs)

    @mq.queuedmessage
    def send_document(self, *args, **kwargs):
        return super(MQBot, self).send_document(*args, **kwargs)

    @mq.queuedmessage
    def send_photo(self, *args, **kwargs):
        return super(MQBot, self).send_photo(*args, **kwargs)

    @mq.queuedmessage
    def send_animation(self, *args, **kwargs):
        return super(MQBot, self).send_animation(*args, **kwargs)

    @mq.queuedmessage
    def send_sticker(self, *args, **kwargs):
        return super(MQBot, self).send_sticker(*args, **kwargs)


def catch_unauthorized(func):
    def wrapper(token, lang):
        try:
            return func(token, lang)
        except Unauthorized:
            chatbots_table.update({"token": token},
                                  {"$set": {"active": False,
                                            # "deactivation_time": datetime.now()
                                            }})
            sys.exit()
    return wrapper


@catch_unauthorized
def main(token, lang):
    telegram_resp = requests.get(f"https://api.telegram.org/bot{token}/getMe")
    telegram_resp.raise_for_status()
    telegram_data = telegram_resp.json()
    fields = {
        "token": token,
        "lang": lang,
        "premium": True,
        "superuser": None,
        "bot_id": telegram_data["result"]["id"],
        "username": telegram_data["result"]["username"],
        "name": telegram_data["result"]["first_name"],
        "welcomeMessage": None,
        "active": True,
        "shop_enabled": False,
        "creation_timestamp": datetime.now()
    }
    chatbot = chatbots_table.find_and_modify(
        {"bot_id": telegram_data["result"]["id"]},
        {"$set": fields}, upsert=True, new=True
    )

    # https://github.com/python-telegram-bot/python-telegram-bot/issues/787
    request = Request(con_pool_size=30)
    # q = mq.MessageQueue(all_burst_limit=25, all_time_limit_ms=1200)
    # bot_obj = MQBot(token, request=request, mqueue=q)
    bot_obj = Bot(token, request=request)

    # filename = 'logs/{}.log'.format(bot_obj.name)
    # open(filename, "w+")
    # hdlr = logging.FileHandler(filename)
    # formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    # hdlr.setFormatter(formatter)
    # logger.addHandler(hdlr)
    # logger.setLevel(logging.ERROR)

    # with open('languages.json') as f:
    #     lang_dicts = json.load(f)
    # if lang == "ENG":
    #     bot_obj.lang_dict = lang_dicts["ENG"]
    # elif lang == "DE":
    #     bot_obj.lang_dict = lang_dicts["DE"]
    # elif lang == "UKR":
    #     bot_obj.lang_dict = lang_dicts["UKR"]
    # else:
    #     bot_obj.lang_dict = lang_dicts["RUS"]

    with open('languages.json') as f:
        lang_dicts = json.load(f)
    bot_obj.lang_dict = lang_dicts[lang]

    # my_persistence = PicklePersistence(filename='persistence.bin')
    # https://github.com/python-telegram-bot/python-telegram-bot/issues/1864
    updater = tg.Updater(use_context=True,
                         bot=bot_obj,
                         workers=20,
                         # persistence=my_persistence
                         )

    # If we stop alive_checker by pressing ctrl+c and there are running job,
    # bot process wouldn't stop. So need to use pkill -9 python
    # job = updater.job_queue
    # job.run_repeating(update_user_unsubs, interval=3600*24, first=0)

    # todo try to add async to
    # every function one by one
    # If you’re using @ run_async you cannot  rely on adding custom
    # attributes  to telegram.ext.CallbackContext. See its docs for more info.
    # https://python-telegram-bot.readthedocs.io/en/stable/telegram.ext.dispatcher.html?highlight=run_async%20#telegram.ext.Dispatcher.run_async
    dispatcher = updater.dispatcher
    start_handler = CommandHandler("start", WelcomeBot().start)
    help_handler = CommandHandler("help", get_help)

    # TODO think if to use this one
    # product_handler_han = CallbackQueryHandler(product_handler,
    #                                            pattern=r"product_")

    custom_button_callback_handler = CallbackQueryHandler(callback=button_handler,
                                                          pattern=r"button_")

    custom_button_back_callback_handler = CallbackQueryHandler(callback=back_from_button_handler,
                                                               pattern=r"back_from_button")

    help_callback_handler = CallbackQueryHandler(callback=help_button,
                                                 pattern=r"help_")

    back_to_modules_handler = CallbackQueryHandler(callback=back_to_modules,
                                                   pattern=r"back_to_module")

    dismiss_handler = CallbackQueryHandler(callback=dismiss,
                                           pattern="dismiss")

    # TODO priority is very important!!!!!!!!!!!!!!!!!!!!
    dispatcher.add_handler(dismiss_handler)
    dispatcher.add_handler(EDIT_BOT_DESCRIPTION_HANDLER)

    #  SHOP USER SIDE
    dispatcher.add_handler(EDIT_SHOP_HANDLER)
    dispatcher.add_handler(OFFLINE_PURCHASE_HANDLER)
    dispatcher.add_handler(BACK_TO_CART)
    dispatcher.add_handler(USERS_PRODUCTS_LIST_HANDLER)
    dispatcher.add_handler(ADD_TO_CART)
    dispatcher.add_handler(REMOVE_FROM_CART)
    dispatcher.add_handler(CART)
    dispatcher.add_handler(MAKE_ORDER)
    dispatcher.add_handler(PRODUCTS_CATEGORIES)
    dispatcher.add_handler(BACK_TO_CATEGORIES)
    dispatcher.add_handler(REMOVE_FROM_CART_LIST)
    dispatcher.add_handler(CHANGE_QUANTITY)
    dispatcher.add_handler(USERS_ORDERS_LIST_HANDLER)
    dispatcher.add_handler(VIEW_CART_PRODUCT)
    dispatcher.add_handler(VIEW_PRODUCT)
    dispatcher.add_handler(MOVE_TO_CART)
    dispatcher.add_handler(BACK_TO_CUSTOMER_SHOP)
    dispatcher.add_handler(USER_ORDER_ITEMS_PAGINATION)
    dispatcher.add_handler(ORDER_PAYMENT_MENU)
    dispatcher.add_handler(BACK_TO_USER_ORDERS)
    dispatcher.add_handler(SHOP_CONTACTS)

    #  SHOP ADMIN SIDE
    # dispatcher.add_handler(product_handler_han)
    dispatcher.add_handler(CHANGE_SHOP_CONFIG)
    dispatcher.add_handler(CONFIGS_SHOP_GENERAL)
    dispatcher.add_handler(CREATE_SHOP_HANDLER)
    dispatcher.add_handler(START_SHOP_HANDLER)
    dispatcher.add_handler(ORDERS_TRASH)
    dispatcher.add_handler(PRODUCTS_TRASH)
    dispatcher.add_handler(ADD_PRODUCT_HANDLER)
    dispatcher.add_handler(ORDERS_HANDLER)
    dispatcher.add_handler(PRODUCTS_HANDLER)
    dispatcher.add_handler(TRASH_START)
    dispatcher.add_handler(ADD_CATEGORY_HANDLER)
    dispatcher.add_handler(CATEGORIES_HANDLER)
    dispatcher.add_handler(EDIT_CATEGORIES_HANDLER)
    dispatcher.add_handler(RENAME_CATEGORY_HANDLER)
    dispatcher.add_handler(RENAME_CATEGORY_HANDLER)
    dispatcher.add_handler(DELETE_CATEGORY_HANDLER)
    dispatcher.add_handler(BACK_TO_CATEGORIES_MENU)
    dispatcher.add_handler(HANDLE_SUCCES)
    dispatcher.add_handler(HANDLE_PRECHECKOUT)

    # BUTTONS
    dispatcher.add_handler(ONE_BUTTON_MENU)
    dispatcher.add_handler(CHANGE_BUTTON_NAME_HANDLER)
    dispatcher.add_handler(EDIT_BUTTON_CONTENT_HANDLER)
    dispatcher.add_handler(EDIT_BUTTON_LINK_HANDLER)
    dispatcher.add_handler(BUTTONS_MENU)
    dispatcher.add_handler(CREATE_BUTTON_CHOOSE)
    dispatcher.add_handler(LINK_BUTTON_ADD_HANDLER)
    dispatcher.add_handler(BUTTON_ADD_HANDLER)
    dispatcher.add_handler(DELETE_BUTTON_HANDLER)
    dispatcher.add_handler(BACK_TO_BUTTONS_MENU)
    dispatcher.add_handler(BACK_TO_ONE_BUTTON_MENU)
    dispatcher.add_handler(LANG_MENU)
    dispatcher.add_handler(SET_LANG)

    # USER MODE
    dispatcher.add_handler(USER_MODE_ON)
    dispatcher.add_handler(USER_MODE_OFF)

    # USERS
    dispatcher.add_handler(USERS_LIST_HANDLER)
    dispatcher.add_handler(CONFIRM_BLOCK_MESSAGING)
    dispatcher.add_handler(FINISH_BLOCK_MESSAGING)
    dispatcher.add_handler(FINISH_UNBLOCK_MESSAGING)
    dispatcher.add_handler(USER_MESSAGES_LIST)
    dispatcher.add_handler(VIEW_USER_MESSAGE)
    dispatcher.add_handler(ANSWER_TO_MESSAGE_FROM_USER_LIST_HANDLER)
    dispatcher.add_handler(BACK_TO_OPEN_MESSAGE)
    dispatcher.add_handler(FINISH_BAN_USER)
    dispatcher.add_handler(CONFIRM_BAN_USER)
    dispatcher.add_handler(FINISH_UNBUN_USER)
    dispatcher.add_handler(SEND_MESSAGE_TO_USER_HANDLER)
    dispatcher.add_handler(SEARCH_USER)
    dispatcher.add_handler(BACK_TO_USERS_LIST)
    dispatcher.add_handler(BACK_TO_USER_MESSAGES_LIST)
    dispatcher.add_handler(DELETE_USER_MESSAGE_HANDLER)
    dispatcher.add_handler(OPEN_USER_HANDLER)
    dispatcher.add_handler(BACK_TO_OPEN_USER)

    # STATISTIC
    dispatcher.add_handler(USERS_STATISTIC_HANDLER)

    # ADMINS
    dispatcher.add_handler(ADMINS_LIST_HANDLER)
    dispatcher.add_handler(NOTIFICATION_MENU)
    dispatcher.add_handler(NOTIFICATION_EDIT)

    # MESSAGES
    dispatcher.add_handler(MESSAGES_MENU)
    dispatcher.add_handler(ANSWER_TO_MESSAGE_HANDLER)
    dispatcher.add_handler(DELETE_MESSAGES_HANDLER)
    dispatcher.add_handler(SEND_MESSAGE_TO_ADMIN_HANDLER)
    dispatcher.add_handler(SEND_MESSAGE_TO_USERS_HANDLER)
    dispatcher.add_handler(SEE_MESSAGES_HANDLER)
    dispatcher.add_handler(SEE_MESSAGES_FINISH_HANDLER)
    # dispatcher.add_handler(SEND_MESSAGE_ONLY_TO_ADMINS_HANDLER)
    # dispatcher.add_handler(SEND_MESSAGE_TO_DONATORS_HANDLER)

    dispatcher.add_handler(FINISH_BLOCK_ANONIM_MESSAGING)
    dispatcher.add_handler(CONFIRM_BLOCK_ANONIM_MESSAGING)
    dispatcher.add_handler(BACK_TO_INBOX_VIEW_MESSAGE)
    dispatcher.add_handler(BACK_TO_INBOX)
    dispatcher.add_handler(UNBLOCK_ANONIM_MESSAGING)
    dispatcher.add_handler(CONFIRM_BLOCK_MESSAGING_FROM_INBOX)
    dispatcher.add_handler(FINISH_BLOCK_MESSAGING_FROM_INBOX)
    dispatcher.add_handler(FINISH_UNBLOCK_MESSAGING_FROM_INBOX)
    dispatcher.add_handler(SHOW_MESSAGE_HANDLER)
    dispatcher.add_handler(HIDE_MESSAGE_HANDLER)
    dispatcher.add_handler(BACK_TO_MESSAGES_MENU)
    dispatcher.add_handler(DELETE_MESSAGES_MENU_HANDLER)

    dispatcher.add_handler(custom_button_back_callback_handler)
    dispatcher.add_handler(custom_button_callback_handler)
    dispatcher.add_handler(start_handler)
    dispatcher.add_handler(help_handler)
    dispatcher.add_handler(back_to_modules_handler)
    dispatcher.add_handler(CallbackQueryHandler(Welcome.back_to_main_menu, pattern=r"_back"))
    dispatcher.add_handler(BACK_TO_MAIN_MENU_HANDLER)
    dispatcher.add_handler(help_callback_handler)

    # if os.environ['SHOP_PRODUCTION'] == "1":
    dispatcher.add_error_handler(error_callback)
    dispatcher.add_handler(CallbackQueryHandler(get_help, pattern=r"back"))
    dispatcher.add_handler(CallbackQueryHandler(get_help, pattern=r"cancel"))
    rex_help_handler = MessageHandler(Filters.regex(r"^((?!@).)*$"), return_to_menu)
    # TODO create another function
    # TODO add "active" to all current bots
    dispatcher.add_handler(rex_help_handler)

    # Delete webhook if it exist before start polling
    if bot_obj.getWebhookInfo().url:
        bot_obj.delete_webhook()

    updater.start_polling(timeout=60, read_latency=60, clean=True, bootstrap_retries=5)
    updater.idle()
    logger.info("Using long polling.")
