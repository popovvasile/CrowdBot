from telegram import ParseMode
from telegram.error import BadRequest


# def currencies_emoji():
#     currencies_emoji = {
#         ""
#     }


def clear_user_data(context):
    to_del = context.user_data.get('to_delete', list())
    context.user_data.clear()
    context.user_data['to_delete'] = to_del


# COMPONENTS HELPER FUNCTIONS
def send_media_arr(full_media_group, update, context):
    media_groups_arr = split_list(full_media_group)
    try:
        msgs = [context.bot.send_media_group(
            update.effective_chat.id, m_g)
            for m_g in media_groups_arr]
        for i in msgs:
            context.user_data["to_delete"].extend([b for b in i])
    except BadRequest:
        context.user_data["to_delete"].append(
            context.bot.send_message(
                update.effective_chat.id,
                context.bot.lang_dict["shop_admin_image_exception"],
                parse_mode=ParseMode.HTML))


def split_list(ls):
    return [ls[x:x + 10] for x in range(0, len(ls), 10)]
