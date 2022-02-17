from telegram import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (ConversationHandler, CallbackQueryHandler, MessageHandler,
                          PreCheckoutQueryHandler, Filters)
from bson.objectid import ObjectId

from helper_funcs.helper import get_help, back_to_modules
from helper_funcs.misc import delete_messages, get_obj
from helper_funcs.pagination import Pagination
from modules.shop.components.order import UserOrder
from modules.shop.user_side.online_payment import OnlinePayment
from modules.shop.user_side.cart import CartHelper
from database import (products_table, carts_table, chatbots_table,
                      categories_table, orders_table)


class UserOrdersHandler(object):
    def orders(self, update, context):
        delete_messages(update, context, True)
        context.bot.send_chat_action(chat_id=update.effective_chat.id,
                                     action="typing")
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith("user_orders_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("user_orders_pagination_", ""))
        if not context.user_data.get("page"):
            context.user_data["page"] = 1

        # Get orders
        orders = orders_table.find(
            {"user_id": update.effective_user.id,
             "bot_id": context.bot.id}).sort([["_id", -1]])

        # Back to the shop menu if no order
        if not orders.count():
            update.callback_query.answer(context.bot.lang_dict["no_orders_blink"])
            update.callback_query.data = "back_to_module_shop"
            return back_to_modules(update, context)
        # Send page content
        self.send_orders_layout(update, context, orders)
        return ConversationHandler.END

    def send_orders_layout(self, update, context, orders):
        # Title
        # context.user_data['to_delete'].append(
        #     context.bot.send_message(
        #         chat_id=update.callback_query.message.chat_id,
        #         text=context.bot.lang_dict["user_orders_title"].format(orders.count()),
        #         parse_mode=ParseMode.HTML))

        # Orders list buttons
        buttons = [[InlineKeyboardButton(
            text=context.bot.lang_dict["back_button"],
            callback_data="back_to_module_shop")]]

        if orders.count():
            # Create page content and send it
            pagination = Pagination(orders, page=context.user_data["page"])
            shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]
            for order in pagination.content:
                order_buttons = []
                if not order["in_trash"] and not order["paid"] and shop["shop_type"] == "online":
                    order_buttons.append(
                        [InlineKeyboardButton(
                            text=context.bot.lang_dict["pay_button"],
                            callback_data=f"order_payment_menu/{order['_id']}")])
                order_buttons.append(
                    [InlineKeyboardButton(
                        text=context.bot.lang_dict["user_order_items_btn"],
                        callback_data=f"order_items/{order['_id']}")])

                context.user_data["to_delete"].append(
                    context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=UserOrder(context, order).template,
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(order_buttons)))
            # Send main buttons
            pagination.send_keyboard(update, context,
                                     page_prefix="user_orders_pagination",
                                     text=context.bot.lang_dict["user_orders_title"].format(
                                         orders.count()),
                                     buttons=buttons)
        else:
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["no_orders_blink"],
                    reply_markup=InlineKeyboardMarkup(buttons)))

    def order_items(self, update, context):
        delete_messages(update, context, True)
        if update.callback_query.data.startswith("order_items"):
            order_id = ObjectId(update.callback_query.data.split("/")[1])
            order = orders_table.find_one({"_id": order_id})
            if not order:
                return self.orders(update, context)
            context.user_data["order"] = UserOrder(context, order)

        if update.callback_query.data.startswith("user_order_item_pagination"):
            context.user_data["item_page"] = int(
                update.callback_query.data.replace("user_order_item_pagination_", ""))
        if not context.user_data.get("item_page"):
            context.user_data["item_page"] = 1

        context.user_data["order"].send_full_template(
            update, context,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["back_button"],
                    callback_data="back_to_user_orders")]
            ]))
        return ConversationHandler.END

    def order_payment_menu(self, update, context):
        delete_messages(update, context, True)
        order_id = ObjectId(update.callback_query.data.split("/")[1])
        order = UserOrder(context, order_id)
        if not order.id_:
            update.callback_query.answer(context.bot.lang_dict["no_order_blink"])
            return self.back_to_orders(update, context)
        if order.in_trash:
            update.callback_query.answer(context.bot.lang_dict["order_canceled_blink"])
            return self.back_to_orders(update, context)

        reply_markup = [[InlineKeyboardButton(text=context.bot.lang_dict["back_button"],
                                              callback_data="back_to_user_orders")]]
        OnlinePayment().send_invoice(update, context, order,
                                     reply_markup=reply_markup)
        return ConversationHandler.END

    def back_to_orders(self, update, context):
        delete_messages(update, context, True)
        page = context.user_data.get("page", 1)
        context.user_data.clear()
        context.user_data["page"] = page
        return self.orders(update, context)


"""ORDERS"""
USERS_ORDERS_LIST_HANDLER = CallbackQueryHandler(
    pattern=r"^(my_orders|user_orders_pagination)",
    callback=UserOrdersHandler().orders)

USER_ORDER_ITEMS_PAGINATION = CallbackQueryHandler(
    pattern=r"^(order_items|user_order_item_pagination)",
    callback=UserOrdersHandler().order_items)

ORDER_PAYMENT_MENU = CallbackQueryHandler(
    pattern=r"order_payment_menu",
    callback=UserOrdersHandler().order_payment_menu)

BACK_TO_USER_ORDERS = CallbackQueryHandler(
    pattern="back_to_user_orders",
    callback=UserOrdersHandler().back_to_orders)