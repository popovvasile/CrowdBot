import html
from collections import OrderedDict

from telegram import InlineKeyboardButton

from helper_funcs.auth import if_admin
from modules.shop.helper.keyboards import start_keyboard
from database import (chatbots_table, users_messages_to_admin_table,
                      user_mode_table, carts_table, orders_table)


def help_strings(context, update):
    help_dict = OrderedDict()
    string_d_str = context.bot.lang_dict
    admins_keyboard = start_keyboard(context, back_button=False, as_list=True)
    chatbot = chatbots_table.find_one({"bot_id": context.bot.id})
    shop = chatbot.get("shop", {})
    cart = carts_table.find_one({"bot_id": context.bot.id,
                                 "user_id": update.effective_user.id}) or {}
    cart_button_text = context.bot.lang_dict["shop_cart"]
    cart_items_count = len(cart.get("products", list()))
    if cart_items_count:
        cart_button_text += f" ({cart_items_count})"
    if chatbots_table.find_one({"bot_id": context.bot.id}).get("premium", False):
        user_keyboard_shop = [
            [InlineKeyboardButton(text=context.bot.lang_dict["shop_catalog"],
                                  callback_data="open_shop")],
            [InlineKeyboardButton(text=context.bot.lang_dict["shop_my_orders"],
                                  callback_data="my_orders")],
            [InlineKeyboardButton(text=cart_button_text,
                                  callback_data="cart")]]
        if shop.get("shipping") is False:
            user_keyboard_shop += [
                [InlineKeyboardButton(text=context.bot.lang_dict["shop_contact_and_address"],
                                      callback_data="contacts_shop")]]
        help_dict["shop"] = dict(
            mod_name=string_d_str["shop_admin_add_product_btn"],
            admin_keyboard=admins_keyboard,
            admin_help=string_d_str["shop_admin_start_message"],
            visitor_help=html.escape(shop.get("description", "")),
            visitor_keyboard=user_keyboard_shop)
    else:
        help_dict["shop"] = dict(  # TODO notification for users
            mod_name=string_d_str["shop_admin_add_product_btn"],
            admin_keyboard=admins_keyboard,
            admin_help=string_d_str["shop_admin_start_message_not_paid"],
            visitor_help="Shop is not available",
        )
    help_dict["settings"] = dict(
        mod_name=["add_menu_module_button"],
        admin_keyboard=[
            [InlineKeyboardButton(text=string_d_str["lang_menu_button"],
                                  callback_data="langmenu")],
            [InlineKeyboardButton(text=string_d_str["edit_menu_text"],
                                  callback_data="edit_bot_description")],
            # [InlineKeyboardButton(text=string_d_str["edit_bot_pic_btn"],
            #                       callback_data="edit_bot_pic")],
            [InlineKeyboardButton(text=string_d_str["menu_buttons_settings"],
                                  callback_data="buttons")],
            [InlineKeyboardButton(text=string_d_str["admins_btn_str"],
                                  callback_data="admins")],
            [InlineKeyboardButton(text=string_d_str["statistic_btn_str"],
                                  callback_data="users_statistic")],
            [InlineKeyboardButton(text=string_d_str["notification_btn_str"],
                                  callback_data="notification_setting")]
        ],
        admin_help=string_d_str["add_menu_buttons_help"]
    )

    help_dict["guides"] = dict(
        mod_name="guides",
        admin_keyboard=[],
        admin_help="\n\n".join([
            string_d_str["guide_store_design"],
            string_d_str["guide_user_mode"],
            string_d_str["guide_users_and_feedback"],
            string_d_str["guide_store_management"]
        ]) + string_d_str["guide_post_title"]
    )

    current_user_mode = user_mode_table.find_one(
        {"bot_id": context.bot.id,
         "user_id": update.effective_user.id})
    if current_user_mode:
        if if_admin(update, context) and not current_user_mode.get("user_mode"):
            messages_mode = string_d_str["users_module"]
        else:
            messages_mode = string_d_str["send_message_module_str"]
    else:

        user_mode_table.update_one(filter=dict(bot_id=context.bot.id),
                                   update={
                                       "$set": dict(
                                           bot_id=context.bot.id,
                                           user_id=update.effective_user.id,
                                           user_mode=False)},
                                   upsert=True)
        messages_mode = string_d_str["users_module"]

    new_messages_count = users_messages_to_admin_table.find(
        {"bot_id": context.bot.id,
         "is_new": True,
         "deleted": False}).count()
    messages_button_text = string_d_str["messages"]
    if new_messages_count:
        messages_button_text += f" ({new_messages_count})"
    help_dict["users"] = dict(
        mod_name=messages_mode,
        admin_help=string_d_str["users_help_admin"],
        admin_keyboard=[
            [InlineKeyboardButton(text=messages_button_text,
                                  callback_data="admin_messages")],
            [InlineKeyboardButton(text=string_d_str["users_module"],
                                  callback_data="users_layout")]
        ]
    )

    return help_dict


def helpable_dict(bot):
    # Get unread messages count.
    new_messages_count = users_messages_to_admin_table.find(
        {"bot_id": bot.id,
         "is_new": True,
         "deleted": False}).count()
    # Create unread messages string
    new_messages_str = (f" ({new_messages_count})"
                        if new_messages_count else "")

    admin_rus = OrderedDict()
    admin_eng = OrderedDict()
    admin_de = OrderedDict()

    user_mode_eng = OrderedDict()
    user_mode_eng["✉️ Message"] = "users"
    user_mode_eng["Admin view"] = "user_mode"

    user_mode_rus = OrderedDict()
    user_mode_rus["Режим админа"] = "user_mode"
    user_mode_rus["✉️ Сообщения"] = "users"

    user_mode_de = OrderedDict()
    user_mode_de["✉️ Message"] = "users"
    user_mode_de["Admin view"] = "user_mode"

    user_eng = OrderedDict()
    user_eng["✉️ Message"] = "users"

    user_rus = OrderedDict()
    user_rus["✉️ Сообщения"] = "users"

    user_de = OrderedDict()
    user_de["✉️ Message"] = "users"

    # if chatbots_table.find_one({"bot_id": bot.id}).get("premium", False):
    admin_rus["💰 Магазин"] = "shop"
    admin_eng["💰 Shop"] = "shop"
    admin_de["💰 Shop"] = "shop"

    user_mode_rus["💰 Магазин"] = "shop"
    user_mode_eng["💰 Shop"] = "shop"
    user_mode_de["💰 Shop"] = "shop"

    user_rus["💰 Магазин"] = "shop"
    user_eng["💰 Shop"] = "shop"
    user_de["💰 Shop"] = "shop"

    admin_rus[f"✉️ Пользователи и Сообщения {new_messages_str}"] = "users"
    admin_rus["⚙ Настройки бота"] = "settings"
    admin_rus["🧐 Гайды"] = "guides"

    admin_eng[f"✉️ Users & Messages {new_messages_str}"] = "users"
    admin_eng["⚙ Settings"] = "settings"
    admin_eng["🧐 Guides"] = "guides"

    admin_de[f"✉️ Benutzer & Nachrichten {new_messages_str}"] = "users"
    admin_de["⚙️ Einstellungen"] = "settings"
    admin_de["🧐 Guides"] = "guides"

    lang_dicts = {
        "en": dict(
            ALL_MODULES=[],
            ADMIN_HELPABLE=admin_eng,
            ADMIN_USER_MODE=user_mode_eng,
            VISITOR_HELPABLE=user_eng,
        ),
        "ru": dict(
            ALL_MODULES=[],
            ADMIN_HELPABLE=admin_rus,
            ADMIN_USER_MODE=user_mode_rus,
            VISITOR_HELPABLE=user_rus,
        ),
        "de": dict(
            ALL_MODULES=[],
            ADMIN_HELPABLE=admin_de,
            ADMIN_USER_MODE=user_mode_de,
            VISITOR_HELPABLE=user_de,
        )
    }
    chatbot = chatbots_table.find_one({"bot_id": bot.id})

    return lang_dicts[chatbot["lang"]]
