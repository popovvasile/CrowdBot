import html

from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from bson.objectid import ObjectId

from .product import Product
from database import orders_table, chatbots_table
from helper_funcs.misc import get_obj
from helper_funcs.pagination import Pagination
from helper_funcs.misc import user_mention


class Order(object):
    def __init__(self, context,  obj: (ObjectId, dict, str) = None):
        order = get_obj(orders_table, obj)
        self.context = context
        self._id = order.get("_id")
        self.article = order.get("article")
        self.status = order.get("status")  # True or False
        self.bot_id = order.get("bot_id") or context.bot.id
        self.user_id = order.get("user_id")
        self.creation_timestamp = str(
            order.get("creation_timestamp", ".")).split(".")[0]
        self.in_trash = order.get("in_trash")
        self.total_price = order.get("total_price")
        self.items_json = order.get("items", list())
        self.currency = order.get("currency")
        self.shipping = order.get("shipping")
        self.user_comment = order.get("user_comment")
        self.phone_number = order.get("phone_number")
        self.address = order.get("address")
        self.paid = order.get("paid")
        # self.name = order.get("name")
        # self.is_canceled = order.get("is_canceled")

    def create_fields(self, context=None, obj=None):
        """Same as __init__ method"""
        if obj:
            order = get_obj(orders_table, obj)
        else:
            order = get_obj(orders_table, self._id)
        self.context = context or self.context
        self._id = order.get("_id")
        self.article = order.get("article")
        self.status = order.get("status")  # True or False
        self.bot_id = order.get("bot_id") or context.bot.id
        self.user_id = order.get("user_id")
        self.creation_timestamp = str(
            order.get("creation_timestamp", ".")).split(".")[0]
        self.in_trash = order.get("in_trash")
        self.total_price = order.get("total_price")
        self.items_json = order.get("items", list())
        self.currency = order.get("currency")
        self.shipping = order.get("shipping")
        self.user_comment = order.get("user_comment")
        self.phone_number = order.get("phone_number")
        self.address = order.get("address")
        # self.name = order.get("name")
        # self.is_canceled = order.get("is_canceled")

    @property
    def items(self):
        return [OrderItem(self.context, order_item, self.currency)
                for order_item in self.items_json]

    @property
    def all_items_exists(self):
        return not any(item.item_exist is False
                       for item in self.items)

    @property
    def id_(self):
        return self._id

    # todo refactor for long order items texts
    def str_order_items(self, currency=None):
        # if not currency:
        #     currency = chatbots_table.find_one(
        #         {"bot_id": self.context.bot.id})["shop"]["currency"]
        text = "\n".join(
            ["{}\nx{} - <u>{} {}</u>".format(
                html.escape(item.name, quote=False),
                item.order_quantity,
                item.item_price,
                self.currency)
             # + (item.item_emoji if not self.status else "")
             for item in self.items[:3]])
        if len(self.items) > 3:
            text += "\n..."
        return text

    def update(self, json):
        orders_table.update_one({"_id": self._id}, {"$set": json})
        self.create_fields(self.context, self._id)


class AdminOrder(Order):
    def __init__(self, context, obj: (ObjectId, dict, str) = None):
        super(AdminOrder, self).__init__(context, obj)

    @property
    def user_mention(self):
        mention = ""
        if self.user_id:
            user = self.context.bot.get_chat_member(self.user_id,
                                                    self.user_id).user
            # Create bots html mention
            # if bots.username:
            #     mention = user_mention(bots.username, bots.full_name)
            # else:
            mention = user.mention_html()
        return mention

    @property
    def template(self):
        template = "\n" + self.context.bot.lang_dict["shop_admin_order_temp_1"].format(
            self.str_status,
            self.article,
            self.creation_timestamp,
            self.user_mention,
            self.phone_number)

        if self.user_comment:
            template += self.context.bot.lang_dict["comment_field"].format(
                html.escape(self.user_comment, quote=False))

        template += self.context.bot.lang_dict["shop_admin_order_temp_2"].format(
            self.total_price,
            self.currency,
            self.str_order_items())
        # template = (
        #     "\n" + self.context.bot.lang_dict["shop_admin_order_temp"].format(
        #         self.str_status,
        #         self.article,
        #         self.creation_timestamp,
                # self.str_product_status,
                # self.user_mention,
                # self.phone_number,
                # html.escape(self.user_comment, quote=False),
                # self.total_price,
                # self.currency,
                # self.str_order_items()))

        return template

    @property
    def str_status(self):
        shop = chatbots_table.find_one({"bot_id": self.context.bot.id})["shop"]

        if self.in_trash:
            string = self.context.bot.lang_dict["order_status_canceled"]
            if self.paid:
                string += self.context.bot.lang_dict["paid_status_refund"].format(self.total_price,
                                                                                  self.currency)
        elif self.status:
            string = self.context.bot.lang_dict["shop_admin_order_status_true"]
        else:
            string = self.context.bot.lang_dict["shop_admin_order_status_new"]
            if self.paid:
                string += self.context.bot.lang_dict["paid_status_true"]
            elif shop["shop_type"] == "online" and not self.paid:
                string += self.context.bot.lang_dict["paid_status_false"]

        if self.shipping:
            string += self.context.bot.lang_dict["delivery_to"].format(
                html.escape(self.address, quote=False))
        else:
            string += self.context.bot.lang_dict["pick_up_from"].format(
                html.escape(shop.get("address", ""), quote=False))
        return string

    def send_short_template(self, update, context,
                            text="", reply_markup=None):
        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=self.template + "\n\n" + text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML))

    def send_full_template(self, update, context, text="", reply_markup=None,
                           item_reply_markup=None):
        # PAGINATION OF ORDER ITEMS
        pagination = Pagination(
            self.items_json, page=context.user_data["item_page"])
        for item in pagination.page_content():
            OrderItem(self.context, item, self.currency).send_template(
                update, context, reply_markup=item_reply_markup)
        pagination.send_keyboard(update, context,
                                 page_prefix="admin_order_item_pagination")

        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=self.template + "\n\n" + text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML))


class UserOrder(Order):
    def __init__(self, context,  obj: (ObjectId, dict, str) = None):
        super(UserOrder, self).__init__(context, obj)

    @property
    def template(self):
        template = self.context.bot.lang_dict["user_order_temp"].format(
            self.article,
            self.str_status,
            self.total_price,
            self.currency,
            self.phone_number)
        if self.user_comment:
            template += self.context.bot.lang_dict["comment_field"].format(
                html.escape(self.user_comment, quote=False))
        template += "\n\n" + self.str_order_items()
        return template

    """"@property
    def str_status(self):
        shop = chatbots_table.find_one({"bot_id": self.context.bot.id})["shop"]
        if self.in_trash:
            string = self.context.bot.lang_dict["order_status_canceled"]
            if self.paid:
                string += "\n                 ♻️ " + str(self.total_price) + " " + self.currency
            return string
        if self.status:
            string = self.context.bot.lang_dict["shop_admin_order_status_true"]
            return string
        if self.shipping:
            # string = self.context.bot.lang_dict["order_on_way_to"].format(self.address)
            string = "🚚 " + f"{html.escape(self.address, quote=False)}"
        else:
            string = self.context.bot.lang_dict["order_wait_on"].format(
                html.escape(shop['address'], quote=False))
        if self.paid:
            string += self.context.bot.lang_dict["paid_status_true"]
        elif shop["shop_type"] == "online" and not self.paid:
            string += self.context.bot.lang_dict["paid_status_false"]
        return string"""

    @property
    def str_status(self):
        shop = chatbots_table.find_one({"bot_id": self.context.bot.id})["shop"]
        if self.in_trash:
            string = self.context.bot.lang_dict["order_status_canceled"]
            if self.paid:
                string += self.context.bot.lang_dict["paid_status_refund"].format(self.total_price,
                                                                                  self.currency)
        elif self.status:
            string = self.context.bot.lang_dict["shop_admin_order_status_true"]
        else:
            if self.shipping:
                string = self.context.bot.lang_dict["delivery_status"]
            else:
                string = self.context.bot.lang_dict["self_delivery_status"]
            if self.paid:
                string += self.context.bot.lang_dict["paid_status_true"]
            elif shop["shop_type"] == "online" and not self.paid:
                string += self.context.bot.lang_dict["paid_status_false"]

        if self.shipping:
            string += self.context.bot.lang_dict["user_delivery_to"].format(
                html.escape(self.address, quote=False))
        else:
            string += self.context.bot.lang_dict["user_pick_up_from"].format(
                html.escape(shop.get("address", ""), quote=False))
        return string

    def send_full_template(self, update, context, text="", reply_markup=None,
                           item_reply_markup=None):
        # PAGINATION OF ORDER ITEMS
        pagination = Pagination(
            self.items_json, page=context.user_data["item_page"])
        for item in pagination.page_content():
            OrderItem(self.context, item, self.currency).send_template(
                update, context, reply_markup=item_reply_markup)
        pagination.send_keyboard(update, context,
                                 page_prefix="user_order_item_pagination")

        context.user_data["to_delete"].append(
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=self.template + "\n\n" + text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML))


class OrderItem(Product):
    """For showing and check orders items.
    Works for both bots and admin side"""

    def __init__(self, context, order_item, currency):
        # change order_item["product_id"] to order_item["product"]
        # and item data will be taken from order document.
        # Items data that was on the order creation moment
        super(OrderItem, self).__init__(context, order_item["product"])
        # Units of item that customer ordered
        self.order_quantity = order_item.get("quantity")
        # Check if the product exist, ready for sale, and quantity is right
        # self.item_exist = (
        #     self._id  # if _id == None - mean find_one() call returns None
        #     and self.on_sale
        #     and (self.unlimited or (self.order_quantity <= self.quantity)))
        # price of the item
        # print(self.name)
        # print(self.discount_price)
        # print(self.price)
        if self.discount_price:
            self.item_price = self.discount_price * self.order_quantity
        else:
            self.item_price = self.price * self.order_quantity
        self.currency = currency

    @property
    def item_exist(self):
        return (self._id  # if _id == None - mean find_one() call returns None
                and self.on_sale
                and (self.unlimited or (self.order_quantity <= self.quantity)))

    def send_template(self, update, context, reply_markup=None):
        # currency = chatbots_table.find_one(
        #     {"bot_id": self.context.bot.id})["shop"]["currency"]

        text = self.context.bot.lang_dict["order_item_template"].format(
            self.article,
            html.escape(self.name, quote=False),
            html.escape(self.category["name"], quote=False),
            self.order_quantity,
            self.item_price,
            self.currency)
        self.send_short_template(update, context, text, reply_markup)

    # @property
    # def item_emoji(self):
    #     """If product can't be sold returns red sticker, else empty string"""
    #     return " 📛" if not self.item_exist else ""
