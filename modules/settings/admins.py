# #!/usr/bin/env python
# # -*- coding: utf-8 -*-
from datetime import datetime
import secrets
import string

from bson.objectid import ObjectId
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ParseMode
from telegram.ext import ConversationHandler, CallbackQueryHandler

from database import users_table, admin_passwords_table
from helper_funcs.pagination import Pagination
from helper_funcs.misc import (delete_messages, lang_timestamp, get_obj, update_user_fields,
                               user_mention)
from helper_funcs.helper import back_from_button_handler


class Admin:
    def __init__(self, context, obj: (ObjectId, dict, str)):
        self.context = context
        obj = get_obj(users_table, obj)
        self._id = obj["_id"]
        self.user_id = obj["user_id"]
        self.full_name = obj["full_name"]
        self.username = obj["username"]
        self.timestamp = lang_timestamp(self.context, obj.get("timestamp"))
        self.unsubscribed = obj["unsubscribed"]

    def send_template(self, update, text="", reply_markup=None):
        self.context.user_data["to_delete"].append(
            self.context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"{self.template}\n\n{text}",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup if reply_markup
                else self.reply_markup))

    @property
    def template(self):
        if self.username:
            _user_mention = user_mention(self.username, self.full_name)
        else:
            _user_mention = f'<a href="tg://user?id={self.user_id}">{self.full_name}</a>'
        return self.context.bot.lang_dict["registered_admin_temp"].format(
                _user_mention, self.timestamp)

    @property
    def reply_markup(self):
        reply_markup = [
            [InlineKeyboardButton(
                text=self.context.bot.lang_dict["delete_button_str"],
                callback_data=f"delete_admin/{self._id}")]]
        return InlineKeyboardMarkup(reply_markup)

    def delete(self):
        users_table.update_one({"_id": self._id},
                               {"$set": {"is_admin": False}})

    @staticmethod
    def get_all(context):
        return users_table.find({"bot_id": context.bot.id,
                                 "is_admin": True,
                                 "superuser": False}).sort([["_id", -1]])


class AdminHandler(object):
    def admins(self, update, context):
        delete_messages(update, context, True)
        # Set current page integer in user_data.
        if update.callback_query.data.startswith("admins_list_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("admins_list_pagination_", ""))
        if not context.user_data.get("page"):
            context.user_data["page"] = 1
        self.send_admins_layout(update, context)
        return ADMINS

    def send_admins_layout(self, update, context):
        all_admins = Admin.get_all(context)
        # context.user_data['to_delete'].append(
        #     context.bot.send_message(
        #         chat_id=update.callback_query.message.chat_id,
        #         text=context.bot.lang_dict["admins_layout_title"].format(all_admins.count()),
        #         parse_mode=ParseMode.HTML))
        buttons = [
            [InlineKeyboardButton(
                text=context.bot.lang_dict["add_admin_btn_str"],
                callback_data="start_add_admins")],
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="help_module(settings)")]]
        if all_admins.count() == 0:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["no_admins_str"],
                    reply_markup=InlineKeyboardMarkup(buttons)))
        else:
            pagination = Pagination(all_admins, context.user_data["page"])
            for admin in pagination.content:
                update_user_fields(context, admin)
                Admin(context, admin).send_template(update)
            pagination.send_keyboard(
                update, context,
                page_prefix="admins_list_pagination",
                text=context.bot.lang_dict["admins_layout_title"].format(all_admins.count()),
                buttons=buttons)

    def confirm_delete_admin(self, update, context):
        delete_messages(update, context, True)
        context.user_data["admin"] = Admin(
            context, update.callback_query.data.split("/")[1])
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=context.bot.lang_dict["delete_button_str"],
                callback_data="finish_delete_admin")],
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_admin_list")]
        ])
        context.user_data["admin"].send_template(
            update, reply_markup=reply_markup,
            text=context.bot.lang_dict["confirm_delete_admin_str"])
        return CONFIRM_DELETE_ADMIN

    def finish_delete_admin(self, update, context):
        delete_messages(update, context, True)
        context.user_data["admin"].delete()
        update.callback_query.answer(context.bot.lang_dict["admin_deleted_blink"])
        return self.back_to_admins_list(update, context)

    def start_add_admins(self, update, context):
        delete_messages(update, context, True)
        # Create 10 character length password
        password = "".join(secrets.choice(
            string.ascii_letters + string.digits) for i in range(10))
        # Created separate collection for the admins passwords
        # because when u click "Add admin" button(create new admin link)
        # u need to keep before created links active.
        # Save password to db to invalid it after bots registration.
        admin_passwords_table.insert_one(
            {"bot_id": context.bot.id,
             "password": password,
             "timestamp": datetime.now()})
        # Message that must be forwarded to admin.
        # print(context.bot.get_me().mention_html())
        context.user_data['to_delete'].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=context.bot.lang_dict["admin_invite"].format(
                    # context.bot.get_me().mention_html()
                    f'<a href="t.me/{context.bot.username}">{context.bot.name}</a>'
                    # f'<a href="{context.bot.get_me().link}">{context.bot.name}</a>'

                ),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=context.bot.lang_dict["admin_invite_btn"],
                        url=f"https://t.me/{context.bot.username}?"
                            f"start=registration" + password)]
                ]),
                parse_mode=ParseMode.HTML))

        context.user_data['to_delete'].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=context.bot.lang_dict["add_admin_menu"],
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=context.bot.lang_dict["back_button"],
                        callback_data="back_to_admin_list")]])
            ))
        return ADD_ADMINS

    def back_to_admins_list(self, update, context):
        delete_messages(update, context, True)
        page = context.user_data.get("page")
        context.user_data.clear()
        context.user_data["page"] = page
        return self.admins(update, context)

    def back(self, update, context):
        back_from_button_handler(update, context)
        context.user_data.clear()
        return ConversationHandler.END


ADMINS, CONFIRM_DELETE_ADMIN, ADD_ADMINS = range(3)


ADMINS_LIST_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(pattern="admins",
                                       callback=AdminHandler().admins)],

    states={
        ADMINS: [
            CallbackQueryHandler(
                pattern=r"admins_list_pagination",
                callback=AdminHandler().admins),
            CallbackQueryHandler(
                pattern=r"delete_admin",
                callback=AdminHandler().confirm_delete_admin),
            CallbackQueryHandler(
                pattern="start_add_admins",
                callback=AdminHandler().start_add_admins)],

        CONFIRM_DELETE_ADMIN: [
            CallbackQueryHandler(
                pattern=r"finish_delete_admin",
                callback=AdminHandler().finish_delete_admin)]

        # ADD_ADMINS: [
        #     MessageHandler(callback=AdminHandler().continue_add_admins,
        #                    filters=Filters.text),
        #     CallbackQueryHandler(AdminHandler().finish_add_admins,
        #                          pattern=r"finish_add_admins")]
    },

    fallbacks=[
        CallbackQueryHandler(pattern=r"help_module",
                             callback=AdminHandler().back),
        CallbackQueryHandler(pattern=r"back_to_admin_list",
                             callback=AdminHandler().back_to_admins_list)]
)
