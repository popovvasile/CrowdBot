from telegram import ParseMode, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ConversationHandler, CallbackQueryHandler, CallbackContext

from modules.shop.helper.helper import clear_user_data
from modules.shop.admin_side.welcome import Welcome
from modules.shop.components.product import Product
from modules.shop.admin_side.products import ProductsHandler
from modules.shop.admin_side.orders import OrdersHandler
from database import products_table, orders_table
from helper_funcs.misc import delete_messages


class TrashHandler(Welcome):
    def start_trash(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_orders_btn"],
                callback_data="trashed_orders")],
            [InlineKeyboardButton(
                context.bot.lang_dict["shop_admin_products_btn"],
                callback_data="trashed_products")],
            [InlineKeyboardButton(
                context.bot.lang_dict["back_button"],
                callback_data="back_to_main_menu_btn")]
        ])
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                context.bot.lang_dict["shop_admin_trash_start"],
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup))
        return ConversationHandler.END

    def orders(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith("admin_order_list_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("admin_order_list_pagination_", ""))
        if not context.user_data.get("page"):
            context.user_data["page"] = 1

        all_orders = orders_table.find({"in_trash": True,
                                        "bot_id": context.bot.id}).sort([["_id", 1]])
        return OrdersHandler().orders_layout(update, context, all_orders, ORDERS)

    # def restore_order(self, update: Update, context: CallbackContext):
    #     context.bot.send_chat_action(update.effective_chat.id, "typing")
    #     order_id = update.callback_query.data.split("/")[1]
    #     Order(order_id).update({"in_trash": False})
    #     update.callback_query.answer(
    #         context.bot.lang_dict["shop_admin_order_restored_blink"])
    #     return self.back_to_orders(update, context)

    def products(self, update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        # Set current page integer in the user_data.
        if update.callback_query.data.startswith("item_list_pagination"):
            context.user_data["page"] = int(
                update.callback_query.data.replace("item_list_pagination_", ""))
        if not context.user_data.get("page"):
            context.user_data["page"] = 1

        all_products = products_table.find({"in_trash": True,
                                            "bot_id": context.bot.id}).sort([["_id", 1]])
        return ProductsHandler().products_layout(update, context, all_products, PRODUCTS)

    def restore_product(self, update: Update, context: CallbackContext):
        context.bot.send_chat_action(update.effective_chat.id, "typing")
        product_id = update.callback_query.data.split("/")[1]
        Product(context, product_id).update({"in_trash": False})
        update.callback_query.answer(context.bot.lang_dict["shop_admin_product_restored_blink"])
        return self.back_to_products(update, context)

    def back_to_orders(self, update, context):
        page = context.user_data.get("page")
        clear_user_data(context)
        context.user_data["page"] = page
        return self.orders(update, context)

    def back_to_products(self, update, context):
        page = context.user_data.get("page")
        clear_user_data(context)
        context.user_data["page"] = page
        return self.products(update, context)

    def back_to_trash(self, update, context):
        page = context.user_data.get("page")
        clear_user_data(context)
        context.user_data["page"] = page
        return self.start_trash(update, context)


ORDERS, WHOLESALE_ORDERS, PRODUCTS = range(3)


fallbacks = [CallbackQueryHandler(TrashHandler().back_to_main_menu,
                                  pattern=r"back_to_main_menu"),
             CallbackQueryHandler(TrashHandler().start_trash,
                                  pattern=r"back_to_trash"),
             CallbackQueryHandler(Welcome().back_to_main_menu,
                                  pattern=r"help_back"),
             ]


TRASH_START = CallbackQueryHandler(TrashHandler().start_trash,
                                   pattern=r"trash")


ORDERS_TRASH = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(TrashHandler().orders,
                                       pattern=r"trashed_orders")],
    states={
        ORDERS: [CallbackQueryHandler(TrashHandler().orders,
                                      pattern=r"admin_order_list_pagination"),
                 # CallbackQueryHandler(TrashHandler().restore_order,
                 #                      pattern=r"restore")
                 ]
    },
    fallbacks=fallbacks
)


PRODUCTS_TRASH = ConversationHandler(
    allow_reentry=True,
    entry_points=[CallbackQueryHandler(TrashHandler().products,
                                       pattern=r"trashed_products")],
    states={
        PRODUCTS: [CallbackQueryHandler(TrashHandler().products,
                                        pattern=r"item_list_pagination"),
                   CallbackQueryHandler(TrashHandler().restore_product,
                                        pattern=r"restore_product")],
    },
    fallbacks=fallbacks
)
