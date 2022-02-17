import html
from bson import ObjectId

from telegram import Update, ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ConversationHandler, CallbackQueryHandler,
                          CallbackContext, MessageHandler, Filters)

from helper_funcs.pagination import Pagination
from helper_funcs.misc import delete_messages, content_dict_as_string
from modules.shop.helper.helper import clear_user_data
from modules.shop.helper.keyboards import keyboards, create_keyboard
from modules.shop.components.product import (Product, MAX_TEMP_DESCRIPTION_LENGTH,
                                             MAX_PRODUCT_NAME_LENGTH)
from modules.shop.admin_side.welcome import Welcome
from modules.shop.admin_side.categories import validate_category_name, MAX_CATEGORIES_COUNT
from database import products_table, categories_table, chatbots_table, orders_table


class ProductsHelper(object):
    # TODO put this logic to the components/product -> class AdminProduct
    """All "short" templates must be passed to send_short_template() method.
    And all "full" templates must be passed to send_full_template() method.
    """

    @staticmethod
    def product_keyboard(context, product_obj: Product):
        """Create keyboard for product in "item list" and "trash list" """
        reply_markup = [[]]
        if product_obj.in_trash:
            reply_markup[0].append(
                InlineKeyboardButton(
                    text=context.bot.lang_dict["shop_admin_restore_btn"],
                    callback_data=f"restore_product/{product_obj.id_}"))
            return InlineKeyboardMarkup(reply_markup)
        reply_markup[0].append(
            InlineKeyboardButton(
                text=context.bot.lang_dict["shop_admin_edit_btn"],
                callback_data=f"edit_product/{product_obj.id_}"))
        orders = orders_table.find(
                {"bot_id": context.bot.id,
                 "status": False,
                 "in_trash": False,
                 "items.product_id": product_obj.id_})
        if not orders.count():
            reply_markup[0].append(
                InlineKeyboardButton(
                    text=context.bot.lang_dict["shop_admin_to_trash_btn"],
                    callback_data=f"to_trash/{product_obj.id_}"))
        return InlineKeyboardMarkup(reply_markup)

    @staticmethod
    def admin_short_template(context, product_obj: Product) -> str:
        """Admin short text representation of the product"""
        shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]
        # List of the NEW(status=False) orders
        new_orders = orders_table.find(
            {"bot_id": context.bot.id,
             "status": False,
             "in_trash": False,
             "items.product_id": product_obj.id_})

        template = context.bot.lang_dict["shop_admin_product_template"].format(
            product_obj.status_str,
            product_obj.article,
            html.escape(product_obj.name, quote=False),
            html.escape(product_obj.category["name"], quote=False),
            product_obj.price_as_str(shop["currency"]),
            product_obj.quantity_str)
        # TODO - refactor need to do better - Product class
        orders_string = ""
        if new_orders.count():
            # How many items wait for the customers now
            orders_string += context.bot.lang_dict["product_temp_part"]
            for order in new_orders[:3]:
                product_items_count = next(
                    item for item in order["items"]
                    if item["product_id"] == product_obj.id_)["quantity"]

                if order["shipping"]:
                    emoji = "🚚"
                else:
                    emoji = "🖐"

                orders_string += (
                    context.bot.lang_dict["product_temp_part_2"].format(
                        order["article"], emoji, product_items_count))
            if new_orders.count() > 3:
                orders_string = orders_string[:-1] + "..."
            else:
                orders_string = orders_string[:-2]
            template += orders_string
        return template

    @staticmethod
    def admin_full_template(context, product_obj: Product) -> str:
        """Admin full text representation of the product"""

        if len(product_obj.description) > MAX_TEMP_DESCRIPTION_LENGTH:
            description = context.bot.lang_dict["add_product_description_above"]
        else:
            description = product_obj.description

        return context.bot.lang_dict["shop_admin_full_product_template"].format(
            product_obj.status_str,
            product_obj.article,
            html.escape(product_obj.name, quote=False),
            html.escape(product_obj.category["name"], quote=False),
            product_obj.price_as_str(),
            product_obj.quantity_str,
            html.escape(description, quote=False))

    @staticmethod
    def status_str(product_obj, new_orders):
        # Admin product status string.
        # Product was deleted
        if product_obj.in_trash:
            status = "🗑 Deleted"
        # At least on item of the product on sale
        elif product_obj.on_sale:
            status = "✅ On Sale"
        # Product not on sale because it is in the NEW order
        elif new_orders.count():
            status = f"🕐 {new_orders.count()} unfinished order(s)"
        else:
            status = "💸 Sold"
        return status


class ProductsHandler(ProductsHelper):
    def products(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith("item_list_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("item_list_pagination_", ""))
        if not context.user_data.get("page"):
            context.user_data["page"] = 1

        all_products = products_table.find({
            "in_trash": False,
            "bot_id": context.bot.id}).sort([["last_modify_timestamp", -1]])
        return self.products_layout(
            update, context, all_products, PRODUCTS)

    @classmethod
    def products_layout(cls, update, context, all_products, state):
        """This Method works for the admin item list and for the item trash"""
        # Send Title..

        buttons = [[InlineKeyboardButton(context.bot.lang_dict["back_button"],
                                         callback_data="back_to_main_menu")]]
        if all_products.count() == 0:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["shop_admin_no_products"],
                    reply_markup=InlineKeyboardMarkup(buttons)
                ))
        else:
            pagination = Pagination(all_products,
                                    page=context.user_data["page"])
            for product in pagination.content:
                prod_obj = Product(context=context, obj=product)
                prod_obj.send_short_template(
                    update, context,
                    text=cls.admin_short_template(context, prod_obj),
                    reply_markup=cls.product_keyboard(context, prod_obj))
            pagination.send_keyboard(
                update, context, buttons,
                page_prefix="item_list_pagination",
                text=context.bot.lang_dict["shop_admin_products_title"].format(
                    all_products.count()))
        return state

    def edit(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        if update.callback_query and update.callback_query.data.startswith("edit_product"):
            product_id = update.callback_query.data.split("/")[1]
            context.user_data["product"] = Product(context, product_id)
            # TODO fix NoneType when creating the Product object

        text = self.admin_full_template(context, context.user_data["product"])
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_set_discount_btn"],
                callback_data='change_discount'),
                InlineKeyboardButton(
                    context.bot.lang_dict["shop_admin_set_price_btn"],
                    callback_data="change_price")],
            [InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_set_description_btn"],
                callback_data="change_description"),
                InlineKeyboardButton(
                    context.bot.lang_dict["shop_admin_set_name_btn"],
                    callback_data="change_name")],
            [InlineKeyboardButton(
                context.bot.lang_dict["add_product_content"],
                callback_data="content_menu"),
                InlineKeyboardButton(
                    context.bot.lang_dict["shop_admin_set_category_btn"],
                    callback_data="change_category")],
            [InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_set_quantity_btn"],
                callback_data="change_quantity")],
            [InlineKeyboardButton(
                context.bot.lang_dict["back_button"],
                callback_data="back_to_products_btn")]])

        context.user_data["product"].send_full_template(
            update, context, text=text, reply_markup=reply_markup)
        return EDIT

    def description(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_set_description"])
        context.user_data["product"].send_short_template(
            update, context,
            text=text, reply_markup=keyboards(context)["back_to_edit"])
        return DESCRIPTION

    def finish_description(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        context.user_data["product"].update(
            {"description": update.message.text})
        return self.edit(update, context)

    def name(self, update: Update, context: CallbackContext, msg=None):
        delete_messages(update, context, True)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_change_name"])
        context.user_data["product"].send_short_template(
            update, context,
            text=text, reply_markup=keyboards(context)["back_to_edit"])
        if msg:
            context.bot.send_message(
                update.effective_chat.id,
                context.bot.lang_dict["shop_admin_name_length_error"])
        return NAME

    def finish_name(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        if len(update.message.text) > MAX_PRODUCT_NAME_LENGTH:
            return self.name(update, context, msg=True)
        context.user_data["product"].update(
            {"name": update.message.text})
        return self.edit(update, context)

    def price(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_set_price"])
        context.user_data["product"].send_short_template(
            update, context,
            text=text, reply_markup=keyboards(context)["back_to_edit"])
        return PRICE

    def finish_price(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        price_request = context.user_data["product"].create_price(update, context)
        if price_request["ok"]:
            context.user_data["product"].update({"price": price_request["price"]})
            # Remove discount price if new price smaller than discount
            if context.user_data["product"].discount_price > price_request["price"]:
                context.user_data["product"].update({"discount_price": 0})
            return self.edit(update, context)
        else:
            text = (self.admin_short_template(context, context.user_data["product"])
                    + "\n\n"
                    + price_request["error_message"]
                    + "\n\n"
                    + context.bot.lang_dict["shop_admin_set_price"])
            context.user_data["product"].send_short_template(
                update, context,
                text=text, reply_markup=keyboards(context)["back_to_edit"])
            return PRICE

    def discount_price(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_set_discount_price"])
        reply_markup = []
        if context.user_data["product"].discount_price:
            reply_markup.append(
                [InlineKeyboardButton(text=context.bot.lang_dict["remove_discount"],
                                      callback_data="remove_discount")])
        reply_markup.append(
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_edit")])
        context.user_data["product"].send_short_template(
            update, context,
            text=text, reply_markup=InlineKeyboardMarkup(reply_markup))
        return DISCOUNT_PRICE

    def finish_discount_price(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        price_request = context.user_data["product"].create_price(update, context)
        if price_request["ok"]:
            if price_request["price"] >= context.user_data["product"].price:
                text = (self.admin_short_template(context, context.user_data["product"])
                        + "\n\n"
                        + context.bot.lang_dict["shop_admin_discount_bigger_than_price"]
                        + "\n\n"
                        + context.bot.lang_dict["shop_admin_set_discount_price"])
            else:
                context.user_data["product"].update({"discount_price": price_request["price"]})
                return self.edit(update, context)
        else:
            text = (self.admin_short_template(context, context.user_data["product"])
                    + "\n\n"
                    + price_request["error_message"]
                    + "\n\n"
                    + context.bot.lang_dict["shop_admin_set_discount_price"])
        context.user_data["product"].send_short_template(
            update, context,
            text=text, reply_markup=keyboards(context)["back_to_edit"])
        return DISCOUNT_PRICE

    def remove_discount(self, update, context):
        context.user_data["product"].update({"discount_price": 0})
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_set_discount_price"])
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_edit")]])

        if update.effective_message.caption:
            update.effective_message.edit_caption(caption=text, parse_mode=ParseMode.HTML)
        else:
            update.effective_message.edit_text(text=text, parse_mode=ParseMode.HTML)
        update.effective_message.edit_reply_markup(reply_markup=reply_markup)
        update.callback_query.answer(text=context.bot.lang_dict["discount_removed_blink"])
        return DISCOUNT_PRICE

    def content_menu(self, update, context):
        delete_messages(update, context, True)
        for content_dict in context.user_data["product"].content:
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["remove_button_str"],
                    callback_data=f"remove_from_content/"
                    f"{content_dict['id']}")]
            ])
            Product.send_content(update.effective_chat.id, context,
                                 content_dict, reply_markup=reply_markup)

        buttons = [
            [InlineKeyboardButton(
                text=context.bot.lang_dict["add_product_add_content"],
                callback_data="add_new_content")],
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_edit")]]
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["add_product_to_delete_click"])
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)))

        return CONTENT_MENU

    def finish_remove_from_content(self, update, context):
        update.callback_query.message.delete()
        content_id = update.callback_query.data.split("/")[1]
        content_dict = next((content_dict for content_dict
                             in context.user_data["product"].content
                             if content_dict["id"] == content_id), {})
        update.callback_query.answer(f"{content_dict_as_string(content_dict, context)}"
                                     + context.bot.lang_dict["add_product_was_removed"])
        product = products_table.find_and_modify(
            {"_id": context.user_data["product"].id_},
            {"$pull": {"content": {"id": content_id}}}, new=True)
        context.user_data["product"] = Product(context, product)
        return CONTENT_MENU

    def start_adding_content(self, update: Update, context: CallbackContext):
        if len(context.user_data["product"].content) >= 10:
            update.callback_query.answer(context.bot.lang_dict["add_product_10_files"])
            return CONTENT_MENU
        delete_messages(update, context, True)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["add_product_add_files"]
                + context.user_data['product'].files_str)

        context.user_data["product"].send_full_template(
            update, context,
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["back_button"],
                    callback_data="back_to_content_menu")]
            ]))
        return ADDING_CONTENT

    def open_content_handler(self, update, context):
        delete_messages(update, context, True)
        if len(context.user_data["product"].content) < 10:
            context.user_data["product"].add_content_dict(update, to_save=True)
        else:
            # update.callback_query == None
            # update.callback_query.answer(context.bot.lang_dict["add_product_10_files"])
            return self.content_menu(update, context)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["add_product_add_files"]
                + context.user_data['product'].files_str)

        context.user_data["product"].send_full_template(
            update, context,
            text=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    context.bot.lang_dict["back_button"],
                    callback_data="back_to_content_menu")]
            ]))
        return ADDING_CONTENT

    def category(self, update: Update, context: CallbackContext, extra_text=""):
        delete_messages(update, context, True)
        category_list = categories_table.find({"bot_id": context.bot.id})
        if category_list.count() > 0:
            keyboard = create_keyboard(
                [InlineKeyboardButton(text=i["name"],
                                      callback_data=f"category_{i['_id']}")
                 for i in category_list],
                [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                      callback_data="back_to_edit")])

            text = (self.admin_short_template(context, context.user_data["product"])
                    + "\n\n"
                    + context.bot.lang_dict["shop_admin_set_category"])
            if extra_text:
                text += extra_text

            context.user_data["product"].send_short_template(
                update, context, text=text, reply_markup=keyboard)
        else:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=context.bot.lang_dict["add_product_didnt_set_category"],
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=context.bot.lang_dict["back_button"],
                        callback_data="back_to_edit")]
                ]))
        return CATEGORY

    def finish_category(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        if update.callback_query:
            context.user_data["product"].update(
                {"category_id": ObjectId(update.callback_query.data.replace("category_", ""))})
        else:
            if update.message:
                categories = categories_table.find({"bot_id": context.bot.id})
                if categories.count() >= MAX_CATEGORIES_COUNT:
                    return self.category(
                        update, context,
                        extra_text="\n" + context.bot.lang_dict["too_much_categories_blink"])
                else:
                    name_request = validate_category_name(update.message.text, context)
                    if name_request["ok"]:
                        category_id = categories_table.insert_one({
                            "name": name_request["name"],
                            "query_name": name_request["name"],
                            "bot_id": context.bot.id}).inserted_id
                        context.user_data["product"].update({"category_id": category_id})
                        return self.edit(update, context)
                    else:
                        return self.category(update, context,
                                             extra_text="\n" + name_request["error_message"])
        return self.edit(update, context)

    def confirm_to_trash(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        product_id = update.callback_query.data.split("/")[1]
        context.user_data["product"] = Product(context, product_id)

        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_confirm_to_trash_product"])

        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_to_trash_yes"],
                callback_data="finish_to_trash"),
                InlineKeyboardButton(
                    text=context.bot.lang_dict["back_button"],
                    callback_data="back_to_products")]])

        context.user_data["product"].send_short_template(
            update, context, text=text, reply_markup=reply_markup)
        return CONFIRM_TO_TRASH

    def finish_to_trash(self, update: Update, context: CallbackContext):
        context.bot.send_chat_action(update.effective_chat.id, "typing")
        delete_messages(update, context, True)
        context.user_data["product"].update({"in_trash": True})
        update.callback_query.answer(context.bot.lang_dict["shop_admin_moved_to_trash_blink"])
        return self.back_to_products(update, context)

    def quantity(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        text = (self.admin_short_template(context, context.user_data["product"])
                + "\n\n"
                + context.bot.lang_dict["shop_admin_set_quantity"])

        context.user_data["product"].send_short_template(
            update, context,
            text=text, reply_markup=self.edit_quantity_markup(context))
        return SET_QUANTITY

    def finish_quantity(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        if update.message:
            quantity_request = context.user_data["product"].create_quantity(
                update, context)
            if quantity_request["ok"]:
                context.user_data["product"].update(
                    {"quantity": quantity_request["quantity"],
                     "unlimited": False})
            else:
                text = (self.admin_short_template(context, context.user_data["product"])
                        + "\n\n"
                        + quantity_request["error_message"]
                        + "\n\n"
                        + context.bot.lang_dict["shop_admin_set_quantity"])
                context.user_data["product"].send_short_template(
                    update, context,
                    text=text, reply_markup=self.edit_quantity_markup(context))
                return SET_QUANTITY
        elif update.callback_query.data == "quantity_unlimited":
            context.user_data["product"].update(
                {"quantity": 0, "unlimited": True})

        return self.edit(update, context)


    @staticmethod
    def edit_quantity_markup(context):
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                text=context.bot.lang_dict["shop_admin_set_unlimited"],
                callback_data='quantity_unlimited')],
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_edit")]])
        return reply_markup

    def back_to_products(self, update: Update, context: CallbackContext):
        page = context.user_data.get("page", 1)
        delete_messages(update, context)
        clear_user_data(context)
        context.user_data["page"] = page
        return self.products(update, context)


(PRODUCTS, EDIT, DESCRIPTION, NAME, PRICE,
 DISCOUNT_PRICE, IMAGES, CATEGORY, PAYMENT, CONFIRM_TO_TRASH, SIZES_MENU,
 SIZE_QUANTITY, SET_SIZE, SET_QUANTITY,
 CONFIRM_ADD_SIZES, CONTENT_MENU, ADDING_CONTENT) = range(17)

PRODUCTS_HANDLER = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(ProductsHandler().products,
                                       pattern=r"products")],
    states={
        PRODUCTS: [CallbackQueryHandler(ProductsHandler().products,
                                        pattern=r"item_list_pagination"),
                   CallbackQueryHandler(ProductsHandler().edit,
                                        pattern=r"edit_product"),
                   CallbackQueryHandler(ProductsHandler().confirm_to_trash,
                                        pattern=r"to_trash")],

        EDIT: [CallbackQueryHandler(ProductsHandler().discount_price,
                                    pattern="change_discount"),
               CallbackQueryHandler(ProductsHandler().price,
                                    pattern="change_price"),
               CallbackQueryHandler(ProductsHandler().quantity,
                                    pattern="change_quantity"),
               CallbackQueryHandler(ProductsHandler().description,
                                    pattern="change_description"),
               CallbackQueryHandler(ProductsHandler().name,
                                    pattern="change_name"),
               CallbackQueryHandler(ProductsHandler().category,
                                    pattern="change_category"),
               CallbackQueryHandler(ProductsHandler().content_menu,
                                    pattern="content_menu")],

        CONFIRM_TO_TRASH: [
            CallbackQueryHandler(ProductsHandler().finish_to_trash,
                                 pattern=r"finish_to_trash")],

        CATEGORY: [
            MessageHandler(
                Filters.text,
                ProductsHandler().finish_category),
            CallbackQueryHandler(
                ProductsHandler().finish_category,
                pattern=r"category_")],

        CONTENT_MENU: [
            CallbackQueryHandler(
                pattern="add_new_content",
                callback=ProductsHandler().start_adding_content),
            CallbackQueryHandler(
                pattern=r"remove_from_content",
                callback=ProductsHandler().finish_remove_from_content)],

        ADDING_CONTENT: [
            MessageHandler(Filters.all,
                           ProductsHandler().open_content_handler),
            MessageHandler(Filters.regex(r"^((?!@).)*$"),
                           ProductsHandler().open_content_handler),
        ],

        DESCRIPTION: [MessageHandler(Filters.text,
                                     ProductsHandler().finish_description)],

        NAME: [MessageHandler(Filters.text,
                              ProductsHandler().finish_name)],

        # todo 3 regexes vs just Filters.text (it looks like everything works anyway)
        PRICE: [MessageHandler(Filters.regex(r'(\d+\.\d{1,2})|(\d+\,\d{1,2})'),
                               ProductsHandler().finish_price),
                MessageHandler(Filters.regex(r'^[-+]?([1-9]\d*|0)$'),
                               ProductsHandler().finish_price),
                MessageHandler(Filters.regex(r"^((?!@).)*$"),
                               ProductsHandler().finish_price)],

        # todo 3 regexes vs just Filters.text (it looks like everything works anyway)
        DISCOUNT_PRICE: [
            MessageHandler(Filters.regex(r'(\d+\.\d{1,2})|(\d+\,\d{1,2})'),
                           ProductsHandler().finish_discount_price),
            MessageHandler(Filters.regex(r'^[-+]?([1-9]\d*|0)$'),
                           ProductsHandler().finish_discount_price),
            MessageHandler(Filters.regex(r"^((?!@).)*$"),
                           ProductsHandler().finish_discount_price),
            CallbackQueryHandler(ProductsHandler().remove_discount,
                                 pattern="remove_discount")
        ],

        # todo 3 regexes vs just Filters.text (it looks like everything works anyway)
        SET_QUANTITY: [
                       CallbackQueryHandler(ProductsHandler().finish_quantity,
                                            pattern=r"quantity_unlimited"),
                       MessageHandler(Filters.regex(r'(\d+\.\d{1,2})|(\d+\,\d{1,2})'),
                                      ProductsHandler().finish_quantity),
                       MessageHandler(Filters.regex(r'^[-+]?([1-9]\d*|0)$'),
                                      ProductsHandler().finish_quantity),
                       MessageHandler(Filters.regex(r"^((?!@).)*$"),
                                      ProductsHandler().finish_quantity),
        ],
    },
    fallbacks=[CallbackQueryHandler(Welcome.back_to_main_menu,
                                    pattern=r"back_to_main_menu"),
               CallbackQueryHandler(Welcome.back_to_main_menu,
                                    pattern=r"help_back"),
               CallbackQueryHandler(ProductsHandler().back_to_products,
                                    pattern=r"back_to_products"),
               CallbackQueryHandler(ProductsHandler().edit,
                                    pattern=r"back_to_edit"),
               CallbackQueryHandler(ProductsHandler().content_menu,
                                    pattern=r"back_to_content_menu")]
)
