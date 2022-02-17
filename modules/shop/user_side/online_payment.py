#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
from random import randint

from telegram.error import BadRequest
from telegram import LabeledPrice, InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
from telegram.ext import (MessageHandler, Filters, PreCheckoutQueryHandler,
                          ConversationHandler, CallbackQueryHandler)

from database import products_table, chatbots_table, orders_table, \
    shop_customers_contacts_table, carts_table, \
    users_table
from helper_funcs.misc import delete_messages
from logs import logger
from modules.shop.components.order import UserOrder, AdminOrder
from modules.shop.user_side.cart import Cart


class OnlinePayment(object):
    def send_invoice(self, update, context, order, shop=None, reply_markup=None, description=None):
        context.user_data["paid_order"] = order
        if not shop:
            shop = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]

        if not description:
            description = "\n".join([
                "{}\nx{} {} {}\n".format(
                    item["product"]["name"],
                    item["quantity"],
                    item["product"]["price"],
                    order.currency) for item in order.items_json])

        # The first button must be a Pay button
        if reply_markup:
            reply_markup = InlineKeyboardMarkup(
                [[InlineKeyboardButton(text=context.bot.lang_dict["pay_button"],
                                       pay=True)]]
                + reply_markup)

        title = context.bot.lang_dict["order_id"].format(str(order.article))
        payload = "Purchase"
        start_parameter = "shop-payment"  # TODO change in production
        prices = [LabeledPrice(title, int(float(order.total_price) * 100))]
        try:
            context.user_data["to_delete"].append(
                context.bot.sendInvoice(chat_id=update.effective_chat.id,
                                        title=title,
                                        description=description,
                                        payload=payload,
                                        provider_token=shop["payment_token"],
                                        start_parameter=start_parameter,
                                        currency=order.currency,
                                        prices=prices,
                                        reply_markup=reply_markup))
        except BadRequest as exception:
            logger.info(f"Sending invoice excseption -> {exception}. "
                        f"User {update.effective_user.full_name} on bot {context.bot.username}")
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    update.effective_chat.id,
                    context.bot.lang_dict["payment_not_available"],
                    parse_mode=ParseMode.HTML))
        logger.info("User {} on bot {} requested a purchase".format(
            update.effective_user.first_name, context.bot.first_name))

    def precheckout_callback(self, update, context):
        # query = update.callback_query
        # if query:
        #     if query.data == "help_back":
        #         return ConversationHandler.END
        # TODO - back problem coz there are now callback_query
        # if not context.user_data.get("paid_order"):
        #     return Cart().back_to_cart(update, context)
        query = update.pre_checkout_query
        context.bot.answer_pre_checkout_query(pre_checkout_query_id=query.id, ok=True)
        return ConversationHandler.END

    @staticmethod
    def successful_payment_callback(update, context):
        delete_messages(update, context, True)
        orders_table.update_one({"_id": context.user_data["paid_order"].id_},
                                {"$set": {"paid": True}})
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                context.bot.lang_dict["order_success"],
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        text=context.bot.lang_dict["back_button"],
                        callback_data="back_to_user_orders")]
                ])))
        return ConversationHandler.END

    """"@staticmethod
    def successful_payment_callback(update, context):
        print(update.pre_checkout_query)
        delete_messages(update, context, True)
        order = UserOrder(context, context.user_data["order"])
        # Check products availability
        for item in order.items:
            if not item.item_exist:
                update.callback_query.answer(
                    context.bot.lang_dict["shop_product_not_available"],
                    show_alert=True)
                return Cart().back_to_cart(update, context)
        # Create order
        inserted_id = orders_table.insert_one(
            {**context.user_data["order"],
             **{"article": randint(10000, 99999),
                "status": False,
                "bot_id": context.bot.id,
                "user_id": update.effective_user.id,
                "creation_timestamp": datetime.datetime.now(),
                # "name": update.effective_user.name,
                "in_trash": False,
                "paid": True
                # "is_canceled": False
                }}).inserted_id
        # Remove products from shop
        for item in order.items_json:
            new_fields = dict()
            product = products_table.find_one({"_id": item["product_id"]})
            if not product["unlimited"]:
                new_fields["quantity"] = product["quantity"] - item["quantity"]
                # if new_fields["quantity"] == 0:
                #     new_fields["sold"] = True
            if new_fields:
                products_table.update_one({"_id": item["product_id"]},
                                          {"$set": new_fields})
        # Save contacts
        all_addresses = context.user_data["used_contacts"].get(
            "addresses", list())
        all_numbers = context.user_data["used_contacts"].get(
            "phone_numbers", list())
        address = context.user_data["order"]["address"]
        number = context.user_data["order"]["phone_number"]
        if address and address not in all_addresses:
            if len(all_addresses) > 5:
                all_addresses.insert(0, address)
                del all_addresses[-1]
            else:
                all_addresses.append(address)
        if number not in all_numbers:
            if len(all_numbers) > 5:
                all_numbers.insert(0, number)
                del all_numbers[-1]
            else:
                all_numbers.append(number)
        shop_customers_contacts_table.update_one(
            {"bot_id": context.bot.id,
             "user_id": update.effective_user.id},
            {"$set": {"phone_numbers": all_numbers,
                      "addresses": all_addresses}},
            upsert=True)
        # Clear cart
        carts_table.update_one({"bot_id": context.bot.id,
                                "user_id": update.effective_user.id},
                               {"$set": {"products": list()}})
        # Send notification
        # Send notification about new order to all admins
        order = AdminOrder(context, inserted_id)
        for admin in users_table.find({"bot_id": context.bot.id,
                                       "is_admin": True}):
            # Create notification text and send it.
            text = context.bot.lang_dict["shop_order_template"].format(
                order.article, order.user_mention)

            context.bot.send_message(chat_id=admin["chat_id"],
                                     text=text,
                                     parse_mode=ParseMode.HTML)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=context.bot.lang_dict["thank_you"],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    text=context.bot.lang_dict["back_button"],
                    callback_data="back_to_cart")]]))
        return ConversationHandler.END"""


HANDLE_PRECHECKOUT = PreCheckoutQueryHandler(OnlinePayment().precheckout_callback)

HANDLE_SUCCES = MessageHandler(Filters.successful_payment,
                               OnlinePayment().successful_payment_callback)