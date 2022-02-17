#!/usr/bin/env python
# -*- coding: utf-8 -*-
import html
from pprint import pprint
import time

from telegram.error import BadRequest, TelegramError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import MessageHandler, Filters, ConversationHandler, CallbackQueryHandler
from bson.objectid import ObjectId
from telegram.utils.promise import Promise

from database import custom_buttons_table
from helper_funcs.auth import initiate_chat_id
from helper_funcs.misc import (delete_messages, create_content_dict, send_content_dict,
                               content_dict_as_string, get_promise_msg)
from helper_funcs.constants import MAX_BUTTON_NAME_LENGTH, MAX_BUTTON_CONTENT_COUNT
from logs import logger


TYPING_BUTTON, TYPING_DESCRIPTION, DESCRIPTION_FINISH = range(3)
CONFIRM_DELETE_BUTTON = 17
TYPING_LINK, TYPING_BUTTON_FINISH = range(2)
ENTER_NEW_NAME = 1
CONTENT_MENU, ADDING_CONTENT, ENTER_NEW_LINK = range(3)


def buttons_menu(update, context):
    delete_messages(update, context, True)
    custom_buttons = custom_buttons_table.find(
        {"bot_id": context.bot.id}).sort([["link_button", 1]])
    reply_buttons = [InlineKeyboardButton(button["button"],
                                          callback_data=f"one_button_menu/{button['_id']}")
                     for button in custom_buttons]
    # todo use one button pagination function for users main menu and for admins buttons menu
    if len(reply_buttons) % 2 == 0:
        pairs = list(zip(reply_buttons[::2], reply_buttons[1::2]))
    else:
        pairs = list(zip(reply_buttons[::2], reply_buttons[1::2])) + [(reply_buttons[-1],)]

    pairs.extend(
        [[InlineKeyboardButton(text=context.bot.lang_dict["create_button_button"],
                               callback_data="create_button")],
         [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                               callback_data="help_module(settings)")]])

    context.user_data["to_delete"].append(
        context.bot.send_message(update.effective_chat.id,
                                 text=context.bot.lang_dict["buttons"],
                                 reply_markup=InlineKeyboardMarkup(pairs)))
    return ConversationHandler.END


def back_to_buttons_menu(update, context):
    delete_messages(update, context, True)
    context.user_data.clear()
    return buttons_menu(update, context)


def one_button_menu(update, context):
    delete_messages(update, context, True)
    if update.callback_query and update.callback_query.data.startswith("one_button_menu"):
        button_id = ObjectId(update.callback_query.data.split("/")[1])
        context.user_data["button"] = custom_buttons_table.find_one({"_id": button_id})
    if not context.user_data["button"]:
        update.callback_query.answer(context.bot.lang_dict["no_button_blink"])
        return back_to_buttons_menu(update, context)

    if context.user_data["button"]["link_button"]:
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["edit_button_button"],
                                               callback_data="edit_button_link")]]
        text = (context.user_data["button"]["button"]
                + "\n"
                + context.user_data["button"]["link"])
    else:
        text = context.user_data["button"]["button"]
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["edit_button_button"],
                                               callback_data="edit_button_content")]]
    reply_buttons.extend(
        [[InlineKeyboardButton(text=context.bot.lang_dict["change_name_str"],
                               callback_data="change_button_name")],
         [InlineKeyboardButton(text=context.bot.lang_dict["delete_button"],
                               callback_data="delete_button")],
         [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                               callback_data="back_to_buttons_menu")]])
    context.user_data["to_delete"].append(
        context.bot.send_message(update.effective_chat.id,
                                 text=text,
                                 reply_markup=InlineKeyboardMarkup(reply_buttons)))
    return ConversationHandler.END


def back_to_one_button_menu(update, context):
    delete_messages(update, context, True)
    try:
        button_id = context.user_data["button"]["_id"]
    except KeyError:
        return back_to_buttons_menu(update, context)
    context.user_data.clear()
    context.user_data["button"] = custom_buttons_table.find_one({"_id": button_id})
    return one_button_menu(update, context)


def validate_link(update, context):
    # TODO Link length validation
    try:
        message = context.bot.send_message(
            update.effective_chat.id,
            text="_",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("_",
                                      url=update.message.text)]
            ]))
        message = get_promise_msg(message)
        if message:
            context.bot.delete_message(update.effective_chat.id,
                                       message.message_id)
            return update.message.text
        else:
            return ""
    except BadRequest:
        return ""


class AddButtons(object):
    def start(self, update, context):
        buttons = custom_buttons_table.find({"bot_id": context.bot.id})
        if buttons.count() < 50:
            delete_messages(update, context, True)
            reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["link_button_str"],
                                                   callback_data="create_link_button")],
                             [InlineKeyboardButton(text=context.bot.lang_dict["simple_button_str"],
                                                   callback_data="create_simple_button")],
                             [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                                   callback_data="back_to_buttons_menu")]]
            context.user_data["to_delete"].append(
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=context.bot.lang_dict["choose_button_type_text"],
                                         reply_markup=InlineKeyboardMarkup(reply_buttons)))
        else:
            update.callback_query.answer(context.bot.lang_dict["so_many_buttons"])
        return ConversationHandler.END


class AddCommands(object):
    def start(self, update, context):
        delete_messages(update, context, True)
        # All users input messages will be deleted at the end or when back
        context.user_data["user_input"] = list()
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="cancel_button_creation")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)
        context.user_data["to_delete"].append(
            context.bot.send_message(update.effective_chat.id,
                                     text=context.bot.lang_dict["add_menu_buttons_str_1_1"],
                                     reply_markup=reply_markup))
        return TYPING_BUTTON

    def button_handler(self, update, context):
        delete_messages(update, context, False)
        context.user_data["user_input"].append(update.message)
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="cancel_button_creation")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)

        chat_id, txt = initiate_chat_id(update)
        if len(txt) > MAX_BUTTON_NAME_LENGTH:
            delete_messages(update, context, True)
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         text=context.bot.lang_dict["invalid_button_name"]
                                         + context.bot.lang_dict["add_menu_buttons_str_1_1"],
                                         reply_markup=InlineKeyboardMarkup(reply_buttons)))
            return TYPING_BUTTON
        button_list = custom_buttons_table.find({"bot_id": context.bot.id,
                                                 "button": txt})
        if not button_list.count():
            context.user_data['new_button'] = {"button": txt}
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    update.effective_chat.id,
                    context.bot.lang_dict["add_menu_buttons_str_2"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id,
                    parse_mode=ParseMode.HTML))
            return TYPING_DESCRIPTION
        else:
            context.user_data["to_delete"].append(
                update.message.reply_text(
                    context.bot.lang_dict["add_menu_buttons_str_3"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id))
            return TYPING_BUTTON

    def description_handler(self, update, context):
        delete_messages(update, context, False)
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["done_button"],
                                               callback_data="DONE")],
                         [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="cancel_button_creation")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)

        if "content" not in context.user_data["new_button"]:
            context.user_data["new_button"]["content"] = list()
        content_dict = create_content_dict(update)
        if content_dict:
            if len(context.user_data["new_button"]["content"]) < MAX_BUTTON_CONTENT_COUNT:
                context.user_data["new_button"]["content"].append(content_dict)
                context.user_data["user_input"].append(update.message)
            else:
                context.user_data["to_delete"].append(
                    context.bot.send_message(update.effective_chat.id,
                                             context.bot.lang_dict["so_many_content"]))
                try:
                    context.bot.delete_message(update.effective_chat.id,
                                               update.effective_message.message_id)
                except TelegramError:
                    pass
        else:
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         text=context.bot.lang_dict["content_error"],
                                         parse_mode=ParseMode.HTML))
            try:
                context.bot.delete_message(update.effective_chat.id,
                                           update.effective_message.message_id)
            except TelegramError:
                pass
        msg_index = (len(context.user_data["user_input"])
                     - len(context.user_data["new_button"]["content"]))
        reply_to = context.user_data["user_input"][msg_index].message_id

        if len(context.user_data["new_button"]["content"]) < MAX_BUTTON_CONTENT_COUNT:
            string = context.bot.lang_dict["add_menu_buttons_str_4"]
        else:
            string = context.bot.lang_dict["add_menu_buttons_str_11"]

        context.user_data["to_delete"].append(
            context.bot.send_message(update.effective_chat.id,
                                     string,
                                     reply_markup=reply_markup,
                                     reply_to_message_id=reply_to))
        return TYPING_DESCRIPTION

    def description_finish(self, update, context):
        delete_messages(update, context, True)
        context.user_data["new_button"]["button_lower"] = (
            context.user_data["new_button"]['button'].replace(" ", "").lower())
        context.user_data["new_button"]["admin_id"] = update.effective_user.id
        context.user_data["new_button"]["bot_id"] = context.bot.id
        context.user_data["new_button"]["link_button"] = False

        custom_buttons_table.save(context.user_data["new_button"])
        logger.info("Admin {} on bot {}:{} added a new button:{}".format(
            update.effective_user.first_name,
            context.bot.first_name,
            context.bot.id,
            context.user_data["new_button"]["button"]))
        # context.user_data.clear()
        update.callback_query.answer(
            context.bot.lang_dict["add_menu_buttons_str_5"].format(
                context.user_data["new_button"]["button"]))
        return self.finish_button_creation(update, context)

    def finish_button_creation(self, update, context):
        if context.user_data["user_input"]:
            context.user_data["to_delete"].extend(context.user_data["user_input"])
        return back_to_buttons_menu(update, context)


class AddLinkButton(object):
    def start(self, update, context):
        delete_messages(update, context, True)
        # All users input messages will be deleted at the end or when back
        context.user_data["user_input"] = list()
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="cancel_button_creation")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)

        context.user_data["to_delete"].append(
            context.bot.send_message(update.effective_chat.id,
                                     context.bot.lang_dict["add_menu_buttons_str_1_1"],
                                     reply_markup=reply_markup))
        return TYPING_LINK

    def link_handler(self, update, context):
        delete_messages(update, context, False)
        context.user_data["user_input"].append(update.message)
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="cancel_button_creation")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)
        chat_id, txt = initiate_chat_id(update)
        if len(txt) > MAX_BUTTON_NAME_LENGTH:
            delete_messages(update, context, True)
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         text=context.bot.lang_dict["invalid_button_name"]
                                         + context.bot.lang_dict["add_menu_buttons_str_1_1"],
                                         reply_markup=reply_markup))
            return TYPING_LINK
        button_list = custom_buttons_table.find({"bot_id": context.bot.id,
                                                 "button": txt})
        if not button_list.count():
            context.user_data['new_button'] = {"button": txt}
            context.user_data["to_delete"].append(
                update.message.reply_text(
                    context.bot.lang_dict["add_menu_buttons_str_2_link"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id))
            return TYPING_BUTTON_FINISH
        else:
            context.user_data["to_delete"].append(
                update.message.reply_text(
                    context.bot.lang_dict["add_menu_buttons_str_3"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id))
            return TYPING_LINK

    def button_finish(self, update, context):
        delete_messages(update, context, False)
        context.user_data["user_input"].append(update.message)
        link = validate_link(update, context)
        if not link:
            reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                                   callback_data="cancel_button_creation")]]
            reply_markup = InlineKeyboardMarkup(reply_buttons)
            context.user_data["to_delete"].append(
                update.message.reply_text(
                    context.bot.lang_dict["wrong_http_url"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id))
            return TYPING_BUTTON_FINISH
        else:
            context.user_data["new_button"]["button_lower"] = (
                context.user_data["new_button"]['button'].replace(" ", "").lower())
            context.user_data["new_button"]["admin_id"] = update.effective_user.id
            context.user_data["new_button"]["bot_id"] = context.bot.id
            context.user_data["new_button"]["link_button"] = True
            context.user_data["new_button"]["link"] = link
            custom_buttons_table.save(context.user_data["new_button"])

            logger.info("Admin {} on bot {}:{} added a new button:{}".format(
                update.effective_user.first_name,
                context.bot.first_name,
                context.bot.id,
                context.user_data["new_button"]["button"]))
            return AddCommands().finish_button_creation(update, context)


class DeleteButton(object):
    def confirm_delete_button(self, update, context):
        delete_messages(update, context, True)
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["delete_button"],
                                               callback_data="btn_confirm_delete")],
                         [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="back_to_one_button_menu")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                text=context.bot.lang_dict["confirm_button_delete"].format(
                    html.escape(context.user_data["button"]["button"], quote=False)),
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup))
        return CONFIRM_DELETE_BUTTON

    def delete_button_finish(self, update, context):
        custom_buttons_table.delete_one({"_id": context.user_data["button"]["_id"]})
        update.callback_query.answer(
            context.bot.lang_dict["add_menu_buttons_str_8"].format(
                context.user_data["button"]["button"]))

        logger.info("Admin {} on bot {}:{} deleted the button:{}".format(
            update.effective_user.first_name,
            context.bot.first_name,
            context.bot.id,
            context.user_data["button"]["button"]))
        return back_to_buttons_menu(update, context)


class ChangeButtonName(object):
    def start(self, update, context):
        delete_messages(update, context, True)
        # All users input messages will be deleted at the end or when back
        context.user_data["user_input"] = list()
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="back_to_one_button_menu")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.callback_query.message.chat.id,
                text=context.bot.lang_dict["new_button_name"].format(
                    html.escape(context.user_data["button"]["button"], quote=False)),
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML))
        return ENTER_NEW_NAME

    def finish_new_name(self, update, context):
        delete_messages(update, context, False)
        context.user_data["user_input"].append(update.message)
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="back_to_one_button_menu")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)

        if len(update.message.text) > MAX_BUTTON_NAME_LENGTH:
            delete_messages(update, context, True)
            context.user_data["to_delete"].append(
                context.bot.send_message(update.effective_chat.id,
                                         text=context.bot.lang_dict["invalid_button_name"]
                                         + context.bot.lang_dict["add_menu_buttons_str_1_1"],
                                         reply_markup=reply_markup))
            return ENTER_NEW_NAME

        button_list = custom_buttons_table.find({"bot_id": context.bot.id,
                                                 "button": update.message.text})
        if not button_list.count():
            custom_buttons_table.update_one(
                {"_id": context.user_data["button"]["_id"]},
                {"$set": {"button": update.message.text,
                          "button_lower": update.message.text.replace(" ", "").lower()}})
            return self.finish_change_name(update, context)
        else:
            context.user_data["to_delete"].append(
                update.message.reply_text(
                    context.bot.lang_dict["add_menu_buttons_str_3"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id))
            return ENTER_NEW_NAME

    def finish_change_name(self, update, context):
        if context.user_data["user_input"]:
            context.user_data["to_delete"].extend(context.user_data["user_input"])
        return back_to_one_button_menu(update, context)


class EditButtonHandler(object):
    def content_menu(self, update, context):
        delete_messages(update, context, True)
        for content_dict in context.user_data["button"]["content"]:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["remove_button_str"],
                    callback_data=f"remove_from_content/"
                    f"{content_dict['id']}")]
            ])
            send_content_dict(update.effective_chat.id, context, content_dict,
                              reply_markup=reply_markup, parse_mode=None)

        reply_buttons = [
            [InlineKeyboardButton(
                text=context.bot.lang_dict["add_product_add_content"],
                callback_data="add_new_content")],
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_one_button_menu")]]
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                text=html.escape(context.user_data["button"]["button"], quote=False)
                + "\n\n"
                + context.bot.lang_dict["add_product_to_delete_click"],
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(reply_buttons)))
        return CONTENT_MENU

    def finish_remove_from_content(self, update, context):
        update.callback_query.message.delete()
        content_id = update.callback_query.data.split("/")[1]
        content_dict = next((content_dict for content_dict
                             in context.user_data["button"]["content"]
                             if content_dict["id"] == content_id), {})
        update.callback_query.answer(f"{content_dict_as_string(content_dict, context)}"
                                     + context.bot.lang_dict["add_product_was_removed"])
        button = custom_buttons_table.find_and_modify(
            {"_id": context.user_data["button"]["_id"]},
            {"$pull": {"content": {"id": content_id}}}, new=True)
        if not button:
            return back_to_buttons_menu(update, context)
        context.user_data["button"] = button
        return CONTENT_MENU

    def start_adding_content(self, update, context):
        if len(context.user_data["button"]["content"]) >= MAX_BUTTON_CONTENT_COUNT:
            update.callback_query.answer(context.bot.lang_dict["add_product_10_files"])
            return CONTENT_MENU
        delete_messages(update, context, True)
        # All users input messages will be deleted at the end or when back
        if not context.user_data.get("user_input"):
            context.user_data["user_input"] = list()
        text = (html.escape(context.user_data["button"]["button"], quote=False)
                + "\n\n"
                + context.bot.lang_dict["add_button_add_files"])
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                text=text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=context.bot.lang_dict["back_button"],
                        callback_data="back_to_content_menu")]]),
                parse_mode=ParseMode.HTML
            ))
        return ADDING_CONTENT

    def open_content_handler(self, update, context):
        delete_messages(update, context, False)
        context.user_data["user_input"].append(update.message)
        if len(context.user_data["button"]["content"]) < MAX_BUTTON_CONTENT_COUNT:
            content_dict = create_content_dict(update)
            if content_dict:
                button = custom_buttons_table.find_and_modify(
                    {"_id": context.user_data["button"]["_id"]},
                    {"$push": {"content": content_dict}}, new=True)
                context.user_data["button"] = button
            else:
                context.bot.delete_message(update.effective_chat.id,
                                           update.message.message_id)
                context.user_data["to_delete"].append(
                    context.bot.send_message(
                        update.effective_chat.id,
                        context.bot.lang_dict["content_error"],
                        parse_mode=ParseMode.HTML))
        else:
            return self.content_menu(update, context)
        text = (context.bot.lang_dict["file_added_to"].format(
                    html.escape(context.user_data["button"]["button"], quote=False))
                + "\n\n"
                + context.bot.lang_dict["add_button_add_files"])

        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                text=text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        context.bot.lang_dict["back_button"],
                        callback_data="back_to_content_menu")]]),
                parse_mode=ParseMode.HTML,
                reply_to_message_id=context.user_data["user_input"][-1].message_id))
        return ADDING_CONTENT

    def start_edit_link(self, update, context):
        delete_messages(update, context, True)
        context.user_data["user_input"] = list()
        reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                               callback_data="cancel_link_edit")]]
        reply_markup = InlineKeyboardMarkup(reply_buttons)
        # todo message length fix - if link too long
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                context.bot.lang_dict["add_menu_buttons_str_2_link"]
                + "\n"
                + context.bot.lang_dict["current_link_field"].format(
                    context.user_data["button"]["link"]),
                reply_markup=reply_markup))
        return ENTER_NEW_LINK

    def finish_edit_link(self, update, context):
        delete_messages(update, context, False)
        context.user_data["user_input"].append(update.message)
        link = validate_link(update, context)
        if not link:
            reply_buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                                   callback_data="cancel_link_edit")]]
            reply_markup = InlineKeyboardMarkup(reply_buttons)
            context.user_data["to_delete"].append(
                update.message.reply_text(
                    context.bot.lang_dict["wrong_http_url"],
                    reply_markup=reply_markup,
                    reply_to_message_id=context.user_data["user_input"][-1].message_id))
            return ENTER_NEW_LINK
        else:
            button = custom_buttons_table.find_and_modify(
                {"_id": context.user_data["button"]["_id"]},
                {"$set": {"link": link}}, new=True)
            if button:
                context.user_data["button"] = button
                return self.cancel_link_edit(update, context)
            else:
                return back_to_buttons_menu(update, context)

    def back_to_content_menu(self, update, context):
        if context.user_data["user_input"]:
            context.user_data["to_delete"].extend(context.user_data["user_input"])
        return self.content_menu(update, context)

    def cancel_link_edit(self, update, context):
        if context.user_data["user_input"]:
            context.user_data["to_delete"].extend(context.user_data["user_input"])
        return back_to_one_button_menu(update, context)


BUTTONS_MENU = CallbackQueryHandler(
    callback=buttons_menu,
    pattern="buttons")

ONE_BUTTON_MENU = CallbackQueryHandler(
    pattern=r"one_button_menu",
    callback=one_button_menu)

"""CREATE NEW BUTTON"""
CREATE_BUTTON_CHOOSE = CallbackQueryHandler(callback=AddButtons().start,
                                            pattern="create_button")

"""ADDING LINK BUTTON"""
LINK_BUTTON_ADD_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(callback=AddLinkButton().start,
                                       pattern=r"create_link_button")],

    states={
        TYPING_LINK: [MessageHandler(Filters.text, callback=AddLinkButton().link_handler)],
        TYPING_BUTTON_FINISH: [MessageHandler(Filters.text,
                                              callback=AddLinkButton().button_finish)],

    },

    fallbacks=[
        CallbackQueryHandler(callback=AddCommands().finish_button_creation,
                             pattern="cancel_button_creation")
        # CallbackQueryHandler(callback=AddCommands().back,
        #                      pattern=r"help_module"),
        # CallbackQueryHandler(callback=AddCommands().back,
        #                      pattern=r"help_back"),
    ]
)

"""ADD CONTENT BUTTON"""
BUTTON_ADD_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(callback=AddCommands().start,
                             pattern=r"create_simple_button")
    ],

    states={
        TYPING_BUTTON: [MessageHandler(Filters.text,
                                       AddCommands().button_handler)],
        TYPING_DESCRIPTION: [MessageHandler(Filters.all,
                                            AddCommands().description_handler)],
        DESCRIPTION_FINISH: [MessageHandler(Filters.text,
                                            AddCommands().description_finish)],

    },

    fallbacks=[
        CallbackQueryHandler(callback=AddCommands().description_finish,
                             pattern=r"DONE"),
        CallbackQueryHandler(callback=back_to_buttons_menu,
                             pattern="back_to_buttons_menu"),
        # CallbackQueryHandler(callback=AddCommands().back,
        #                      pattern=r"help_module"),
        CallbackQueryHandler(callback=AddCommands().finish_button_creation,
                             pattern="cancel_button_creation")
    ]
)

DELETE_BUTTON_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(callback=DeleteButton().confirm_delete_button,
                             pattern=r"delete_button")
    ],

    states={
        CONFIRM_DELETE_BUTTON: [
            CallbackQueryHandler(pattern="btn_confirm_delete",
                                 callback=DeleteButton().delete_button_finish)],
    },

    fallbacks=[CallbackQueryHandler(callback=back_to_one_button_menu,
                                    pattern=r"back_to_one_button_menu")]
)


CHANGE_BUTTON_NAME_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CallbackQueryHandler(callback=ChangeButtonName().start,
                             pattern="change_button_name")
    ],

    states={
        ENTER_NEW_NAME: [
            MessageHandler(Filters.text,
                           callback=ChangeButtonName().finish_new_name)]
        },

    fallbacks=[CallbackQueryHandler(callback=ChangeButtonName().finish_change_name,
                                    pattern=r"back_to_one_button_menu")]
)


EDIT_BUTTON_CONTENT_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(callback=EditButtonHandler().content_menu,
                                       pattern="edit_button_content")],
    states={
        CONTENT_MENU: [
            CallbackQueryHandler(
                pattern="add_new_content",
                callback=EditButtonHandler().start_adding_content),
            CallbackQueryHandler(
                pattern=r"remove_from_content",
                callback=EditButtonHandler().finish_remove_from_content)],

        ADDING_CONTENT: [
            MessageHandler(Filters.all,
                           EditButtonHandler().open_content_handler)],
    },

    fallbacks=[CallbackQueryHandler(callback=back_to_one_button_menu,
                                    pattern=r"back_to_one_button_menu"),
               CallbackQueryHandler(callback=EditButtonHandler().back_to_content_menu,
                                    pattern="back_to_content_menu")]
)

EDIT_BUTTON_LINK_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(callback=EditButtonHandler().start_edit_link,
                                       pattern="edit_button_link")],
    states={
        ENTER_NEW_LINK: [MessageHandler(Filters.text,
                                        callback=EditButtonHandler().finish_edit_link)]
    },
    fallbacks=[CallbackQueryHandler(pattern="cancel_link_edit",
                                    callback=EditButtonHandler().cancel_link_edit)]
)

"""BACKS"""
BACK_TO_BUTTONS_MENU = CallbackQueryHandler(
    pattern="back_to_buttons_menu",
    callback=back_to_buttons_menu)

BACK_TO_ONE_BUTTON_MENU = CallbackQueryHandler(
    pattern="back_to_one_button_menu",
    callback=back_to_one_button_menu)
