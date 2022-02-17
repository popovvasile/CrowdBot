from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from database import chatbots_table, orders_table


def start_keyboard(context, back_button=True, as_list=False):
    chatbot = chatbots_table.find_one({"bot_id": context.bot.id})
    new_orders_quantity = orders_table.find({"bot_id": context.bot.id,
                                             "status": False,
                                             "in_trash": False}).count()
    orders_btn_text = context.bot.lang_dict["shop_admin_orders_btn"]
    if new_orders_quantity:
        orders_btn_text += f" ({new_orders_quantity})"

    keyboard = []

    if chatbot.get("shop_enabled", None) is True and chatbot.get("premium", None) is True:
        keyboard = [
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_add_product_btn"],
                                  callback_data="add_product")],
            [InlineKeyboardButton(orders_btn_text,
                                  callback_data="orders")],
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_products_btn"],
                                  callback_data="products")],
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_categories_btn"],
                                  callback_data="categories")],
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_trash_btn"],
                                  callback_data="trash")],
            [InlineKeyboardButton(text=context.bot.lang_dict["configure_button"],
                                  callback_data="shop_config")]]
    elif "shop" in chatbot and chatbot.get("premium", None) is True :
        keyboard = [[InlineKeyboardButton(text=context.bot.lang_dict["turn_shop_on"],
                                          callback_data="change_shop_config")]]
    elif chatbot.get("premium", None) is True:
        keyboard = [[InlineKeyboardButton(text=context.bot.lang_dict["allow_shop_button"],
                                          callback_data='allow_shop')]]

    if back_button:
        keyboard.append([InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                              callback_data="help_back")])
    return keyboard if as_list else InlineKeyboardMarkup(keyboard)


def currency_markup(context):
    # [["RUB", "USD", "EUR", "GBP"], ["KZT", "UAH", "RON", "PLN"]]
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(text="RUB", callback_data="currency/RUB"),
         InlineKeyboardButton(text="USD", callback_data="currency/USD"),
         InlineKeyboardButton(text="EUR", callback_data="currency/EUR"),
         InlineKeyboardButton(text="GBP", callback_data="currency/GBP")],

        [InlineKeyboardButton(text="KZT", callback_data="currency/KZT"),
         InlineKeyboardButton(text="UAH", callback_data="currency/UAH"),
         InlineKeyboardButton(text="RON", callback_data="currency/RON"),
         InlineKeyboardButton(text="PLN", callback_data="currency/PLN")],
        [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                              callback_data="help_module(shop)")]
    ])


def create_keyboard(buttons, extra_buttons):
    pairs = list(zip(buttons[::2], buttons[1::2]))
    if len(buttons) % 2 == 1:
        pairs.append((buttons[-1],))
    pairs.extend([extra_buttons])
    return InlineKeyboardMarkup(pairs)


def back_btn(callback_data: str, context):
    return InlineKeyboardButton(
        context.bot.lang_dict["back_button"], callback_data=callback_data)


def back_kb(callback_data: str, context):
    return InlineKeyboardMarkup([[back_btn(callback_data, context)]])


def keyboards(context):
    keyboards = dict(
        back_to_edit=InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_edit")]]),
        back_to_main_menu_keyboard=InlineKeyboardMarkup([
            [back_btn("back_to_main_menu_btn", context=context)]
        ]),
        back_to_products=InlineKeyboardMarkup([
            [back_btn("back_to_products_btn", context=context)]
        ]),
        back_to_brands=InlineKeyboardMarkup([
            [back_btn("back_to_brands_btn", context=context)]
        ]),
        confirm_add_product=InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_confirm_btn"],
                                  callback_data="confirm_product")],
            [back_btn("back_to_main_menu_btn", context=context)]
        ]),
        continue_back_kb=InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["continue_btn"],
                                  callback_data="continue"),
             back_btn("back_to_main_menu_btn", context=context)]
        ]),
        confirm_to_done=InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["done_button"],
                                  callback_data="finish_to_done")],
            # [InlineKeyboardButton(context.bot.lang_dict["shop_admin_add_product_btn"],
            #                       callback_data="add_product_to_order")],
            # [InlineKeyboardButton(context.bot.lang_dict["shop_admin_edit_btn"],
            #                       callback_data=f"edit")],
            [back_btn("back_to_orders_btn", context=context)]
        ]),
        confirm_to_trash=InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_to_trash_yes"],
                                  callback_data="finish_to_trash"),
             back_btn("back_to_orders_btn", context=context)]
        ]),
        confirm_cancel=InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["cancel_button"],
                                  callback_data="finish_cancel"),
             back_btn("back_to_orders_btn", context=context)]
        ]),
        edit_keyboard=InlineKeyboardMarkup([
            [InlineKeyboardButton(context.bot.lang_dict["shop_admin_add_product_btn"],
                                  callback_data="add_to_order")],
            [back_btn("back_to_orders_btn", context=context)]
        ]))
    return keyboards
