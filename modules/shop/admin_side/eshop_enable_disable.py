# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
from telegram import ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (MessageHandler, Filters, ConversationHandler, CallbackQueryHandler)

from database import chatbots_table
from helper_funcs.auth import initiate_chat_id
from helper_funcs.constants import MIN_ADDRESS_LENGTH, MAX_ADDRESS_LENGTH
from helper_funcs.helper import get_help
from helper_funcs.misc import delete_messages
from logs import logger
from modules.shop.admin_side.welcome import Welcome
from modules.shop.helper.keyboards import currency_markup


(ASK_TOKEN, TYPING_TOKEN, TYPING_DESCRIPTION,
 TYPING_SHOP_ADDRESS, SHOP_FINISH, CHOOSING_PICK_UP_OR_DELIVERY) = range(6)


class CreateShopHandler(object):
    @staticmethod
    def facts_to_str(context):
        facts = list()

        for key, value in context.user_data.items():
            facts.append('{} - {}'.format(key, value))

        return "\n".join(facts).join(['\n', '\n'])

    def start_create_shop(self, update, context):
        if "to_delete" not in context.user_data:
            context.user_data["to_delete"] = []
        if update.message:
            context.user_data["new_product"].description = update.message.text
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        delete_messages(update, context, True)
        context.user_data["shop_type"] = "offline"
        reply_markup = [
            [InlineKeyboardButton(text=context.bot.lang_dict["shop_creation_delivery"],
                                  callback_data="shop_type_delivery")],
            [InlineKeyboardButton(text=context.bot.lang_dict["shop_creation_pick_up"],
                                  callback_data="shop_type_pick_up")],
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="help_module(shop)")],
        ]
        context.user_data["to_delete"].append(context.bot.send_message(
            update.callback_query.message.chat_id,
            context.bot.lang_dict["create_shop_str_13"],
            reply_markup=InlineKeyboardMarkup(reply_markup)))
        return CHOOSING_PICK_UP_OR_DELIVERY

    def handle_type(self, update, context):
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        delete_messages(update, context, True)

        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                   callback_data="help_module(shop)")]])
        if "delivery" in update.callback_query.data:
            context.user_data["shipping"] = True
            context.user_data["to_delete"].append(
                context.bot.send_message(update.callback_query.message.chat_id,
                                         context.bot.lang_dict["create_shop_str_6"],
                                         reply_markup=reply_markup))
            return TYPING_DESCRIPTION
        else:
            context.user_data["shipping"] = False
            context.user_data["to_delete"].append(
                context.bot.send_message(update.callback_query.message.chat_id,
                                         context.bot.lang_dict["create_shop_str_9"],
                                         reply_markup=reply_markup))
            return TYPING_SHOP_ADDRESS

    def handle_address(self, update, context):
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        delete_messages(update, context, True)

        chat_id, txt = initiate_chat_id(update)
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                   callback_data="help_module(shop)")]])
        if len(txt) < MIN_ADDRESS_LENGTH:
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         context.bot.lang_dict["short_address"]
                                         + context.bot.lang_dict["create_shop_str_9"],
                                         reply_markup=reply_markup))
            return TYPING_SHOP_ADDRESS
        elif len(txt) > MAX_ADDRESS_LENGTH:
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         context.bot.lang_dict["long_address"]
                                         + context.bot.lang_dict["create_shop_str_9"],
                                         reply_markup=reply_markup))
            return TYPING_SHOP_ADDRESS

        context.user_data["address"] = txt
        context.user_data["to_delete"].append(
            context.bot.send_message(update.effective_chat.id,
                                     context.bot.lang_dict["create_shop_str_6"],
                                     reply_markup=reply_markup))
        return TYPING_DESCRIPTION

    def handle_description(self, update, context):
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        delete_messages(update, context, True)

        chat_id, txt = initiate_chat_id(update)
        context.user_data["description"] = txt
        context.user_data["to_delete"].append(update.message.reply_text(
            context.bot.lang_dict["create_shop_str_7"],
            # reply_markup=ReplyKeyboardMarkup(currency_keyboard,
            #                                  one_time_keyboard=True))
            reply_markup=currency_markup(context)))
        return SHOP_FINISH

    def handle_shop_finish(self, update, context):
        # chat_id, txt = initiate_chat_id(update)
        # currency = txt
        context.user_data["currency"] = update.callback_query.data.split("/")[1]
        chatbot = chatbots_table.find_one({"bot_id": context.bot.id}) or {}
        context.user_data.pop("to_delete", None)
        chatbot["shop_enabled"] = True
        chatbot["shop"] = context.user_data
        chatbots_table.update_one({"bot_id": context.bot.id}, {'$set': chatbot}, upsert=True)
        update.callback_query.answer(context.bot.lang_dict["create_shop_str_8"])
        logger.info("Admin {} on bot {}:{} added a shop config".format(
            update.effective_user.first_name, context.bot.first_name, context.bot.id))
        delete_messages(update, context, True)
        context.user_data.clear()
        Welcome.start(update, context)
        return ConversationHandler.END

    def cancel(self, update, context):
        update.message.reply_text("Command is cancelled =(")
        get_help(update, context)
        return ConversationHandler.END

    def back(self, update, context):
        context.bot.delete_message(chat_id=update.effective_chat.id,
                                   message_id=update.effective_message.message_id)
        get_help(update, context)
        return ConversationHandler.END


CREATE_SHOP_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(callback=CreateShopHandler().start_create_shop,
                                       pattern=r'allow_shop'),
                  ],

    states={
        CHOOSING_PICK_UP_OR_DELIVERY: [
            CallbackQueryHandler(callback=CreateShopHandler().handle_type,
                                 pattern=r"shop_type_")],
        TYPING_SHOP_ADDRESS: [MessageHandler(Filters.text,
                                             CreateShopHandler().handle_address)],
        TYPING_DESCRIPTION: [MessageHandler(Filters.text,
                                            CreateShopHandler().handle_description)],
        SHOP_FINISH: [CallbackQueryHandler(pattern=r"currency",
                                           callback=CreateShopHandler().handle_shop_finish)],
    },

    fallbacks=[CallbackQueryHandler(callback=CreateShopHandler().back, pattern=r"help_back"),
               CallbackQueryHandler(callback=CreateShopHandler().back, pattern=r"help_module"),
               MessageHandler(filters=Filters.command, callback=CreateShopHandler().back),
               ]
)
