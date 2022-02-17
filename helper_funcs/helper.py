import os
import sys
import re
import html
import traceback
from datetime import datetime

from urllib3.exceptions import HTTPError
from bson.objectid import ObjectId
from pickle import PicklingError
from telegram.utils.helpers import create_deep_linked_url, mention_html
from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, LabeledPrice, Bot
from telegram.ext import ConversationHandler
from telegram.error import (BadRequest, TimedOut, NetworkError, TelegramError,
                            ChatMigrated, Unauthorized, Conflict)

from logs import logger
from helper_funcs.lang_strings.help_strings import help_strings, helpable_dict
from helper_funcs.misc import paginate_modules, delete_messages, send_content_dict, user_mention
from helper_funcs.auth import (if_admin, initiate_chat_id,
                               register_chat, register_admin)
from database import (custom_buttons_table, users_table, chatbots_table,
                      user_mode_table, products_table, groups_table, conflict_notifications_table)


HELP_STRINGS = """
{}
"""


def return_to_menu(update, context):
    context.bot.send_message(update.effective_message.chat.id,
                             context.bot.lang_dict["return_to_menu"],
                             reply_markup=InlineKeyboardMarkup([
                                 [InlineKeyboardButton(
                                     text=context.bot.lang_dict["menu_button"],
                                     callback_data="help_back")],
                                 [InlineKeyboardButton(
                                     text=context.bot.lang_dict["notification_close_btn"],
                                     callback_data="dismiss")]]))


def dismiss_button(context):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text=context.bot.lang_dict["notification_close_btn"],
                              callback_data="dismiss")]])


# do not async
def send_admin_help(bot, chat_id, text, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(
            paginate_modules(helpable_dict(bot)["ADMIN_HELPABLE"], "help", bot.id)
            + [[InlineKeyboardButton(text=bot.lang_dict["user_mode_module"],
                                     callback_data="turn_user_mode_on")]])
    bot.send_message(chat_id=chat_id,
                     text=text,
                     parse_mode=ParseMode.HTML,
                     reply_markup=keyboard)


def send_visitor_help(bot, chat_id, text):
    pairs = user_main_menu_creator(bot)
    bot.send_message(chat_id=chat_id,
                     text=text,
                     parse_mode=ParseMode.HTML,
                     reply_markup=InlineKeyboardMarkup(pairs))


def send_admin_user_mode(bot, chat_id, text):

    pairs = (user_main_menu_creator(bot)
             + [[InlineKeyboardButton(text=bot.lang_dict["admin_mode"],
                                      callback_data="turn_user_mode_off")]])
    bot.send_message(chat_id=chat_id,
                     text=text,
                     parse_mode=ParseMode.HTML,
                     reply_markup=InlineKeyboardMarkup(pairs))


def user_main_menu_creator(bot):
    first_buttons = [[InlineKeyboardButton(bot.lang_dict["send_message_1"],
                                           callback_data="send_message_to_admin")]]

    if chatbots_table.find_one({"bot_id": bot.id})["shop_enabled"]:
        first_buttons += [[InlineKeyboardButton(bot.lang_dict["shop"],
                                                callback_data="help_module(shop)")]]

    buttons = [InlineKeyboardButton(button["button"],
                                    callback_data="button_{}".format(button["_id"]))
               for button in custom_buttons_table.find({"bot_id": bot.id, "link_button": False})]

    buttons += [InlineKeyboardButton(button["button"], url=button["link"])
                for button in custom_buttons_table.find({"bot_id": bot.id, "link_button": True})]

    if len(buttons) % 2 == 0:
        pairs = list(zip(buttons[::2], buttons[1::2]))
    else:
        pairs = list(zip(buttons[::2], buttons[1::2])) + [(buttons[-1],)]
    return first_buttons + pairs


def greeting_creator(update, context, chatbot):
    # todo Fuck it - need to do better
    # Creating welcome message
    if chatbot:
        current_user_mode = user_mode_table.find_one(
            {"bot_id": context.bot.id,
             "user_id": update.effective_user.id}) or {}
        is_admin = if_admin(update=update, context=context.bot)
        if chatbot.get("welcomeMessage"):
            if is_admin:
                if current_user_mode.get("user_mode"):
                    welcome_message = chatbot['welcomeMessage']
                else:
                    welcome_message = context.bot.lang_dict["welcome"]
            else:
                welcome_message = chatbot['welcomeMessage']
        else:
            if is_admin:
                if current_user_mode.get("user_mode"):
                    welcome_message = context.bot.lang_dict["default_greeting"]
                else:
                    welcome_message = context.bot.lang_dict["welcome"]
            else:
                welcome_message = context.bot.lang_dict["default_greeting"]
    else:
        welcome_message = context.bot.lang_dict["default_greeting"]
    return html.escape(welcome_message, quote=False)


def check_provider_token(currency, provider_token, update, context):
    prices = [LabeledPrice("TEST", 100000)]
    if "to_delete" not in context.user_data:
        context.user_data["to_delete"] = []

    if update.callback_query:
        update_data = update.callback_query
    else:
        update_data = update
    print(provider_token)
    print(currency)
    try:
        context.user_data["to_delete"].append(
            context.bot.sendInvoice(update_data.message.chat_id,
                                    context.bot.lang_dict["test_invoice_title"],
                                    context.bot.lang_dict["test_invoice_description"],
                                    "test",
                                    provider_token, "test", currency, prices
                                    ))

    except Exception as e:
        print(e.message)
        if str(e) == "Payment_provider_invalid":
            error = "The payment provider was not recognised or its token was invalid"
        else:
            error = e
        return (False, str(error))
    delete_messages(update, context, True)
    return (True, "All good")


def error_callback(update, context):
    delete_messages(update, context)
    try:
        raise context.error
    except Unauthorized as err:
        if err.message == "Unauthorized":
            print(f"Token revoked or bot deleted. Bot: {context.bot.first_name}: {context.bot.id}")
            chat_bot = chatbots_table.find_and_modify({"bot_id": context.bot.id},
                                                      {"$set": {"active": False}}, new=True)
            # Send notification to superuser
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["more_info"],
                    callback_data="notification_bot_menu/" + str(context.bot.id))]])

            send_superuser_notification(
                chat_id=chat_bot["superuser"],
                text=context.bot.lang_dict["bot_off_notification"].format(
                    user_mention(context.bot.username, context.bot.first_name)),
                reply_markup=reply_markup)
            sys.exit()
        else:
            err_string = str(err) + "\nUnauthorized Checker " + traceback.format_exc()
            print(err_string)
            logger.error(err_string)

    except Conflict as err:
        # todo check wtf is going on here with notification messages.
        # if "terminated by other getUpdates request" in err.message:
        #     print(f"Two bots instances running. Bot: {context.bot.first_name}: {context.bot.id}")
        #     notifications = conflict_notifications_table.find(
        #         {"bot_id": context.bot.id}).sort([["_id", -1]])
        #     if (notifications.count() == 0 or
        #             (datetime.now() - notifications[0]["timestamp"]).days >= 1):
        #         chat_bot = chatbots_table.find_one({"bot_id": context.bot.id})
        #         # Send notification to superuser
        #         reply_markup = InlineKeyboardMarkup([
        #             [InlineKeyboardButton(text=context.bot.lang_dict["notification_close_btn"],
        #                                   callback_data="dismiss")]])
        #         send_superuser_notification(
        #             chat_id=chat_bot["superuser"],
        #             text=context.bot.lang_dict["two_bots_instance_notification"].format(
        #                 username="@" + context.bot.username),
        #             reply_markup=reply_markup)
        #         conflict_notifications_table.insert_one({"bot_id": context.bot.id,
        #                                                  "timestamp": datetime.now()})
        # else:
        err_string = str(err) + "\nConflict Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    except ConnectionError as err:
        err_string = str(err) + "\nConnectionError Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    except TimedOut as err:
        err_string = str(err) + "\nTimedOut Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    except PicklingError as err:
        err_string = str(err) + "\nPicklingError Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    # handle slow connection problems
    except (HTTPError, BadRequest) as err:
        err_string = str(err) + "\nHTTPError, BadRequest Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    except NetworkError as err:
        err_string = str(err) + "\nNetworkError Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    # handle other connection problems
    except ChatMigrated as err:
        # the chat_id of a group has changed, use e.new_chat_id instead
        err_string = str(err) + "\nChatMigrated Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    except TelegramError as err:
        err_string = str(err) + "\nTelegramError Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)

    except Exception as err:
        err_string = str(err) + "\nException Checker " + traceback.format_exc()
        print(err_string)
        logger.error(err_string)
        context.bot.send_message(update.effective_chat.id,
                                 context.bot.lang_dict["error_occurred"],
                                 reply_markup=InlineKeyboardMarkup(
                                     [[InlineKeyboardButton(
                                         text=context.bot.lang_dict["back_button"],
                                         callback_data="help_back")]]))
        return ConversationHandler.END


def send_superuser_notification(chat_id, text, reply_markup):
    # Send notification to bot superuser using @crowdrobot
    bot_father_token = os.environ.get("BOTFATHER_TOKEN")
    if bot_father_token:
        try:
            bot_instance = Bot(bot_father_token)
            bot_instance.send_message(chat_id=chat_id,
                                      text=text,
                                      parse_mode=ParseMode.HTML,
                                      reply_markup=reply_markup)
        except TelegramError as notification_exc:
            print("Failed notification to superuser")
            logger.error(str(notification_exc))
        else:
            print("Successfully notification to superuser")
    else:
        print("Failed notification to superuser. Need to set BOTFATHER_TOKEN env var")


def button_handler(update, context):
    context.user_data['to_delete'] = []
    query = update.callback_query
    button_callback_data = query.data
    buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                     callback_data="back_from_button")]]
    context.bot.delete_message(chat_id=update.callback_query.message.chat_id,
                               message_id=update.callback_query.message.message_id)
    button_info = dict()
    try:
        button_info = custom_buttons_table.find_one(
            {"_id": ObjectId(button_callback_data.replace("button_", ""))})
        for content_dict in button_info["content"]:
            send_content_dict(query.message.chat.id, context, content_dict)

    except BadRequest as excp:
        if excp.message == "Message is not modified":
            pass
        elif excp.message == "Query_id_invalid":
            pass
        elif excp.message == "Message can't be deleted":
            pass
        else:
            logger.exception("Exception in help buttons. %s", str(query.data))
    context.bot.send_message(chat_id=update.callback_query.message.chat_id,
                             text=button_info.get("button")
                             or context.bot.lang_dict["back_button"],
                             reply_markup=InlineKeyboardMarkup(buttons))


def back_from_button_handler(update, context):
    delete_messages(update, context)
    help_button(update, context)


def back_to_modules(update, context):
    # todo rewrite it to use as the back function in the handlers
    """All backs to main menu buttons(modules) must be done through this func.
    Need to do better with logic in help_button function.
    Don't want to reformat for now so use little trick here.

    update.callback_query.data = "back_to_module_{here is the name of module}"
    """
    delete_messages(update, context, True)
    context.user_data.clear()
    # here can be exception if callback_query is None
    module_name = update.callback_query.data.replace("back_to_module_", "")
    update.callback_query.data = f"help_module({module_name})"
    return help_button(update, context)


def help_button(update, context):
    user = users_table.find_one({"user_id": update.effective_user.id,
                                 "bot_id": context.bot.id})
    if not user:
        register_chat(update, context)
    elif user.get("blocked", False):
        update.effective_message.reply_text(context.bot.lang_dict["blocked_user"])
        return ConversationHandler.END

    if if_admin(update=update, context=context.bot):
        HELPABLE = helpable_dict(context.bot)["ADMIN_HELPABLE"]
    else:
        HELPABLE = helpable_dict(context.bot)["VISITOR_HELPABLE"]
    query = update.callback_query
    mod_match = re.match(r"help_module\((.+?)\)", query.data)
    prev_match = re.match(r"help_prev\((.+?)\)", query.data)
    next_match = re.match(r"help_next\((.+?)\)", query.data)
    back_match = re.match(r"help_back", query.data)
    back_button_match = re.match(r"back_from_button", query.data)
    chatbot = chatbots_table.find_one({"bot_id": context.bot.id})

    welcome_message = greeting_creator(update, context, chatbot)

    try:
        if mod_match:

            module = mod_match.group(1)
            current_user_mode = user_mode_table.find_one({"bot_id": context.bot.id,
                                                          "user_id": update.effective_user.id})
            if if_admin(update=update, context=context.bot):
                if current_user_mode:
                    if current_user_mode.get("user_mode"):
                        text = help_strings(context, update)[module]["visitor_help"]
                        commands_keyboard = help_strings(context, update)[module][
                            "visitor_keyboard"]
                    else:
                        text = help_strings(context, update)[module]["admin_help"]
                        commands_keyboard = help_strings(context, update)[module]["admin_keyboard"]
                else:
                    text = help_strings(context, update)[module]["admin_help"]
                    commands_keyboard = help_strings(context, update)[module]["admin_keyboard"]

            else:
                module_dict = help_strings(context, update)[module] # TODO notification for users
                if "visitor_help" in module_dict:
                    text = module_dict["visitor_help"]
                else:
                    text = context.bot.username
                if "visitor_keyboard" in module_dict:
                    commands_keyboard = module_dict["visitor_keyboard"]
                else:
                    commands_keyboard = []
            pairs = commands_keyboard

            pairs.append(
                [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                      callback_data="help_back")]
            )
            query.message.reply_text(text=text,
                                     reply_markup=InlineKeyboardMarkup(pairs),
                                     parse_mode=ParseMode.HTML,
                                     disable_web_page_preview=True)

        elif prev_match:
            query.message.reply_text(HELP_STRINGS.format(welcome_message),
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(HELPABLE, "help", context.bot.id)))
        elif next_match:
            query.message.reply_text(HELP_STRINGS.format(welcome_message),
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(HELPABLE, "help", context.bot.id)))

        elif back_match or back_button_match:
            # context.bot.delete_message(chat_id=update.callback_query.message.chat_id,
            #                            message_id=update.callback_query.message.message_id)
            delete_messages(update, context, True)
            get_help(update, context)
            return ConversationHandler.END

        else:
            query.message.reply_text(text=HELP_STRINGS.format(welcome_message),
                                     reply_markup=InlineKeyboardMarkup(
                                         paginate_modules(HELPABLE, "help", context.bot.id)))
            return ConversationHandler.END
        # ensure no spiny white circle
        context.bot.answer_callback_query(query.id)
        try:
            query.message.delete()
        except BadRequest:
            pass
        return ConversationHandler.END

    except BadRequest as excp:
        if excp.message == "Message is not modified":
            pass
        elif excp.message == "Query_id_invalid":
            pass
        elif excp.message == "Message can't be deleted":
            pass
        else:
            logger.exception("Exception in help buttons. %s", str(query.data))


def get_help(update, context):
    try:
        delete_messages(update, context, False)
    except BadRequest:
        pass
    register_chat(update, context)
    if users_table.find_one({"user_id": update.effective_user.id, "bot_id": context.bot.id}).get(
            "blocked", False):
        update.effective_message.reply_text(context.bot.lang_dict["you_have_been_blocked"])
        return ConversationHandler.END
    chatbot = chatbots_table.find_one({"bot_id": context.bot.id})
    chat = update.effective_chat
    current_user_mode = user_mode_table.find_one({"bot_id": context.bot.id,
                                                  "user_id": update.effective_user.id})

    welcome_message = greeting_creator(update, context, chatbot)

    if if_admin(update, context):
        if current_user_mode:
            if current_user_mode.get("user_mode") is True:
                send_admin_user_mode(context.bot, chat.id, HELP_STRINGS.format(welcome_message))
            else:
                send_admin_help(context.bot, chat.id, HELP_STRINGS.format(welcome_message))
        else:

            user_mode_table.insert({"bot_id": context.bot.id,
                                    "user_id": update.effective_user.id,
                                    "user_mode": False})
            welcome_message = greeting_creator(update, context, chatbot)
            send_admin_help(context.bot, chat.id, HELP_STRINGS.format(welcome_message))
    else:
        send_visitor_help(context.bot, chat.id, HELP_STRINGS.format(welcome_message))


def on_stupid_strings(update, context):
    get_help(update, context)


class WelcomeBot(object):
    @staticmethod
    def start(update, context):
        print(update.effective_user.username, update.effective_user.id)
        chat_id, txt = initiate_chat_id(update)
        if chat_id < 0:
            print("Group")
            context.bot.send_message(chat_id=chat_id, text=context.bot.lang_dict["hello_group"],
                                     reply_markup=InlineKeyboardMarkup(
                                         [[InlineKeyboardButton(
                                             text=context.bot.lang_dict["menu_button"],
                                             url="https://telegram.me/{}".format(
                                                 context.bot.username))]]
                                     ))
            groups_table.update({"group_id": chat_id, "bot_id": context.bot.id},
                                {"group_id": chat_id, "bot_id": context.bot.id,
                                 "group_name": update.message.chat.title},
                                upsert=True)
            return ConversationHandler.END
        register_chat(update, context)
        if "survey_" in txt:
            context.bot.send_message(chat_id=chat_id, text=context.bot.lang_dict["survey_str_20"],
                                     reply_markup=InlineKeyboardMarkup(
                                         [[InlineKeyboardButton(
                                             text=context.bot.lang_dict["start_button"],
                                             callback_data="{}".format(
                                                 str(txt.replace("/start ", ""))
                                             ))]]
                                     ))
        elif "registration" in txt:
            register_admin(update, context)
            get_help(update, context)
        elif "pay_donation" in txt:
            context.bot.send_message(chat_id=chat_id, text=context.bot.lang_dict["donate_button"],
                                     reply_markup=InlineKeyboardMarkup(
                                         [[InlineKeyboardButton(
                                             text=context.bot.lang_dict["donate_button"],
                                             callback_data="pay_donation")]]
                                     ))
        else:
            get_help(update, context)

        return ConversationHandler.END


currency_limits_dict = {"RUB": {"min": 66.93, "max": 669329.91},
                        "USD": {"min": 1, "max": 10000},
                        "EUR": {"min": 0.89, "max": 8938.05},
                        "GBP": {"min": 0.77, "max": 7738.05},
                        "KZT": {"min": 380.86, "max": 3808642.90},
                        "UAH": {"min": 24.70, "max": 247047.94},
                        "RON": {"min": 4.30, "max": 43007.99},
                        "PLN": {"min": 3.84, "max": 38415.50}}
