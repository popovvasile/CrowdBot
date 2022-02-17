# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ConversationHandler, CallbackQueryHandler

from helper_funcs.misc import delete_messages


# def statistic_main_menu(update, context):
#     string_d_str = context.bot.lang_dict
#     delete_messages(update, context, True)
#     users_menu_keyboard = InlineKeyboardMarkup([
#         [InlineKeyboardButton(text=string_d_str["user_statistic_btn_str"],
#                               callback_data="users_statistic"),
#          InlineKeyboardButton(text=string_d_str["donation_statistic_btn_str"],
#                               callback_data="donation_statistic")],
#         [InlineKeyboardButton(text=string_d_str["back_button"],
#                               callback_data="help_module(settings)")]
#     ])
#     context.bot.send_message(update.callback_query.message.chat.id,
#                              context.bot.lang_dict["users_menu_str"],
#                              reply_markup=users_menu_keyboard)
#     return ConversationHandler.END


# def back_to_statistic_main_menu(update, context):
#     delete_messages(update, context, True)
#     context.user_data.clear()
#     return statistic_main_menu(update, context)
#
#
# STATISTIC_MAIN_MENU = CallbackQueryHandler(callback=statistic_main_menu,
#                                            pattern="statistic")

# BACK_TO_STATISTIC_MAIN = CallbackQueryHandler(
#     callback=back_to_statistic_main_menu,
#     pattern="back_to_statistic_main_menu")
