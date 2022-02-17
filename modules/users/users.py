# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
import html
from pprint import pprint

from bson.objectid import ObjectId
from telegram.error import Unauthorized, TelegramError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from telegram.utils.promise import Promise

from helper_funcs.helper import get_help, back_to_modules
from helper_funcs.pagination import Pagination
from helper_funcs.misc import (delete_messages, lang_timestamp, get_obj, user_mention,
                               update_user_fields, get_promise_msg)
from logs import logger
from modules.statistic.donation_statistic import DonationStatistic
from modules.users.message_helper import (MessageTemplate, send_deleted_message_content,
                                          AnswerToMessage, send_not_deleted_message_content,
                                          SenderHelper)
from database import users_table, donations_table, users_messages_to_admin_table


class UsersHandler(object):
    def users(self, update, context):
        delete_messages(update, context, True)
        # Set current page integer in user_data.
        if update.callback_query.data.startswith("users_list_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("users_list_pagination_", ""))
        # If one of the filters buttons clicked -
        # set new filters for query and new menu buttons
        if (update.callback_query.data == 'users_layout'
                or update.callback_query.data == "show_all"):
            context.user_data['page'] = 1
            context.user_data["filter"] = {"bot_id": context.bot.id,
                                           "is_admin": False,
                                           "unsubscribed": False}
            context.user_data["filters_buttons"] = [
                [InlineKeyboardButton(context.bot.lang_dict["show_banned_btn"],
                                      callback_data="show_banned"),
                 InlineKeyboardButton(context.bot.lang_dict["show_unbanned_btn"],
                                      callback_data="show_unbanned")]]

        elif update.callback_query.data == "show_banned":
            context.user_data['page'] = 1
            context.user_data["filter"] = {"bot_id": context.bot.id,
                                           "is_admin": False,
                                           # "regular_messages_blocked": True
                                           "blocked": True,
                                           "unsubscribed": False}
            context.user_data["filters_buttons"] = [
                [InlineKeyboardButton(context.bot.lang_dict["show_all_users_btn"],
                                      callback_data="show_all"),
                 InlineKeyboardButton(context.bot.lang_dict["show_unbanned_btn"],
                                      callback_data="show_unbanned")]]

        elif update.callback_query.data == "show_unbanned":
            context.user_data['page'] = 1
            context.user_data["filter"] = {"bot_id": context.bot.id,
                                           "is_admin": False,
                                           # "regular_messages_blocked": False
                                           "blocked": False,
                                           "unsubscribed": False}
            context.user_data["filters_buttons"] = [
                [InlineKeyboardButton(context.bot.lang_dict["show_all_users_btn"],
                                      callback_data="show_all"),
                 InlineKeyboardButton(text=context.bot.lang_dict["show_banned_btn"],
                                      callback_data="show_banned")]]
        if not context.user_data.get("page"):
            context.user_data["page"] = 1
        # Send page with users.
        self.send_users_layout(update, context)
        # return USERS
        return ConversationHandler.END

    def send_users_layout(self, update, context):
        # Get users with filters from user_data.
        users = users_table.find(
            context.user_data["filter"]).sort([["_id", -1]])
        # Send title for bots list.
        if context.user_data["filter"].get("blocked") is True:
            title_str = "banned_users_title"
        elif context.user_data["filter"].get("blocked") is False:
            title_str = "not_banned_users_title"
        else:
            title_str = "users_layout_title"
        # context.user_data['to_delete'].append(
        #     context.bot.send_message(update.callback_query.message.chat_id,
        #                              text=context.bot.lang_dict[title_str].format(users.count()),
        #                              parse_mode=ParseMode.HTML))
        # Keyboard with bots list filters buttons
        main_buttons = (context.user_data["filters_buttons"]
                        + [[InlineKeyboardButton(context.bot.lang_dict["search_btn"],
                                                 callback_data="search_user")],
                            [InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                                  callback_data="back_to_module_users")]])
        # If no users just send back button.
        if users.count() == 0:
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         text=context.bot.lang_dict["no_users_str"],
                                         reply_markup=InlineKeyboardMarkup(main_buttons)))
        else:
            # Create Pagination instance for showing page content and pages
            pagination = Pagination(users, page=context.user_data["page"])
            # Loop over users on given page and send users templates.
            for user in pagination.content:
                # Update bots names and check if the bots block the bot
                update_user_fields(context, user)
                # Send template with keyboard.
                reply_markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton(context.bot.lang_dict["open_btn_str"],
                                          callback_data=f"open_user/{user['_id']}")]
                ])
                UserTemplate(user).send(update, context, reply_markup=reply_markup)
            # Send pagination navigation keyboard.
            pagination.send_keyboard(update, context,
                                     page_prefix="users_list_pagination",
                                     text=context.bot.lang_dict[title_str].format(users.count()),
                                     buttons=main_buttons)

    def open_user(self, update, context):
        delete_messages(update, context, True)
        if update.callback_query.data.startswith("open_user"):
            user_id = ObjectId(update.callback_query.data.split("/")[1])
            context.user_data["bots"] = users_table.find_one({"_id": user_id})
        if not context.user_data["bots"]:
            update.callback_query.answer(context.bot.lang_dict["no_user_str"])
            return self.back_to_users(update, context)
        extra_buttons = [[InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                               callback_data="back_to_users_list")]]
        reply_markup = self.user_markup(context, context.user_data["bots"], extra_buttons)
        UserTemplate(context.user_data["bots"]).send(update, context, reply_markup=reply_markup)
        return ConversationHandler.END

    def user_markup(self, context, user, extra_buttons=None):
        # Creating keyboard for bots.
        user_buttons = []
        # TODO STRINGS
        if not user["unsubscribed"]:
            user_buttons.append(
                # todo change name callback
                [InlineKeyboardButton(context.bot.lang_dict["send_msg_to_user"],
                                      callback_data=f"send_message_to_user/{user['chat_id']}")])
            # if message:
            user_buttons.append(
                [InlineKeyboardButton(context.bot.lang_dict["user_messages"],
                                      callback_data=f"user_messages_{user['user_id']}")])

            if user["blocked"]:
                user_buttons.append(
                    [InlineKeyboardButton(context.bot.lang_dict["unblock_user"],
                                          callback_data=f"unblock_user_{user['_id']}")])
            else:
                user_buttons.append(
                    [InlineKeyboardButton(context.bot.lang_dict["block_user"],
                                          callback_data=f"block_user_{user['_id']}")])

        if extra_buttons:
            user_buttons.extend(extra_buttons)
        return InlineKeyboardMarkup(user_buttons)

    def search_user(self, update, context):
        delete_messages(update, context, True)
        users = users_table.find({"bot_id": context.bot.id,
                                  "is_admin": False})
        if users.count():
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    context.bot.lang_dict["back_button"],
                    callback_data="back_to_users_list")]
            ])
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         text=context.bot.lang_dict["search_user_str"],
                                         reply_markup=reply_markup))
            return START_SEARCH_USER
        else:
            update.callback_query.answer(context.bot.lang_dict["no_users_str"])
            return self.back_to_users(update, context)

    def do_search(self, update, context):
        delete_messages(update, context, True)
        reply_buttons = [[InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                               callback_data="back_to_users_list")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)
        pattern = update.message.text
        if pattern.startswith("@"):
            pattern = pattern[1:]

        # Max full name length
        if len(pattern) > 128:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    update.effective_chat.id,
                    text=context.bot.lang_dict["name_or_username_wrong_length"],
                    reply_markup=reply_markup))
            return START_SEARCH_USER
        else:
            # Get all users
            users = users_table.find({"bot_id": context.bot.id,
                                      "is_admin": False})

            # If no users just send back button.
            if not users.count():
                context.user_data["to_delete"].append(
                    context.bot.send_message(update.effective_chat.id,
                                             text=context.bot.lang_dict["no_users_str"],
                                             reply_markup=reply_markup))
                return ConversationHandler.END
            else:
                result = users_table.find(
                    {"$or": [{"username": {"$regex": pattern, "$options": "i"},
                              "bot_id": context.bot.id,
                              "superuser": False},

                             {"full_name": {"$regex": pattern, "$options": "i"},
                              "bot_id": context.bot.id,
                              "superuser": False}]
                     })

                if result.count():
                    context.user_data["found_users"] = list(result)
                    return self.send_found_users(update, context)
                else:
                    context.user_data["to_delete"].append(
                        context.bot.send_message(
                            update.effective_chat.id,
                            context.bot.lang_dict["user_not_found"],
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.HTML))
                    return START_SEARCH_USER

    def send_found_users(self, update, context):
        delete_messages(update, context, True)
        # Set current page integer in user_data.
        if (update.callback_query
                and update.callback_query.data.startswith("user_search_pagination")):
            context.user_data["search_page"] = int(
                update.callback_query.data.replace("user_search_pagination_", ""))
        if not context.user_data.get("search_page"):
            context.user_data["search_page"] = 1

        # Create Pagination instance for showing page content and pages
        pagination = Pagination(context.user_data["found_users"],
                                page=context.user_data["search_page"])
        # Loop over users on given page and send users templates.
        for user in pagination.content:
            # Update bots names and check if the bots block the bot
            update_user_fields(context, user)
            # Send template with keyboard.
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(context.bot.lang_dict["open_btn_str"],
                                      callback_data=f"open_user/{user['_id']}")]
            ])

            UserTemplate(user).send(update, context, reply_markup=reply_markup)
        reply_buttons = [[InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                               callback_data="back_to_users_list")]]
        # Send pagination navigation keyboard.
        pagination.send_keyboard(update, context,
                                 page_prefix="user_search_pagination",
                                 buttons=reply_buttons,
                                 text=context.bot.lang_dict["users_layout_title"].format(
                                     pagination.total_items))
        return FOUND_USERS

    def clear_and_reset_user_data(self, context):
        """Clear data and reset keys that users list use"""
        page = context.user_data["page"]
        filter_ = context.user_data["filter"]
        filters_buttons = context.user_data["filters_buttons"]
        # to_delete = context.user_data["to_delete"]
        context.user_data.clear()
        # context.user_data["to_delete"] = to_delete
        context.user_data["page"] = page
        context.user_data["filter"] = filter_
        context.user_data["filters_buttons"] = filters_buttons

    def back_to_users(self, update, context):
        """All backs to bots list must be done through this method"""
        delete_messages(update, context, True)
        try:
            self.clear_and_reset_user_data(context)
            return self.users(update, context)
        except KeyError:
            logger.info("Something gone wrong while back to users list")
            context.user_data.clear()
            update.callback_query.data = "back_to_module_users"
            return back_to_modules(update, context)
            # return get_help(update, context)

    def back_to_open_user(self, update, context):
        """All backs to open bots must be done through this method"""
        delete_messages(update, context, True)
        try:
            user_id = context.user_data["bots"]["_id"]
            self.clear_and_reset_user_data(context)
            context.user_data["bots"] = users_table.find_one({"_id": user_id})
            return self.open_user(update, context)
        except KeyError:
            logger.info("Something gone wrong while back to open bots")
            context.user_data.clear()
            return get_help(update, context)


class UserBlockHandler(object):
    def block_messaging_confirmation(self, update, context):
        delete_messages(update, context, True)
        context.user_data["_id"] = ObjectId(
            update.callback_query.data.replace("block_messages_", ""))
        user = users_table.find_one({"_id": context.user_data["_id"]})
        if not user:
            update.callback_query.answer(context.bot.lang_dict["no_user_str"])
            return UsersHandler().back_to_users(update, context)
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["block_messages_button"],
                                  callback_data="block_messaging_confirm_true"),
             InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                  callback_data=f"back_to_open_user")]])
        UserTemplate(user).send(update, context,
                                text=context.bot.lang_dict["confirm_block_messages"],
                                reply_markup=markup)
        return ConversationHandler.END

    def block_messaging_finish(self, update, context):
        users_table.update_one({"_id": context.user_data["_id"]},
                               {"$set": {"regular_messages_blocked": True,
                                         "anonim_messages_blocked": True}})
        update.callback_query.answer(context.bot.lang_dict["messages_blocked_blink"])
        return UsersHandler().back_to_open_user(update, context)

    def unblock_messaging_finish(self, update, context):
        _id = ObjectId(update.callback_query.data.replace("unblock_messages_", ""))
        users_table.update_one({"_id": _id},
                               {"$set": {"regular_messages_blocked": False,
                                         "anonim_messages_blocked": False}})
        update.callback_query.answer(context.bot.lang_dict["messages_unblocked"])
        return UsersHandler().back_to_open_user(update, context)

    def ban_confirmation(self, update, context):
        delete_messages(update, context, True)
        context.user_data["_id"] = ObjectId(update.callback_query.data.replace("block_user_", ""))
        user = users_table.find_one({"_id": context.user_data["_id"]})
        if not user:
            update.callback_query.answer(context.bot.lang_dict["no_user_str"])
            return UsersHandler().back_to_users(update, context)
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["block_user"],
                                  callback_data="block_user_confirm_true"),
             InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                  callback_data=f"back_to_open_user")]
        ])
        UserTemplate(user).send(update, context,
                                text=context.bot.lang_dict["ban_confirm"],
                                reply_markup=reply_markup)
        return ConversationHandler.END

    def ban_finish(self, update, context):
        users_table.update_one({"_id": context.user_data["_id"]},
                               {"$set": {"blocked": True}})
        update.callback_query.answer(context.bot.lang_dict["user_banned_blink"])
        return UsersHandler().back_to_open_user(update, context)

    def unbun_finish(self, update, context):
        _id = ObjectId(update.callback_query.data.replace("unblock_user_", ""))
        users_table.update_one({"_id": _id},
                               {"$set": {"blocked": False}})
        update.callback_query.answer(context.bot.lang_dict["user_unbanned_blink"])
        return UsersHandler().back_to_open_user(update, context)


class SeeUserMessage(object):
    def see_messages(self, update, context):
        delete_messages(update, context, True)
        # Set current page integer in user_data.
        if update.callback_query.data.startswith("pagination_user_messages"):
            context.user_data["user_messages_page"] = int(
                update.callback_query.data.replace("pagination_user_messages_", ""))
        if not context.user_data.get("user_messages_page"):
            context.user_data["user_messages_page"] = 1
        # Take user_id of from button data and set it in the user_data
        # to show messages between pagination buttons clicks.
        if update.callback_query.data.startswith("user_messages"):
            context.user_data["user_id"] = int(
                update.callback_query.data.replace("user_messages_", ""))
        buttons = list()
        buttons.append([InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                             callback_data="back_to_open_user")])

        messages = users_messages_to_admin_table.find(
            {"bot_id": context.bot.id,
             "user_id": context.user_data["user_id"],
             "anonim": False,
             "deleted": False}).sort([["_id", -1]])
        if not messages.count():
            update.callback_query.answer(context.bot.lang_dict["no_messages_blink"])
            return UsersHandler().back_to_open_user(update, context)
        pagination = Pagination(messages,
                                page=context.user_data["user_messages_page"])
        # Loop over messages on given page and send messages template.
        for message in pagination.content:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(context.bot.lang_dict["view_message_str"],
                                      callback_data=f"view_user_message_{message['_id']}")]
            ])
            # Send message template.
            MessageTemplate(message, context).send(update.effective_chat.id,
                                                   reply_markup=reply_markup)
        # Send pagination navigation keyboard.
        pagination.send_keyboard(
            update, context,
            buttons=buttons,
            page_prefix="pagination_user_messages",
            text=context.bot.lang_dict["message_count_str"].format(messages.count()))
        return ConversationHandler.END

    def view_message(self, update, context):
        delete_messages(update, context, True)
        # If "Open" button clicked - set message object in bots data
        if update.callback_query.data.startswith("view_user_message_"):
            message_id = ObjectId(
                update.callback_query.data.replace("view_user_message_", ""))
            context.user_data["message"] = (
                users_messages_to_admin_table.find_one({"_id": message_id}))

            # When message opened first time - mark it like read.
            if context.user_data["message"]["is_new"]:
                users_messages_to_admin_table.update_one(
                    {"_id": message_id}, {"$set": {"is_new": False}})

        # Send bots message content
        context.user_data["to_delete"].append(
            context.bot.send_message(chat_id=update.effective_chat.id,
                                     text=context.bot.lang_dict["user_content_title"],
                                     parse_mode=ParseMode.HTML))
        send_deleted_message_content(
            context,
            chat_id=update.effective_user.id,
            content=context.user_data["message"]["content"],
            update=update)
        # If answer exist show it
        if context.user_data["message"]["answer_content"]:
            context.user_data["to_delete"].append(
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=context.bot.lang_dict["answer_content_title"],
                                         parse_mode=ParseMode.HTML))
            send_deleted_message_content(
                context,
                chat_id=update.effective_user.id,
                content=context.user_data["message"]["answer_content"],
                update=update)
        buttons = []
        if not context.user_data["message"]["answer_content"]:
            buttons.append(
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["answer_button_str"],
                    callback_data=f"answer_to_user_message/"
                                  + str(context.user_data["message"]['_id']))])
        buttons.append(
            [InlineKeyboardButton(
                text=context.bot.lang_dict["delete_button_str"],
                # TODO NEW CALLBACK
                callback_data="confirm_delete_user_message")])
        buttons.append(
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_users_messages")])

        # Send message template.
        MessageTemplate(context.user_data["message"], context).send(
            update.effective_chat.id, temp="short",
            reply_markup=InlineKeyboardMarkup(buttons))
        return ConversationHandler.END

    def confirm_delete_message(self, update, context):
        delete_messages(update, context, True)
        buttons = [[
            InlineKeyboardButton(
                text=context.bot.lang_dict["yes"],
                callback_data="finish_delete_user_message"),
            InlineKeyboardButton(
                text=context.bot.lang_dict["no"],
                callback_data="cancel_deletion")
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)

        MessageTemplate(context.user_data["message"], context).send(
            update.effective_chat.id,
            reply_markup=reply_markup,
            text=context.bot.lang_dict["delete_messages_double_check"])
        return DOUBLE_CHECK

    def delete_message_finish(self, update, context):
        users_messages_to_admin_table.update_one(
            {"_id": context.user_data["message"]["_id"]},
            {"$set": {"deleted": True}})

        user_messages = users_messages_to_admin_table.find(
            {"bot_id": context.bot.id,
             "deleted": False,
             "user_id": context.user_data["user_id"],
             "anonim": False})

        if user_messages.count():
            return self.back_to_users_messages(update, context)
        else:
            update.callback_query.answer(context.bot.lang_dict["no_messages_blink"])
            return UsersHandler().back_to_open_user(update, context)

    def back_to_users_messages(self, update, context):
        """All backs to the bots messages list must be done through this method"""
        delete_messages(update, context, True)
        try:
            # Data for showing users list when - back
            page = context.user_data["page"]
            filter_ = context.user_data["filter"]
            filters_buttons = context.user_data["filters_buttons"]
            # Data for showing users messages when - back
            user_id = context.user_data["user_id"]
            user_messages_page = context.user_data["user_messages_page"]
            # todo do better backs()
            user = context.user_data["bots"]
        except KeyError:
            context.user_data.clear()
            return get_help(update, context)

        context.user_data.clear()
        context.user_data["page"] = page
        context.user_data["filter"] = filter_
        context.user_data["filters_buttons"] = filters_buttons
        context.user_data["user_id"] = user_id
        context.user_data["user_messages_page"] = user_messages_page
        # todo do better backs()
        context.user_data["bots"] = users_table.find_one({"_id": user["_id"]})
        return self.see_messages(update, context)

    def back_to_view_message(self, update, context):
        """All backs to the opened bots message must be done through this method"""
        delete_messages(update, context, True)
        try:
            # Data for showing users list when - back
            page = context.user_data["page"]
            filter_ = context.user_data["filter"]
            filters_buttons = context.user_data["filters_buttons"]
            # Data for showing users messages when -back
            user_id = context.user_data.get("user_id")
            user_messages_page = context.user_data["user_messages_page"]
            # Data for showing open message when - back
            message = context.user_data["message"]
            # todo do better backs()
            user = context.user_data["bots"]
        except KeyError:
            context.user_data.clear()
            return get_help(update, context)

        context.user_data.clear()
        context.user_data["page"] = page
        context.user_data["filter"] = filter_
        context.user_data["filters_buttons"] = filters_buttons
        context.user_data["user_id"] = user_id
        context.user_data["user_messages_page"] = user_messages_page
        context.user_data["message"] = users_messages_to_admin_table.find_one(
            {"_id": message["_id"]})
        # todo do better backs()
        context.user_data["bots"] = users_table.find_one({"_id": user["_id"]})
        return self.view_message(update, context)


class SendMessageToUser(object):
    """Sending messages to bots"""
    def send_message(self, update, context):
        delete_messages(update, context, True)
        context.user_data["chat_id"] = int(
            update.callback_query.data.split("/")[1])

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="cancel_creating_message")]
        ])
        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["send_message_3"],
                reply_markup=reply_markup))
        return MESSAGE_TO_USER

    def received_message(self, update, context):
        # TODO REFACTOR - use one content_dict structure for the whole project
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["done_button"],
                                  callback_data="send_message_finish")],
            [InlineKeyboardButton(text=context.bot.lang_dict["cancel_button"],
                                  callback_data="cancel_creating_message")]
        ])
        return SenderHelper().help_receive(update, context, reply_markup, MESSAGE_TO_USER)

    def send_message_finish(self, update, context):
        try:
            send_not_deleted_message_content(
                context,
                # TODO NO CHAT_ID HERE
                chat_id=context.user_data["chat_id"],
                content=context.user_data["content"],
                update=update)
        except Unauthorized:
            update.callback_query.answer(context.bot.lang_dict["user_unauthorized"])
            return self.cancel_creating_message(update, context)
        logger.info("Admin {} on bot {}:{} sent a message to the bots".format(
            update.effective_user.first_name,
            context.bot.first_name, context.bot.id))
        update.callback_query.answer(context.bot.lang_dict["message_sent_blink"])
        return UsersHandler().back_to_open_user(update, context)

    def cancel_creating_message(self, update, context):
        if context.user_data.get("user_input"):
            context.user_data["to_delete"].extend(context.user_data["user_input"])
        return UsersHandler().back_to_open_user(update, context)


class UserTemplate(object):
    def __init__(self, obj: (ObjectId, dict, str)):
        user_obj = get_obj(users_table, obj)
        self._id = user_obj["_id"]
        self.user_id = user_obj["user_id"]
        self.chat_id = user_obj["chat_id"]
        self.username = user_obj["username"]
        self.full_name = user_obj["full_name"]
        self.timestamp = user_obj["timestamp"]
        self.regular_messages_blocked = user_obj["regular_messages_blocked"]
        self.unsubscribed = user_obj["unsubscribed"]

    def send(self, update, context, text="", reply_markup=None):
        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=self.template(context) + "\n\n" + text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup))

    # todo add messages count
    def template(self, context):
        if self.username:
            _user_mention = user_mention(self.username, self.full_name)
        else:
            _user_mention = (f'<a href="tg://bots?id={self.user_id}">'
                             f'{html.escape(self.full_name, quote=False)}</a>')

        return (context.bot.lang_dict["user_temp"].format(
            _user_mention, lang_timestamp(context, self.timestamp))
            + (context.bot.lang_dict["unsub"] if self.unsubscribed else "")
            + "\n" + self.donates_to_string(context))

    def donates_to_string(self, context):
        donates = donations_table.find({"bot_id": context.bot.id,
                                        "user_id": self.user_id})
        return (context.bot.lang_dict["donations_count_str"].format(
            # TODO import fom another module
            DonationStatistic().create_amount(donates))
            if donates.count() else "")


MESSAGE_TO_USERS, MESSAGE_TO_USER, DOUBLE_CHECK = range(3)
START_SEARCH_USER, FOUND_USERS = range(2)

USERS_LIST_HANDLER = CallbackQueryHandler(
    pattern="^(users_layout|"
            "show_all|"
            "show_banned|"
            "show_unbanned|"
            "users_list_pagination)",
    callback=UsersHandler().users)

OPEN_USER_HANDLER = CallbackQueryHandler(
    pattern=r"open_user",
    callback=UsersHandler().open_user)

SEARCH_USER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(pattern="search_user",
                             callback=UsersHandler().search_user)],
    states={
        START_SEARCH_USER: [MessageHandler(Filters.text,
                                           callback=UsersHandler().do_search)],

        FOUND_USERS: [CallbackQueryHandler(pattern=r"user_search_pagination",
                                           callback=UsersHandler().send_found_users)]
    },
    fallbacks=[CallbackQueryHandler(pattern="back_to_users_list",
                                    callback=UsersHandler().back_to_users),
               CallbackQueryHandler(pattern=r"open_user",
                                    callback=UsersHandler().open_user)]
)


"""BLOCK AND UNBLOCK MESSAGING FOR USER"""
CONFIRM_BLOCK_MESSAGING = CallbackQueryHandler(
    pattern=r"block_messages",
    callback=UserBlockHandler().block_messaging_confirmation)

FINISH_BLOCK_MESSAGING = CallbackQueryHandler(
    pattern="block_messaging_confirm_true",
    callback=UserBlockHandler().block_messaging_finish)

FINISH_UNBLOCK_MESSAGING = CallbackQueryHandler(
    pattern=r"unblock_messages",
    callback=UserBlockHandler().unblock_messaging_finish)


"""BAN AND UNBUN USERS"""
CONFIRM_BAN_USER = CallbackQueryHandler(
    pattern=r"block_user",
    callback=UserBlockHandler().ban_confirmation)

FINISH_BAN_USER = CallbackQueryHandler(
    pattern=r"block_user_confirm_true",
    callback=UserBlockHandler().ban_finish)

FINISH_UNBUN_USER = CallbackQueryHandler(
    pattern=r"unblock_user",
    callback=UserBlockHandler().unbun_finish)


"""USER MESSAGES"""
USER_MESSAGES_LIST = CallbackQueryHandler(
    pattern="^(user_messages|pagination_user_messages)",
    callback=SeeUserMessage().see_messages)

VIEW_USER_MESSAGE = CallbackQueryHandler(
    pattern=r"view_user_message",
    callback=SeeUserMessage().view_message)

"""DELETE ONE USER MESSAGE"""
DELETE_USER_MESSAGE_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(
            pattern="confirm_delete_user_message",
            callback=SeeUserMessage().confirm_delete_message)],

    states={
        DOUBLE_CHECK: [
            CallbackQueryHandler(
                pattern=r"finish_delete_user_message",
                callback=SeeUserMessage().delete_message_finish),
            # CallbackQueryHandler(
            #     pattern="back_to_view_message",
            #     callback=SeeUserMessage().back_to_view_message)
        ]},

    fallbacks=[
        CallbackQueryHandler(
            pattern="cancel_deletion",
            callback=SeeUserMessage().back_to_view_message)
    ]
)

"""ANSWER TO SUBSCRIBER MESSAGE"""
answer_to_message = AnswerToMessage(
    back_button="back_to_view_message",
    state=MESSAGE_TO_USERS,
    final_callback=SeeUserMessage().back_to_view_message)

ANSWER_TO_MESSAGE_FROM_USER_LIST_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(
            pattern=r"answer_to_user_message",
            callback=answer_to_message.send_message)],
    states={
        MESSAGE_TO_USERS: [
            MessageHandler(
                filters=Filters.all,
                callback=answer_to_message.received_message)],

    },
    fallbacks=[
        CallbackQueryHandler(
            pattern=r"send_message_finish",
            callback=answer_to_message.send_message_finish),
        CallbackQueryHandler(
            pattern=r"back_to_view_message",
            callback=SeeUserMessage().back_to_view_message)]
)


"""SEND MESSAGE TO USER"""
SEND_MESSAGE_TO_USER_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(
            pattern=r"send_message_to_user",
            callback=SendMessageToUser().send_message)],

    states={
        MESSAGE_TO_USER: [
            MessageHandler(
                filters=Filters.all,
                callback=SendMessageToUser().received_message)]
    },

    fallbacks=[
        CallbackQueryHandler(
            pattern=r"send_message_finish",
            callback=SendMessageToUser().send_message_finish),
        CallbackQueryHandler(
            pattern=r"back_to_users_list",
            callback=UsersHandler().back_to_users),
        CallbackQueryHandler(
            pattern="back_to_open_user",
            callback=UsersHandler().back_to_open_user),
        CallbackQueryHandler(
            pattern="cancel_creating_message",
            callback=SendMessageToUser().cancel_creating_message)]
)


"""BACKS"""
BACK_TO_USER_MESSAGES_LIST = CallbackQueryHandler(
    pattern=r"back_to_users_messages",
    callback=SeeUserMessage().back_to_users_messages)

BACK_TO_USERS_LIST = CallbackQueryHandler(
    pattern=r"back_to_users_list",
    callback=UsersHandler().back_to_users)

BACK_TO_OPEN_USER = CallbackQueryHandler(
    pattern="back_to_open_user",
    callback=UsersHandler().back_to_open_user)

BACK_TO_OPEN_MESSAGE = CallbackQueryHandler(
    pattern="back_to_view_message",
    callback=SeeUserMessage().back_to_view_message)
