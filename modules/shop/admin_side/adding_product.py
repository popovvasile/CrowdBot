import html

from telegram import InlineKeyboardButton, Update, InlineKeyboardMarkup, ParseMode
from telegram.ext import (ConversationHandler, CallbackQueryHandler,
                          CallbackContext, Filters, MessageHandler)

from modules.shop.admin_side.welcome import Welcome
from modules.shop.admin_side.categories import validate_category_name, MAX_CATEGORIES_COUNT
from modules.shop.components.product import Product
from modules.shop.helper.keyboards import keyboards, back_btn, create_keyboard
from helper_funcs.misc import delete_messages
from helper_funcs.constants import MAX_TEMP_DESCRIPTION_LENGTH, MAX_PRODUCT_NAME_LENGTH
from database import categories_table, chatbots_table


(START_ADD_PRODUCT, ONLINE_PAYMENT,
 SET_TITLE, SET_CATEGORY, SET_PRICE, SET_DISCOUNT,
 ASK_DESCRIPTION, SET_DESCRIPTION, SET_QUANTITY, CONFIRM_ADDING,
 ADDING_CONTENT, FINISH_ADDING) = range(12)


# EDIT WHAT- CONTENT OR PRODUCT
class AddingProductHandler(object):
    def start(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        buttons = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                         callback_data="back_to_main_menu")]]
        reply_markup = InlineKeyboardMarkup(buttons)
        context.user_data["to_delete"].append(context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=context.bot.lang_dict["shop_admin_product_title"],
            reply_markup=reply_markup))
        return SET_TITLE

    def set_title(self, update: Update, context: CallbackContext):
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        context.user_data["new_product"] = Product(context)
        if len(update.message.text) <= MAX_PRODUCT_NAME_LENGTH:
            context.user_data["new_product"].name = update.message.text
        else:
            context.user_data["to_delete"].append(context.bot.send_message(
                chat_id=update.message.chat_id,
                text=context.bot.lang_dict["shop_admin_name_length_error"],
                reply_markup=InlineKeyboardMarkup([
                             [back_btn("back_to_main_menu_btn", context)]])))
            return SET_TITLE
        delete_messages(update, context, True)

        category_list = categories_table.find({"bot_id": context.bot.id})
        if category_list.count() > 0:
            keyboard = create_keyboard(
                [InlineKeyboardButton(
                    text=i["name"],
                    callback_data=f"choose_category/{i['_id']}")
                    for i in category_list],
                [back_btn("back_to_main_menu_btn", context)])
            context.user_data["new_product"].send_full_template(
                update, context,
                context.bot.lang_dict["shop_admin_set_category_add_product"], keyboard)
        else:
            buttons = [
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["back_button"],
                    callback_data="back_to_main_menu")]]
            reply_markup = InlineKeyboardMarkup(buttons)
            context.user_data["to_delete"].append(context.bot.send_message(
                chat_id=update.message.chat_id,
                text=context.bot.lang_dict["add_product_didnt_set_category"],
                reply_markup=reply_markup))
        return SET_CATEGORY

    def set_category(self, update: Update, context: CallbackContext):
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        delete_messages(update, context, True)
        if update.message:
            final_text = context.bot.lang_dict["shop_admin_set_category_add_product"]
            category_list = categories_table.find({"bot_id": context.bot.id})

            name_request = validate_category_name(update.message.text, context)
            if name_request["ok"]:
                if category_list.count() >= MAX_CATEGORIES_COUNT:
                    final_text = context.bot.lang_dict["too_much_categories_blink"]

                else:
                    categories_table.insert_one({
                        "name": name_request["name"],
                        "query_name": name_request["name"],
                        "bot_id": context.bot.id
                    })
                    category_list = categories_table.find({"bot_id": context.bot.id})
                reply_markup = create_keyboard(
                    [InlineKeyboardButton(
                        text=i["name"],
                        callback_data=f"choose_category/{i['_id']}")
                        for i in category_list],
                    [back_btn("back_to_main_menu_btn", context)])
            else:
                final_text = name_request["error_message"]
                if category_list.count() > 0:
                    reply_markup = create_keyboard(
                        [InlineKeyboardButton(
                            text=i["name"],
                            callback_data=f"choose_category/{i['_id']}")
                            for i in category_list],
                        [back_btn("back_to_main_menu_btn", context)])
                else:
                    reply_markup = InlineKeyboardMarkup([
                        [back_btn("back_to_main_menu_btn", context)]])

            context.user_data["new_product"].send_full_template(
                update, context,
                final_text,
                reply_markup)
            return SET_CATEGORY

    def ask_quantity(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        if update.callback_query:
            context.user_data["new_product"].category_id = (
                update.callback_query.data.split("/")[1])
        context.user_data["new_product"].send_full_template(
            update, context,
            context.bot.lang_dict["shop_admin_write_quantity"],
            InlineKeyboardMarkup([
                [InlineKeyboardButton(text=context.bot.lang_dict["shop_admin_set_unlimited"],
                                      callback_data="unlimited")],
                [back_btn("back_to_main_menu_btn", context)]]))
        return SET_QUANTITY

    def ask_price(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        if update.message:
            quantity_request = context.user_data["new_product"].create_quantity(
                update, context)
            if quantity_request["ok"]:
                context.user_data["new_product"].quantity = quantity_request["quantity"]
                context.user_data["new_product"].unlimited = False
            else:
                context.user_data["to_delete"].append(context.bot.send_message(
                    chat_id=update.message.chat_id,
                    text=quantity_request["error_message"],
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton(
                            text=context.bot.lang_dict["shop_admin_set_unlimited"],
                            callback_data="unlimited")],
                        [back_btn("back_to_main_menu_btn", context)]])))
                return SET_QUANTITY

        elif update.callback_query.data == "unlimited":
            context.user_data["new_product"].quantity = 0
            context.user_data["new_product"].unlimited = True

        context.user_data["new_product"].send_full_template(
            update, context, context.bot.lang_dict["shop_admin_write_your_price"],
            keyboards(context)["back_to_main_menu_keyboard"])
        return SET_PRICE

    def ask_description(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        price_request = context.user_data["new_product"].create_price(update, context)
        if price_request["ok"]:
            context.user_data["new_product"].price = price_request["price"]
            context.user_data["new_product"].discount_price = 0
            context.user_data["new_product"].send_full_template(
                update, context, context.bot.lang_dict["add_product_description"],
                keyboards(context)["back_to_main_menu_keyboard"])
            return SET_DESCRIPTION
        else:
            context.user_data["to_delete"].append(context.bot.send_message(
                chat_id=update.message.chat_id,
                text=price_request["error_message"],
                reply_markup=InlineKeyboardMarkup([
                    [back_btn("back_to_main_menu_btn", context)]]),
                parse_mode=ParseMode.HTML))
            return SET_PRICE

    def set_description(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        if "user_input" not in context.user_data:
            context.user_data["user_input"] = list()
        context.user_data["new_product"].description = update.message.text
        context.user_data["new_product"].send_full_template(
            update, context,
            context.bot.lang_dict["shop_admin_files_adding"],
            keyboards(context)["back_to_main_menu_keyboard"])
        return ADDING_CONTENT

    """
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
    """

    def open_content_handler(self, update, context):
        delete_messages(update, context)
        # delete_list = context.user_data["to_delete"]
        # delete_list.append(update.message)
        if len(context.user_data["new_product"].content) < 10:
            context.user_data["new_product"].add_content_dict(update)
            text = context.bot.lang_dict["shop_admin_send_more_photo"].format(
                len(context.user_data["new_product"].content))
        else:
            text = context.bot.lang_dict["shop_admin_press_continue"]
        context.user_data["new_product"].send_full_template(
            update, context,
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    context.bot.lang_dict["continue_btn"],
                    callback_data="continue"),
                    back_btn("back_to_main_menu_btn", context=context)]
            ]))
        return ADDING_CONTENT

    def confirm_adding(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        currency = chatbots_table.find_one(
            {"bot_id": context.bot.id})["shop"]["currency"]

        category = categories_table.find_one(
            {"_id": context.user_data["new_product"].category_id})["name"]

        if (len(context.user_data["new_product"].description)
                > MAX_TEMP_DESCRIPTION_LENGTH):
            description = context.bot.lang_dict["add_product_description_above"]
        else:
            description = html.escape(context.user_data["new_product"].description, quote=False)

        context.user_data["new_product"].send_full_template(
            update, context,
            context.bot.lang_dict["shop_admin_product_description"].format(
                currency=currency,
                name=html.escape(context.user_data["new_product"].name, quote=False),
                price=context.user_data["new_product"].price,
                quantity=context.user_data["new_product"].quantity_str,
                category=html.escape(category, quote=False),
                description=description),
            keyboards(context)["confirm_add_product"])
        return FINISH_ADDING

    def finish_adding(self, update: Update, context: CallbackContext):
        context.bot.send_chat_action(update.effective_chat.id, "upload_photo")
        context.user_data["new_product"].create()
        return Welcome().back_to_main_menu(
            update, context,
            context.bot.lang_dict["shop_admin_adding_product_finished"])


ADD_PRODUCT_HANDLER = ConversationHandler(
    # persistent=True, name='ADD_PRODUCT_HANDLER'
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(AddingProductHandler().start,
                                       pattern=r"add_product")],

    states={
        SET_TITLE: [
            MessageHandler(Filters.text,
                           AddingProductHandler().set_title)],
        SET_CATEGORY: [
            MessageHandler(Filters.text, AddingProductHandler().set_category),
            CallbackQueryHandler(AddingProductHandler().ask_quantity,
                                 pattern=r"choose_category")],

        # todo 3 regexes vs just Filters.text(it looks like everything works anyway)
        SET_QUANTITY: [CallbackQueryHandler(AddingProductHandler().ask_price,
                                            pattern=r"unlimited"),
                       MessageHandler(Filters.regex(r'(\d+\.\d{1,2})|(\d+\,\d{1,2})'),
                                      AddingProductHandler().ask_price),
                       MessageHandler(Filters.regex(r'^[-+]?([1-9]\d*|0)$'),
                                      AddingProductHandler().ask_price),
                       MessageHandler(Filters.regex(r"^((?!@).)*$"),
                                      AddingProductHandler().ask_price),
                       # MessageHandler(Filters.text,
                       #                AddingProductHandler().ask_price)
                       ],

        # todo 3 regexes vs just Filters.text(it looks like everything works anyway)
        SET_PRICE: [MessageHandler(Filters.regex(r'(\d+\.\d{1,2})|(\d+\,\d{1,2})'),
                                   AddingProductHandler().ask_description),
                    MessageHandler(Filters.regex(r'^[-+]?([1-9]\d*|0)$'),
                                   AddingProductHandler().ask_description),
                    MessageHandler(Filters.regex(r"^((?!@).)*$"),
                                   AddingProductHandler().ask_description)

                    ],


        SET_DESCRIPTION: [
            MessageHandler(Filters.text,
                           AddingProductHandler().set_description)],

        ADDING_CONTENT: [
            MessageHandler(Filters.all,
                           AddingProductHandler().open_content_handler),
            CallbackQueryHandler(AddingProductHandler().confirm_adding,
                                 pattern=r"continue"),
        ],
        FINISH_ADDING: [
            CallbackQueryHandler(AddingProductHandler().finish_adding,
                                 pattern=r"confirm_product")
        ]
    },

    fallbacks=[CallbackQueryHandler(Welcome().back_to_main_menu,
                                    pattern=r"back_to_main_menu"),
               CallbackQueryHandler(Welcome().back_to_main_menu,
                                    pattern=r"help_back")]
)
