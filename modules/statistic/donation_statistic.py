# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
from datetime import datetime, timedelta, time

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler
from database import donations_table, chatbots_table
from helper_funcs.helper import get_help
from helper_funcs.misc import delete_messages, lang_timestamp
from helper_funcs.pagination import Pagination


class DonationStatistic(object):
    def create_amount(self, donations):
        collected = dict()
        for donate in donations:
            if collected.get(donate["currency"]):
                collected[donate["currency"]] += donate["amount"]
            else:
                collected[donate["currency"]] = donate["amount"]
        if len(collected) == 0:
            return 0
        string = "\n" + "\n".join([f"{amount / 100} {currency}"
                                   for currency, amount in collected.items()])
        return string

    # def top_donators_string(self, donations):
    #     all_donators = dict()
    #     for donate in donations:
    #         if all_donators.get(donate["currency"]):
    #             collected[donate["currency"]] += donate["amount"]
    #         else:
    #             collected[donate["currency"]] = donate["amount"]
    #     return

    def show_statistic(self, update, context):
        delete_messages(update, context, True)
        kb = [[InlineKeyboardButton(
                   text=context.bot.lang_dict["donations_history_button"],
                   callback_data="show_history"),
               InlineKeyboardButton(
                   text=context.bot.lang_dict["back_button"],
                   callback_data="back_to_statistic_main_menu")]]
        bot_lang = chatbots_table.find_one({"bot_id": context.bot.id})["lang"]

        today_date = datetime.combine(datetime.today(), time.min)
        week_ago_date = today_date - timedelta(days=7)
        month_ago_date = today_date - timedelta(days=30)

        # https://www.w3resource.com/python-exercises/
        # date-time-exercise/python-date-time-exercise-8.php
        all_donations = donations_table.find(
            {"bot_id": context.bot.id,
             "status": "Paid"}).sort([["_id", -1]])
        all_donations_count = all_donations.count()
        daily_donations = donations_table.find(
            {"bot_id": context.bot.id,
             "status": "Paid",
             "timestamp_paid": {"$gt": today_date}})
        week_donations = donations_table.find(
            {"bot_id": context.bot.id,
             "status": "Paid",
             "timestamp_paid": {"$gt": week_ago_date}})
        month_donations = donations_table.find(
            {"bot_id": context.bot.id,
             "status": "Paid",
             "timestamp_paid": {"$gt": month_ago_date}})

        first_donate_time, last_donate_time = \
            (lang_timestamp(
                bot_lang,
                all_donations[all_donations_count - 1]['timestamp_paid']),
             lang_timestamp(bot_lang, all_donations[0]['timestamp_paid'])) \
            if all_donations_count else (0, 0)

        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=context.bot.lang_dict[
                    "donation_statistic_template"].format(
                    today_str=lang_timestamp(bot_lang, today_date,
                                             "d MMM yyyy"),
                    today_count=daily_donations.count(),
                    today_amount=self.create_amount(daily_donations),

                    week_from=lang_timestamp(bot_lang, week_ago_date,
                                             "d MMM yyyy"),
                    week_count=week_donations.count(),
                    week_amount=self.create_amount(week_donations),

                    month_from=lang_timestamp(bot_lang, month_ago_date,
                                              "d MMM yyyy"),
                    month_count=month_donations.count(),
                    month_amount=self.create_amount(month_donations),

                    first_donate=first_donate_time,
                    last_donate=last_donate_time,
                    all_count=all_donations_count,
                    all_amount=self.create_amount(all_donations)),
                reply_markup=InlineKeyboardMarkup(kb),
                parse_mode=ParseMode.MARKDOWN))
        return DONATION_STATISTIC

    def send_donation_history(self, update, context):
        delete_messages(update, context, True)
        # set_page_key(update, context, "show_history")
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith(
                "donation_history_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace(
                    "donation_history_pagination_", ""))
        if (not context.user_data.get("page")
                or update.callback_query.data == "show_history"):
            context.user_data["page"] = 1
        all_donations = donations_table.find(
            {"bot_id": context.bot.id}).sort([["_id", -1]])
        per_page = 5
        back_button = [[
            InlineKeyboardButton(
                text=context.bot.lang_dict["donation_statistic_btn_str"],
                callback_data="donation_statistic"),
            InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_statistic_main_menu")]]
        if all_donations.count() == 0:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["no_donations"],
                    reply_markup=InlineKeyboardMarkup(back_button)))
        else:
            pagination = Pagination(all_donations, context.user_data["page"])
            page_content = (
                context.bot.lang_dict["donation_history_title"] +
                "\n\n".join(
                    [context.bot.lang_dict[
                        "donation_history_item_temp"].format(
                        donation['mention_markdown'],
                        donation['amount']/100, donation['currency'],
                        str(donation['timestamp_paid']).split('.')[0])
                        for donation in pagination.page_content()]))
            pagination.send_keyboard(update, context, back_button)
        return HISTORY

    def cancel(self, update, context):
        update.message.reply_text(
            "Command is cancelled =("
        )
        get_help(update, context)
        return ConversationHandler.END

    def back(self, update, context):
        context.bot.delete_message(
            chat_id=update.callback_query.message.chat_id,
            message_id=update.callback_query.message.message_id)
        get_help(update, context)
        context.user_data.clear()
        return ConversationHandler.END


DONATION_STATISTIC, DONATORS, HISTORY = range(3)


# DONATION_STATISTIC_HANDLER = ConversationHandler(
#     entry_points=[
#         CallbackQueryHandler(
#             callback=DonationStatistic().show_statistic,
#             pattern=r"donation_statistic")],
#     states={
#         DONATION_STATISTIC: [
#             # CallbackQueryHandler(DonationStatistic().show_donators,
#             #                      pattern=r"donators")
#             CallbackQueryHandler(
#                 callback=back_to_statistic_main_menu,
#                 pattern="back_module(settings)"),
#
#             CallbackQueryHandler(
#                 callback=DonationStatistic().send_donation_history,
#                 pattern=r"show_history")],
#
#         # DONATORS: [CallbackQueryHandler(DonationStatistic().show_donators,
#         #                                 pattern="^[0-9]+$")],
#
#         HISTORY: [
#             CallbackQueryHandler(
#                 callback=DonationStatistic().send_donation_history,
#                 pattern="donation_history_pagination"),
#             CallbackQueryHandler(
#                 callback=back_to_statistic_main_menu,
#                 pattern="back_to_statistic_main_menu"),
#             CallbackQueryHandler(callback=DonationStatistic().show_statistic,
#                                  pattern=r"donation_statistic")]
#     },
#     fallbacks=[  # CallbackQueryHandler(callback=DonationStatistic().back,
#                  #                      pattern=r"help_back"),
#         CallbackQueryHandler(callback=DonationStatistic().back,
#                              pattern=r"help_module")]
# )
