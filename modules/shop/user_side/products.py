from pprint import pprint
import html

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CallbackQueryHandler
from bson.objectid import ObjectId

from helper_funcs.misc import delete_messages
from helper_funcs.pagination import Pagination
from modules.shop.components.product import Product, MAX_TEMP_DESCRIPTION_LENGTH
from modules.shop.user_side.cart import Cart
from database import products_table, carts_table, chatbots_table, categories_table


class UserProductsHelper(object):
    # TODO put this logic to the components/product -> class AdminProduct

    """All "short" templates must be passed to send_short_template() method.
    And all "full" templates must be passed to send_full_template() method.
    """

    @staticmethod
    def product_markup(cart, product, context):
        """Keyboard for the product in product list.

        :param cart: mongo document of the cart
        :param product: mongo document of the product
        :param context: CallbackContext
        :return: InlineKeyboardMarkup
        """
        buttons = []
        content_len = len(product["content"])

        if any(cart_product["product_id"] == product["_id"]
               for cart_product in cart.get("products", list())):
            buttons.append(
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["remove_button_str"],
                    callback_data=f"remove_from_cart/{product['_id']}")])
        else:
            buttons.append(
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["add_to_cart_btn"],
                    callback_data=f"add_to_cart/{product['_id']}")])

        if (len(product["description"]) > MAX_TEMP_DESCRIPTION_LENGTH
                or content_len > 1):
            buttons.append(
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["view_button_str"]
                    + (context.bot.lang_dict["cart_view_help"].format(content_len)
                       if content_len else ""),
                    callback_data=f"view_product_from_catalog/{product['_id']}")])
        return InlineKeyboardMarkup(buttons)

    @classmethod
    def short_product_template(cls, cart, product, currency, context):
        """Short customer text representation of the product.

        :param product: mongo document of the product
        :param cart: mongo document of the cart
        :param currency: currency of the shop
        :param context: CallbackContext

        :return: str
        """
        if len(product["description"]) > MAX_TEMP_DESCRIPTION_LENGTH:
            description = product["description"][:MAX_TEMP_DESCRIPTION_LENGTH] + "..."
        else:
            description = product["description"]

        category = categories_table.find_one(
            {"_id": product["category_id"]})["name"]
        # if product.get("discount_price") > 0:
        template = context.bot.lang_dict["short_user_product_temp"].format(
            product.get("article"),
            html.escape(product["name"], quote=False),
            html.escape(category, quote=False),
            cls.price_as_str(product, context, currency),
            html.escape(description, quote=False))
        # else:
        #     template = context.bot.lang_dict["short_user_product_temp_2"].format(
        #         str(product.get("_id")),
        #         html.escape(product["name"], quote=False),
        #         html.escape(category, quote=False),
        #         product["price"], currency,
        #         html.escape(description, quote=False))

        if not product["unlimited"]:
            template += context.bot.lang_dict["quantity_field"].format(product['quantity'])

        # Check if the product exist in the cart
        if any(cart_product["product_id"] == product["_id"]
               for cart_product in cart.get("products", list())):
            template += context.bot.lang_dict["product_already_in_cart"]
        # Check if the product exist in the not done order
        # product_in_order = orders_table.find_one(
        #     {""})

        return template

    @classmethod
    def full_product_template(cls, cart, product, currency, context):
        """Full customer text representation of the product.

        :param product: mongo document of the product
        :param cart: mongo document of the cart
        :param currency: currency of the shop
        :param context: CallbackContext

        :return: str
        """
        category = categories_table.find_one(
            {"_id": product["category_id"]})["name"]

        template = context.bot.lang_dict["full_user_product_temp"].format(
            product.get("article"),
            html.escape(product["name"], quote=False),
            html.escape(category, quote=False),
            cls.price_as_str(product, context, currency))

        if len(product["description"]) < MAX_TEMP_DESCRIPTION_LENGTH:
            template += context.bot.lang_dict["description_field"].format(
                html.escape(product["description"], quote=False))

        if not product["unlimited"]:
            template += context.bot.lang_dict["quantity_field"].format(product['quantity'])

        if any(cart_product["product_id"] == product["_id"]
               for cart_product in cart.get("products", list())):
            template += context.bot.lang_dict["product_already_in_cart"]
        return template

    @classmethod
    def price_as_str(cls, product, context, currency=None):
        # todo repeating - create "components" logic for bots side
        if not currency:
            currency = chatbots_table.find_one(
                {"bot_id": context.bot.id})["shop"]["currency"]
        if product['discount_price']:
            return (f"💥 <s>{product['price']}</s> "
                    f"<u>{product['discount_price']} {currency}</u>")
        else:
            return f"<u>{product['price']} {currency}</u>"


class UserProductsHandler(UserProductsHelper):
    def categories_menu(self, update, context):
        delete_messages(update, context, True)
        filters = {"$or": [
            {"in_trash": False,
             "bot_id": context.bot.id,
             'unlimited': True},
            {"in_trash": False,
             "bot_id": context.bot.id,
             "quantity": {"$gt": 0}}
        ]}
        categories_list_ids = [x["category_id"] for x in products_table.find(filters)]
        categories_list = [categories_table.find_one({"_id": x})
                           for x in set(categories_list_ids)]

        if categories_list:
            categories_buttons = [
                [InlineKeyboardButton(text=x["name"],
                                      callback_data=f"catalog/{x['_id']}")]
                for x in categories_list]

            categories_reply_markup = InlineKeyboardMarkup(
                categories_buttons
                + [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                         callback_data="back_to_module_shop")]])

            context.user_data["to_delete"].append(
                context.bot.send_message(chat_id=update.effective_chat.id,
                                         text=context.bot.lang_dict["shop_user_choose_category"],
                                         reply_markup=categories_reply_markup))
        else:
            return self.products(update, context)
        return ConversationHandler.END

    def products(self, update, context):
        delete_messages(update, context, True)
        context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                     action="typing")
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith("user_products_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("user_products_pagination_", ""))
        if not context.user_data.get("page"):
            context.user_data["page"] = 1

        if update.callback_query.data.startswith("catalog"):
            context.user_data["category_id"] = ObjectId(
                update.callback_query.data.split("/")[1])

        filters = {"$or": [
            {"in_trash": False,
             "bot_id": context.bot.id,
             'unlimited': True},
            {"in_trash": False,
             "bot_id": context.bot.id,
             "quantity": {"$gt": 0}}
        ]}

        if context.user_data.get("category_id"):
            filters["$or"][0]["category_id"] = context.user_data["category_id"]
            filters["$or"][1]["category_id"] = context.user_data["category_id"]
        all_products = products_table.find(filters).sort([["last_modify_timestamp", -1]])
        self.send_products_layout(update, context, all_products)
        return ConversationHandler.END

    def send_products_layout(self, update, context, all_products):
        # Title
        # context.user_data['to_delete'].append(
        #     context.bot.send_message(
        #         chat_id=update.callback_query.message.chat_id,
        #         text=context.bot.lang_dict[
        #             "shop_admin_products_title"].format(all_products.count()),
        #         parse_mode=ParseMode.HTML))
        # Products list buttons
        buttons = [[InlineKeyboardButton(
            text=context.bot.lang_dict["shop_cart"],
            callback_data="move_to_cart")],
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_categories")]]

        if all_products.count():
            # Create page content and send it
            pagination = Pagination(all_products,
                                    page=context.user_data["page"])
            shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]
            cart = carts_table.find_one(
                {"bot_id": context.bot.id,
                 "user_id": update.effective_user.id}) or {}

            for product in pagination.content:
                # Send short product template
                reply_markup = self.product_markup(cart, product, context)
                template = self.short_product_template(cart, product,
                                                       shop["currency"], context)
                product_obj = Product(context, product)
                product_obj.send_short_template(
                    update, context, text=template, reply_markup=reply_markup)

            # Send main buttons
            pagination.send_keyboard(
                update, context,
                page_prefix="user_products_pagination",
                text=context.bot.lang_dict["shop_admin_products_title"].format(
                    all_products.count()),
                buttons=buttons)
        else:
            buttons = [[
                InlineKeyboardButton(
                    text=context.bot.lang_dict["shop_cart"],
                    callback_data="move_to_cart")],
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["back_button"],
                    callback_data="back_to_module_shop")]]
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["shop_admin_no_products"],
                    reply_markup=InlineKeyboardMarkup(buttons)))

    def add_to_cart(self, update, context):
        product_id = ObjectId(update.callback_query.data.split("/")[1])
        product = products_table.find_one({"_id": product_id})
        if product:
            cart = carts_table.find_and_modify(
                {"bot_id": context.bot.id,
                 "user_id": update.effective_user.id},
                {"$push": {"products": {"product_id": product_id,
                                        "quantity": 1}}},
                upsert=True, new=True)
            update.callback_query.answer(
                context.bot.lang_dict["added_to_cart_blink"].format(product['name']))

            shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]
            template = self.short_product_template(cart, product,
                                                   shop["currency"], context)
            if len(product["content"]) > 0:
                update.effective_message.edit_caption(
                    caption=template, parse_mode=ParseMode.HTML)
            else:
                update.effective_message.edit_text(
                    text=template, parse_mode=ParseMode.HTML)

            update.effective_message.edit_reply_markup(
                reply_markup=self.product_markup(cart, product, context))
        else:
            update.callback_query.answer(context.bot.lang_dict["no_product_blink"])
            return self.back_to_products(update, context)
        return ConversationHandler.END

    def remove_from_cart(self, update, context):
        product_id = ObjectId(update.callback_query.data.split("/")[1])
        product = products_table.find_one({"_id": product_id}) or {}
        cart = carts_table.find_and_modify(
            {"bot_id": context.bot.id, "user_id": update.effective_user.id},
            {"$pull": {"products": {"product_id": product_id}}}, new=True)
        update.callback_query.answer(
            context.bot.lang_dict["removed_from_cart_blink"].format(product.get("name") or ""))

        shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]
        template = self.short_product_template(cart, product,
                                               shop["currency"], context)
        if len(product["content"]) > 0:
            update.effective_message.edit_caption(
                caption=template, parse_mode=ParseMode.HTML)
        else:
            update.effective_message.edit_text(
                text=template, parse_mode=ParseMode.HTML)

        update.effective_message.edit_reply_markup(
            reply_markup=self.product_markup(cart, product, context))
        return ConversationHandler.END

    def view_product(self, update, context):
        """When product description is too long
        or there a few files in the product - "View" button
        """
        delete_messages(update, context, True)
        cart = carts_table.find_one({"user_id": update.effective_user.id,
                                     "bot_id": context.bot.id}) or {}
        product_id = ObjectId(update.callback_query.data.split("/")[1])
        product = products_table.find_one({"_id": product_id})
        if not product:
            return self.back_to_products(update, context)
        prod_obj = Product(context, product)
        currency = chatbots_table.find_one(
            {"bot_id": context.bot.id})["shop"]["currency"]
        template = self.full_product_template(cart, product, currency, context)
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_customer_shop")]])
        prod_obj.send_full_template(
            update, context, text=template, reply_markup=back_button)

        return ConversationHandler.END

    def shop_contacts(self, update, context):
        delete_messages(update, context, True)
        address = chatbots_table.find_one({"bot_id": context.bot.id})["shop"].get("address")
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_module_shop")]])
        update.effective_message.reply_text(text="{}".format(address),
                                            reply_markup=back_button)
        return ConversationHandler.END

    def back_to_products(self, update, context):
        delete_messages(update, context, True)
        page = context.user_data.get("page", 1)
        try:
            category_id = context.user_data["category_id"]
        except KeyError:
            return self.back_to_categories(update, context)
        context.user_data.clear()
        context.user_data["page"] = page
        context.user_data["category_id"] = category_id
        return self.products(update, context)

    def move_to_cart(self, update, context):
        cart = carts_table.find_one({"user_id": update.effective_user.id,
                                     "bot_id": context.bot.id}) or {}
        if len(cart.get("products", list())):
            delete_messages(update, context, True)
            context.user_data.clear()
            return Cart().cart(update, context)
        else:
            update.callback_query.answer(context.bot.lang_dict["cart_empty_blink"])
            return ConversationHandler.END

    def back_to_categories(self, update, context):
        delete_messages(update, context, True)
        context.user_data.clear()
        return self.categories_menu(update, context)


"""SHOP"""
PRODUCTS_CATEGORIES = CallbackQueryHandler(
    pattern="open_shop",
    callback=UserProductsHandler().categories_menu)

USERS_PRODUCTS_LIST_HANDLER = CallbackQueryHandler(
    pattern="^(catalog|user_products_pagination)",
    callback=UserProductsHandler().products)

ADD_TO_CART = CallbackQueryHandler(
    pattern=r"add_to_cart",
    callback=UserProductsHandler().add_to_cart)

REMOVE_FROM_CART = CallbackQueryHandler(
    pattern=r"remove_from_cart",
    callback=UserProductsHandler().remove_from_cart)

VIEW_PRODUCT = CallbackQueryHandler(
    pattern=r"view_product_from_catalog",
    callback=UserProductsHandler().view_product)

MOVE_TO_CART = CallbackQueryHandler(
    pattern="move_to_cart",
    callback=UserProductsHandler().move_to_cart)

"""BACKS"""
BACK_TO_CATEGORIES = CallbackQueryHandler(
    pattern=r"back_to_categories",
    callback=UserProductsHandler().back_to_categories)

BACK_TO_CUSTOMER_SHOP = CallbackQueryHandler(
    pattern=r"back_to_customer_shop",
    callback=UserProductsHandler().back_to_products)

SHOP_CONTACTS = CallbackQueryHandler(pattern="contacts_shop",
                                     callback=UserProductsHandler().shop_contacts)
