from telegram import Update, ParseMode
from telegram.ext import ConversationHandler, CallbackQueryHandler, CallbackContext

from helper_funcs.helper import dismiss_button
from modules.shop.helper.helper import clear_user_data
from modules.shop.helper.keyboards import start_keyboard
from database import orders_table
from helper_funcs.misc import delete_messages


class Welcome(object):
    @staticmethod
    def start(update: Update, context: CallbackContext):
        delete_messages(update, context, True)
        if context.user_data.get("msg_to_send"):
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    update.effective_chat.id,
                    context.user_data["msg_to_send"],
                    parse_mode=ParseMode.HTML,
                    reply_markup=dismiss_button(context)))

        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                context.bot.lang_dict["shop_admin_start_message"],
                reply_markup=start_keyboard(context)))
        return ConversationHandler.END

    @staticmethod
    def back_to_main_menu(update, context, msg_to_send=None):
        clear_user_data(context)
        if msg_to_send:
            context.user_data["msg_to_send"] = msg_to_send
        return Welcome.start(update, context)


START_SHOP_HANDLER = CallbackQueryHandler(pattern="shop_start",
                                          callback=Welcome.start)


BACK_TO_MAIN_MENU_HANDLER = CallbackQueryHandler(Welcome.back_to_main_menu,
                                                 pattern=r"back_to_main_menu")
