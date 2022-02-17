# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
import datetime
from datetime import datetime, timedelta, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler, CallbackQueryHandler

from helper_funcs.misc import lang_timestamp
from database import users_table, chatbots_table


class UsersStatistic(object):
    @staticmethod
    def statistic(context):
        bot_lang = chatbots_table.find_one({"bot_id": context.bot.id})["lang"]
        today_date = datetime.combine(datetime.today(), time.min)
        week_ago_date = today_date - timedelta(days=7)
        month_ago_date = today_date - timedelta(days=30)

        # https://www.w3resource.com/python-exercises/
        # date-time-exercise/python-date-time-exercise-8.php
        all_users = users_table.find({"bot_id": context.bot.id,
                                      "is_admin": False}).sort([["_id", -1]])
        all_users_count = all_users.count()
        daily_users = users_table.find({"bot_id": context.bot.id,
                                        "is_admin": False,
                                        "timestamp": {"$gt": today_date}})
        week_users = users_table.find({"bot_id": context.bot.id,
                                       "is_admin": False,
                                       "timestamp": {"$gt": week_ago_date}})
        month_users = users_table.find({"bot_id": context.bot.id,
                                        "is_admin": False,
                                        "timestamp": {"$gt": month_ago_date}})

        today_str = lang_timestamp(bot_lang, today_date, "d MMM yyyy")

        all_unsubs = users_table.find({"bot_id": context.bot.id,
                                       "is_admin": False,
                                       "unsubscribed": True})
        return {
            "quantity": {
                "day": {"time_strings": today_str,
                        "count": daily_users.count()},

                "week": {"time_strings":
                             (lang_timestamp(bot_lang, week_ago_date,
                                             "d MMM yyyy"),
                              today_str),
                         "count": week_users.count()},

                "month": {"time_strings":
                              (lang_timestamp(bot_lang, month_ago_date,
                                              "d MMM yyyy"),
                               today_str),
                          "count": month_users.count()},

                "all": {"time_strings":
                            (lang_timestamp(bot_lang,
                                            all_users[all_users_count - 1][
                                                'timestamp']),
                             lang_timestamp(bot_lang,
                                            all_users[0]['timestamp']))
                            if all_users_count else (0, 0),
                        "count": all_users_count},

                "unsubs": {"count": all_unsubs.count()}
            }}

    def show_statistic(self, update, context):
        context.bot.delete_message(update.callback_query.message.chat_id,
                                   update.callback_query.message.message_id)
        user_statistic = UsersStatistic.statistic(context)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=context.bot.lang_dict["users_statistic_template"].format(
                user_statistic["quantity"]["day"]["time_strings"],
                user_statistic["quantity"]["day"]["count"],

                user_statistic["quantity"]["week"]["time_strings"][0],
                user_statistic["quantity"]["week"]["time_strings"][1],
                user_statistic["quantity"]["week"]["count"],

                user_statistic["quantity"]["month"]["time_strings"][0],
                user_statistic["quantity"]["month"]["time_strings"][1],
                user_statistic["quantity"]["month"]["count"],

                user_statistic["quantity"]["all"]["time_strings"][0],
                user_statistic["quantity"]["all"]["time_strings"][1],
                user_statistic["quantity"]["all"]["count"],
                user_statistic["quantity"]["unsubs"]["count"]),
            reply_markup=InlineKeyboardMarkup([
               [InlineKeyboardButton(
                   text=context.bot.lang_dict["back_button"],
                   callback_data="back_to_module_settings")]
            ]),
            parse_mode=ParseMode.MARKDOWN),
        return ConversationHandler.END


USERS_STATISTIC_HANDLER = CallbackQueryHandler(
    pattern=r"users_statistic",
    callback=UsersStatistic().show_statistic)
