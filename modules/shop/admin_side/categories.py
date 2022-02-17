import html

from bson import ObjectId
from telegram import InlineKeyboardButton, Update, InlineKeyboardMarkup, ParseMode
from telegram.ext import (ConversationHandler, CallbackQueryHandler,
                          CallbackContext, Filters, MessageHandler)

from modules.shop.admin_side.welcome import Welcome
from helper_funcs.misc import delete_messages
from helper_funcs.constants import MAX_CATEGORY_NAME_LENGTH, MAX_CATEGORIES_COUNT
from database import categories_table, products_table, orders_table
from modules.shop.helper.keyboards import (back_btn)


START_ADD_CATEGORY, SET_CATEGORY, RENAME_CATEGORY = range(3)
DELETE_CATEGORY_CONFIRM = 1


def validate_category_name(name, context):
    result = dict()
    if len(name) > MAX_CATEGORY_NAME_LENGTH:
        result["ok"] = False
        result["error_message"] = context.bot.lang_dict["shop_admin_category_too_long"]
    elif categories_table.find_one({"bot_id": context.bot.id, "name": name}):
        result["ok"] = False
        result["error_message"] = context.bot.lang_dict["category_name_exist"].format(
            html.escape(name, quote=False))
    else:
        result["ok"] = True
        result["name"] = name
    return result


class ProductCategoryHandler(object):
    def menu(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        category_list = categories_table.find({"bot_id": context.bot.id})
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=i["name"],
                                   callback_data=f"edit_category/{i['_id']}")]
             for i in category_list]
            + [[InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_add_category_btn"],
                callback_data="add_shop_category")],
                [back_btn("back_to_main_menu", context)]],
        )

        context.user_data["to_delete"] = [context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=context.bot.lang_dict["products_categories_menu"],
            reply_markup=keyboard)]

        return ConversationHandler.END

    def edit_category_menu(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        category_id = update.callback_query.data.replace("edit_category/", "")
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                context.bot.lang_dict["change_category_name"],
                callback_data="edit_name_shop_category/{}".format(category_id))],
            [InlineKeyboardButton(context.bot.lang_dict["delete_button_str"],
                                  callback_data="delete_shop_category/{}".format(category_id))],

            [back_btn("back_to_admin_categories", context)],
        ])

        context.user_data["to_delete"] = [context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=context.bot.lang_dict["category_edit"],
            reply_markup=keyboard)]

        return ConversationHandler.END

    def delete_category(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        category_id = update.callback_query.data.replace("delete_shop_category/", "")
        products = products_table.find({"bot_id": context.bot.id,
                                        "category_id": ObjectId(category_id),
                                        "in_trash": False})
        new_orders = orders_table.find(
            {"bot_id": context.bot.id,
             "items": {"$elemMatch": {"product.category_id": ObjectId(category_id)}},
             "status": False,
             "in_trash": False})
        all_orders = orders_table.find({"bot_id": context.bot.id,
                                       "category_id": ObjectId(category_id)})
        category = categories_table.find_one({"bot_id": context.bot.id,
                                              "_id": ObjectId(category_id)})
        if new_orders.count():
            context.user_data["category_id"] = category_id
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                      callback_data="back_to_admin_categories")]])
            context.user_data["to_delete"] = [context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["shop_orders_cannot_be_deleted"].format(
                    category["name"], str(new_orders.count())),
                reply_markup=keyboard)]
            # self.menu(update, context)
            return ConversationHandler.END

        if products.count():
            context.user_data["category_id"] = category_id
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(context.bot.lang_dict["yes"],
                                      callback_data="del_cat_confirm")],
                [InlineKeyboardButton(context.bot.lang_dict["no"],
                                      callback_data="back_to_admin_categories")]])
            context.user_data["to_delete"] = [context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["shop_category_will_be_deleted"].format(
                    category["name"], str(products.count()), str(all_orders.count())),
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML)]
            return DELETE_CATEGORY_CONFIRM
        else:
            keyboard = InlineKeyboardMarkup([[back_btn("back_to_admin_categories", context)]])
            categories_table.delete_one({"bot_id": context.bot.id,
                                         "_id": ObjectId(category_id)})
            # It means all orders and products in trash
            # that associated with category will be deleted
            products_table.delete_many({"bot_id": context.bot.id,
                                        "category_id": ObjectId(category_id)})
            orders_table.delete_many(
                {"bot_id": context.bot.id,
                 "items": {"$elemMatch": {"product.category_id": ObjectId(category_id)}}})

            context.user_data["to_delete"] = [context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["category_deleted"].format(category["name"]),
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML)]

            return ConversationHandler.END

    def delete_category_confirm(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        category_id = context.user_data["category_id"]
        category = categories_table.find_one({"bot_id": context.bot.id,
                                              "_id": ObjectId(category_id)})
        categories_table.delete_one({"bot_id": context.bot.id,
                                     "_id": ObjectId(category_id)})
        products_table.delete_many({"bot_id": context.bot.id,
                                    "category_id": ObjectId(category_id)})

        keyboard = InlineKeyboardMarkup([[back_btn("back_to_main_menu", context)]])
        context.user_data["to_delete"] = [context.bot.send_message(
            chat_id=update.callback_query.message.chat_id,
            text=context.bot.lang_dict["category_deleted"].format(category["name"]),
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML)]

        return ConversationHandler.END

    def rename_category(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        context.user_data["category_id"] = update.callback_query.data.replace(
                                                "edit_name_shop_category/", "")
        keyboard = InlineKeyboardMarkup([[back_btn("back_to_admin_categories", context)]])
        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["write_new_category"],
                reply_markup=keyboard))
        return RENAME_CATEGORY

    def rename_category_finish(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        keyboard = InlineKeyboardMarkup([[back_btn("back_to_admin_categories", context)]])
        name_request = validate_category_name(update.message.text, context)
        if name_request["ok"]:
            categories_table.update_one({"_id": ObjectId(context.user_data["category_id"])},
                                        {"$set": {"name": name_request["name"]}})
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=context.bot.lang_dict["shop_category_changed_name"],
                    reply_markup=keyboard))
            return ConversationHandler.END
        else:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=name_request["error_message"],
                    reply_markup=keyboard,
                    parse_mode=ParseMode.HTML))
            return RENAME_CATEGORY

    def add_category(self, update: Update, context: CallbackContext):
        category_list = categories_table.find({"bot_id": context.bot.id})
        if category_list.count() >= MAX_CATEGORIES_COUNT:
            update.callback_query.answer(context.bot.lang_dict["too_much_categories_blink"])
            return ConversationHandler.END
        delete_messages(update, context, True)
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=i["name"],
                                   # callback_data="nigga_dont_touch_me"
                                   callback_data=f"edit_category/{i['_id']}")]
             for i in category_list]
            + [[back_btn("back_to_admin_categories", context)]]
        )

        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.callback_query.message.chat_id,
                text=context.bot.lang_dict["shop_category_add_new"],
                reply_markup=keyboard))

        return START_ADD_CATEGORY

    def set_category(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        if update.message:
            final_text = context.bot.lang_dict["shop_category_add_or_continue"]
            name_request = validate_category_name(update.message.text, context)
            if name_request["ok"]:
                categories_table.insert_one({
                    "name": name_request["name"],
                    "query_name": name_request["name"],
                    "bot_id": context.bot.id
                })
            else:
                final_text = name_request["error_message"]

            category_list = categories_table.find({"bot_id": context.bot.id})
            if category_list.count() >= MAX_CATEGORIES_COUNT:
                return self.back_to_categories_menu(update, context)
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text=i["name"],
                                       callback_data=f"edit_category/{i['_id']}")]
                 for i in category_list]
                + [[back_btn("back_to_admin_categories", context)]]
            )
            context.user_data["to_delete"].append(context.bot.send_message(
                chat_id=update.message.chat_id,
                text=final_text,
                reply_markup=keyboard,
                parse_mode=ParseMode.HTML))
        return START_ADD_CATEGORY

    def back_to_categories_menu(self, update, context):
        delete_messages(update, context, True)
        context.user_data.clear()
        return self.menu(update, context)


CATEGORIES_HANDLER = CallbackQueryHandler(ProductCategoryHandler().edit_category_menu,
                                          pattern=r"edit_category")
EDIT_CATEGORIES_HANDLER = CallbackQueryHandler(ProductCategoryHandler().menu,
                                               pattern=r"categories")
RENAME_CATEGORY_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(ProductCategoryHandler().rename_category,
                                       pattern=r"edit_name_shop_category")],
    states={
        RENAME_CATEGORY: [
            MessageHandler(Filters.text, ProductCategoryHandler().rename_category_finish)],
    },

    fallbacks=[
        CallbackQueryHandler(ProductCategoryHandler().back_to_categories_menu,
                             pattern="back_to_admin_categories"),
        CallbackQueryHandler(Welcome().back_to_main_menu,
                             pattern=r"back_to_main_menu"),
    ]
)
DELETE_CATEGORY_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(ProductCategoryHandler().delete_category,
                                       pattern=r"delete_shop_category")],
    states={DELETE_CATEGORY_CONFIRM: [
        CallbackQueryHandler(ProductCategoryHandler().delete_category_confirm,
                             pattern="del_cat_confirm"),
    ]},
    fallbacks=[
        CallbackQueryHandler(
            pattern="back_to_admin_categories",
            callback=ProductCategoryHandler().back_to_categories_menu),
        CallbackQueryHandler(Welcome().back_to_main_menu,
                             pattern=r"back_to_main_menu"),
    ])
ADD_CATEGORY_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(ProductCategoryHandler().add_category,
                                       pattern=r"add_shop_category")],

    states={  # TODO fix add category
        START_ADD_CATEGORY: [
            MessageHandler(Filters.text, ProductCategoryHandler().set_category)],
    },

    fallbacks=[
        CallbackQueryHandler(ProductCategoryHandler().back_to_categories_menu,
                             pattern="back_to_admin_categories"),
        CallbackQueryHandler(ProductCategoryHandler().edit_category_menu,
                             pattern=r"edit_category"),
        CallbackQueryHandler(Welcome().back_to_main_menu,
                             pattern=r"back_to_main_menu"),
        CallbackQueryHandler(Welcome().back_to_main_menu,
                             pattern=r"help_back"),
    ]
)


BACK_TO_CATEGORIES_MENU = CallbackQueryHandler(
    pattern="back_to_admin_categories",
    callback=ProductCategoryHandler().back_to_categories_menu)
