from pprint import pprint
import html

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CallbackQueryHandler
from bson.objectid import ObjectId

from helper_funcs.helper import get_help, back_to_modules
from helper_funcs.misc import delete_messages, get_obj
from helper_funcs.pagination import Pagination
from modules.shop.components.product import Product, MAX_TEMP_DESCRIPTION_LENGTH
from database import products_table, carts_table, chatbots_table, categories_table


class CartHelper(object):
    """All "short" templates must be passed to send_short_template() method.
    And all "full" templates must be passed to send_full_template() method.
    """
    @classmethod
    def order_data(cls, update, context):
        """Make order from current cart products"""
        cart = carts_table.find_one({"bot_id": context.bot.id,
                                     "user_id": update.effective_user.id})
        cart_items = list()
        for cart_item in cart["products"]:
            cart_item = cls.validate_cart_item(cart, cart_item["product_id"])
            if cart_item:
                cart_items.append(cart_item)
        # print(cart_items)
        shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]
        template = context.bot.lang_dict["order_create_title"]
        order_price = 0
        for cart_item in cart_items:
            pprint(cart_item)
            if cart_item["product"].get("discount_price"):
                item_price = (round(float(cart_item["product"]["discount_price"])
                              * cart_item["quantity"], 2))
            else:
                item_price = (round(float(cart_item["product"]["price"])
                              * cart_item["quantity"], 2))
            # print(item_price)
            order_price += item_price
            if len(template) < 3800:
                template += (
                    "<b>{}</b>\n<i>x{}</i> - <b>{} {}</b>\n\n").format(
                    html.escape(cart_item["product"]["name"], quote=False),
                    cart_item["quantity"],
                    item_price,
                    shop["currency"])
            elif not template.endswith("..."):
                template += "..."
        template += context.bot.lang_dict["order_create_end"].format(order_price, shop['currency'])
        # Save order data. Need to check order data on each step??
        order = dict()
        order["items"] = cart_items
        order["total_price"] = order_price
        order["currency"] = shop['currency']
        return {"order": order, "template": template, "shop": shop}

    @staticmethod
    def validate_cart_item(cart, product: (ObjectId, str)) -> dict:
        """Check if the product exist and check product quantity

        * when cart opened from main menu button("Cart")
        * when change quantity

        :param cart: ObjectId or string _id of the cart or cart dict
        :param product: ObjectId or string _id of the product or product dict
        :return: empty dict if product doesn't exist, sold of deleted
            or dict with data if item exist and correct
        """

        if type(product) is ObjectId:
            product_id = product
            product = products_table.find_one({"_id": product_id})
        elif type(product) is str:
            product_id = ObjectId(product)
            product = products_table.find_one({"_id": product_id})
        else:
            product_id = product["_id"]

        cart = get_obj(carts_table, cart)

        if not product or product["in_trash"] or (
                not product["unlimited"] and not product["quantity"]):
            carts_table.update_one(
                {"_id": cart["_id"]},
                {"$pull": {"products": {"product_id": product_id}}})
            return dict()

        cart_item = next((i for i in cart["products"]
                          if i["product_id"] == product_id), None)
        if not cart_item:
            return dict()

        # If cart item quantity bigger than product
        # set cart item quantity to maximum count
        if (not product.get("unlimited")
                and cart_item["quantity"] > int(product["quantity"])):
            cart_item["quantity"] = int(product["quantity"])
            carts_table.find_and_modify(
                {"_id": cart["_id"], "products.product_id": product["_id"]},
                {"$set": {"products.$.quantity": int(product["quantity"])}})
        cart_item["product"] = product
        return cart_item

    @classmethod
    def short_cart_item_template(cls, cart_item, currency, context) -> str:
        """Short text representation of the cart item.

        :param cart_item: {
            "product_id": ObjectId,  # Object id of the product
            "quantity": int,  # Cart product quantity
            "product": dict  # Product document
        }
        :param currency: shop currency
        :param context: CallbackContext

        :return str
        """
        # Create product template
        if len(cart_item["product"]["description"]) > MAX_TEMP_DESCRIPTION_LENGTH:
            description = (cart_item["product"]["description"]
                           [:MAX_TEMP_DESCRIPTION_LENGTH] + "...")
        else:
            description = cart_item["product"]["description"]
        category_name = categories_table.find_one(
            {"_id": cart_item["product"]["category_id"]})["name"]

        template = context.bot.lang_dict["cart_item_template"].format(
                cart_item["product"].get("article"),
                html.escape(cart_item["product"]["name"], quote=False),
                html.escape(category_name, quote=False),
                cls.price_as_str(cart_item, context, currency))
        if not cart_item["product"].get("unlimited"):
            template += context.bot.lang_dict["in_stock_field"].format(
                cart_item['product']['quantity'])
        template += context.bot.lang_dict["cart_quantity_field"].format(
            cart_item['quantity'])
        return template

    @classmethod
    def full_cart_item_template(cls, cart_item, currency, context) -> str:
        """Full text representation of the cart item.

        :param cart_item: {
            "product_id": ObjectId,  # Object id of the product
            "quantity": int,  # Cart product quantity
            "product": dict  # Product document
        }
        :param currency: shop currency
        :param context: CallbackContext

        :return: str
        """
        category_name = categories_table.find_one(
            {"_id": cart_item["product"]["category_id"]})["name"]

        template = context.bot.lang_dict["full_cart_item_template"].format(
                cart_item["product"].get("article"),
                html.escape(cart_item["product"]["name"], quote=False),
                html.escape(category_name, quote=False),
                cls.price_as_str(cart_item, context, currency))
        if (len(cart_item["product"]["description"])
                < MAX_TEMP_DESCRIPTION_LENGTH):
            template += context.bot.lang_dict["description_field"].format(
                html.escape(cart_item["product"]["description"], quote=False))

        if not cart_item["product"].get("unlimited"):
            template += context.bot.lang_dict["in_stock_field"].format(
                cart_item['product']['quantity'])
        template += context.bot.lang_dict["cart_quantity_field"].format(cart_item['quantity'])
        return template

    @staticmethod
    def cart_item_markup(cart_item, context):
        """Keyboard for the cart item.
        Product must exist in the cart and quantity must be correct

        :param cart_item: {
            "product_id": ObjectId,  # Object id of the product
            "quantity": int,  # Cart quantity
            "product": dict  # product document
        }
        :param context: CallbackContext

        :return: InlineKeyboardMarkup
        """
        product_buttons = [[]]
        product_buttons[0].append(
            InlineKeyboardButton(
                text=context.bot.lang_dict["minus"],
                callback_data=f"reduce_quantity/{cart_item['product_id']}"))
        product_buttons[0].append(
            InlineKeyboardButton(
                text=context.bot.lang_dict["plus"],
                callback_data=f"increase_quantity/{cart_item['product_id']}"))
        product_buttons[0].append(
            InlineKeyboardButton(
                text=context.bot.lang_dict["remove_button_str"],
                callback_data=f"list_cart_remove/{cart_item['product_id']}"))
        content_len = len(cart_item["product"]["content"])
        if len(cart_item["product"]["description"]) > 150 or content_len > 1:
            product_buttons.append(
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["view_button_str"]
                    + (context.bot.lang_dict["cart_view_help"].format(content_len)
                       if content_len else ""),
                    callback_data=f"view_cart_product/{cart_item['product_id']}")])
        return InlineKeyboardMarkup(product_buttons)

    @classmethod
    def price_as_str(cls, cart_item, context, currency=None):
        # todo repeating - quick solution, create "components" logic for bots side
        if not currency:
            currency = chatbots_table.find_one(
                {"bot_id": context.bot.id})["shop"]["currency"]
        price = float(format((cart_item["product"]["price"]) * cart_item["quantity"], '.2f'))

        if cart_item["product"]['discount_price']:
            discount_price = float(
                format((cart_item["product"]["discount_price"]) * cart_item["quantity"], '.2f'))
            return (f"💥 <s>{price}</s> "
                    f"<b><u>{discount_price} {currency}</u></b>")
        else:
            return f"<b><u>{price} {currency}</u></b>"


class Cart(CartHelper):
    def cart(self, update, context):
        delete_messages(update, context, True)
        context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                     action="typing")
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith("user_cart_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("user_cart_pagination_", ""))
        if (not context.user_data.get("page")
                or update.callback_query.data == "cart"):
            context.user_data["page"] = 1
        # Get cart products
        cart = carts_table.find_one({"user_id": update.effective_user.id,
                                     "bot_id": context.bot.id})
        if not cart:
            inserted_id = carts_table.insert_one(
                {"user_id": update.effective_user.id,
                 "bot_id": context.bot.id,
                 "products": list()}).inserted_id
            cart = carts_table.find_one({"_id": inserted_id})
        # when cart opened from main menu button check all cart products
        elif update.callback_query.data == "cart":
            for cart_item in cart["products"]:
                self.validate_cart_item(cart, cart_item["product_id"])
            cart = carts_table.find_one({"user_id": update.effective_user.id,
                                         "bot_id": context.bot.id})

        # Show blink if cart is empty
        if not len(cart["products"]):
            update.callback_query.answer(context.bot.lang_dict["cart_empty_blink"])
            # return ConversationHandler.END
            update.callback_query.data = "back_to_module_shop"
            return back_to_modules(update, context)

        # Send page content
        self.send_cart_products_layout(update, context, cart["products"])
        return ConversationHandler.END

    def send_cart_products_layout(self, update, context, cart_products):
        # Title
        # context.user_data['to_delete'].append(
        #     context.bot.send_message(
        #         chat_id=update.callback_query.message.chat_id,
        #         text=context.bot.lang_dict["shop_admin_products_title"].format(len(cart_products)),
        #         parse_mode=ParseMode.HTML))
        # Products list buttons
        buttons = [[InlineKeyboardButton(
                        text=context.bot.lang_dict["back_button"],
                        callback_data="back_to_module_shop")]]

        if len(cart_products):
            buttons.insert(0, [InlineKeyboardButton(
                                   text=context.bot.lang_dict["make_order_btn"],
                                   callback_data="make_order")])
            # Create page content and send it
            pagination = Pagination(cart_products,
                                    page=context.user_data["page"])
            currency = chatbots_table.find_one(
                {"bot_id": context.bot.id})["shop"]["currency"]

            for cart_item in pagination.content:
                product = products_table.find_one(
                    {"_id": cart_item["product_id"]})
                if not product:
                    continue

                # Create product reply markup and send short product template
                cart_item["product"] = product
                reply_markup = self.cart_item_markup(cart_item, context)
                template = self.short_cart_item_template(cart_item, currency, context)
                product_obj = Product(context, product)
                product_obj.send_short_template(
                    update, context, text=template, reply_markup=reply_markup)
            # Send main buttons
            pagination.send_keyboard(
                update, context,
                buttons=buttons,
                page_prefix="user_cart_pagination",
                text=context.bot.lang_dict["shop_admin_products_title"].format(
                    len(cart_products)))
        else:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["shop_admin_no_products"],
                    reply_markup=InlineKeyboardMarkup(buttons)))

    def change_quantity(self, update, context):
        operation, product_id = update.callback_query.data.split("/")
        cart = carts_table.find_one({"bot_id": context.bot.id,
                                     "user_id": update.effective_user.id})
        cart_item = self.validate_cart_item(cart, product_id)

        if cart_item:
            if operation == "increase_quantity":
                if cart_item["product"]["unlimited"]:
                    cart_item["quantity"] += 1
                elif (cart_item["quantity"]
                      < cart_item["product"]["quantity"]):
                    cart_item["quantity"] += 1
                else:
                    update.callback_query.answer(context.bot.lang_dict["max_quantity_blink"])

            elif operation == "reduce_quantity":
                if cart_item["quantity"] > 1:
                    cart_item["quantity"] -= 1
                else:
                    update.callback_query.answer(context.bot.lang_dict["min_quantity_blink"])
            else:
                return self.back_to_cart(update, context)

            carts_table.find_and_modify(
                {"_id": cart["_id"],
                 "products.product_id": cart_item["product_id"]},
                {"$set": {"products.$.quantity": cart_item["quantity"]}})

            currency = chatbots_table.find_one(
                {"bot_id": context.bot.id})["shop"]["currency"]
            template = self.short_cart_item_template(cart_item, currency, context)

            if update.effective_message.caption_html:
                update.effective_message.edit_caption(
                    caption=template, parse_mode=ParseMode.HTML)
            else:
                update.effective_message.edit_text(
                    text=template, parse_mode=ParseMode.HTML)

            update.effective_message.edit_reply_markup(
                reply_markup=self.cart_item_markup(cart_item, context))
        else:
            return self.back_to_cart(update, context)

    def remove_from_cart(self, update, context):
        product_id = ObjectId(update.callback_query.data.split("/")[1])
        product = products_table.find_one({"_id": product_id}) or {}
        carts_table.update_one(
            {"bot_id": context.bot.id, "user_id": update.effective_user.id},
            {"$pull": {"products": {"product_id": product_id}}})
        update.callback_query.answer(
            context.bot.lang_dict["removed_from_cart_blink"].format(product.get("name") or ""))
        return self.back_to_cart(update, context)

    def view_product(self, update, context):
        """When product description is too long
        or there a few files in the product - "View" button
        """
        delete_messages(update, context, True)
        cart = carts_table.find_one({"user_id": update.effective_user.id,
                                     "bot_id": context.bot.id})
        product_id = update.callback_query.data.split("/")[1]
        cart_item = self.validate_cart_item(cart, product_id)
        if not cart_item:
            return self.back_to_cart(update, context)

        prod_obj = Product(context, cart_item["product"])
        currency = chatbots_table.find_one(
            {"bot_id": context.bot.id})["shop"]["currency"]
        template = self.full_cart_item_template(cart_item, currency, context)
        back_button = InlineKeyboardMarkup([
            [InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                  callback_data="back_to_cart")]])
        prod_obj.send_full_template(
            update, context, text=template, reply_markup=back_button)

        return ConversationHandler.END

    def make_order(self, update, context):
        delete_messages(update, context, True)
        # Prepare cart items for order
        order_data = self.order_data(update, context)
        if not order_data["order"]["items"]:
            return self.back_to_cart(update, context)
        context.user_data["order"] = order_data["order"]
        # Create reply markup
        buttons = list()
        # if order_data["shop"]["shop_type"] == "offline":
        #     buttons.append(
        #         [InlineKeyboardButton(
        #             text=context.bot.lang_dict["offline_buy"],
        #             callback_data=f"offline_buy")])
        # elif order_data["shop"]["shop_type"] == "online":
        #     buttons.append(
        #         [InlineKeyboardButton(
        #             text=context.bot.lang_dict["online_buy"],
        #             callback_data=f"online_buy")])
        buttons.append(
            [InlineKeyboardButton(
                text=context.bot.lang_dict["buy_btn"],
                callback_data="create_order")])
        buttons.append(
            [InlineKeyboardButton(
                text=context.bot.lang_dict["back_button"],
                callback_data="back_to_cart")])
        # Send order template
        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=order_data["template"],
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(buttons)))
        return ConversationHandler.END

    def back_to_cart(self, update, context):
        delete_messages(update, context, True)
        page = context.user_data.get("page", 1)
        context.user_data.clear()
        context.user_data["page"] = page
        return self.cart(update, context)


"""CART"""
CART = CallbackQueryHandler(
    pattern="^(cart|user_cart_pagination)",
    callback=Cart().cart)

REMOVE_FROM_CART_LIST = CallbackQueryHandler(
    pattern=r"list_cart_remove",
    callback=Cart().remove_from_cart)

CHANGE_QUANTITY = CallbackQueryHandler(
    pattern=r"^(increase_quantity|reduce_quantity)",
    callback=Cart().change_quantity)

VIEW_CART_PRODUCT = CallbackQueryHandler(
    pattern=r"view_cart_product",
    callback=Cart().view_product)

MAKE_ORDER = CallbackQueryHandler(
    pattern="make_order",
    callback=Cart().make_order)

"""BACKS"""
BACK_TO_CART = CallbackQueryHandler(
    pattern="back_to_cart",
    callback=Cart().back_to_cart)
