from datetime import datetime
from database import users_table, chatbots_table, admin_passwords_table
from helper_funcs import helper
from logs import logger


def register_chat(update, context):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    bot_id = context.bot.id

    user = users_table.find_one({"user_id": user_id, "bot_id": bot_id})
    superuser = chatbots_table.find_one({"bot_id": bot_id})["superuser"]

    if not user:

        if user_id == superuser or superuser is None:
            chatbots_table.update_one({"bot_id": bot_id}, {"$set": {"superuser": user_id}})
            users_table.update_one(
                {"user_id": user_id, "bot_id": bot_id},
                {"$set": {'bot_id': bot_id,
                          "chat_id": chat_id,
                          "user_id": user_id,
                          "username": update.effective_user.username,
                          "full_name": update.effective_user.full_name,
                          # 'registered': True,
                          "is_admin": True,
                          "superuser": True,
                          "timestamp": datetime.now(),
                          "regular_messages_blocked": False,
                          "anonim_messages_blocked": False,
                          "order_notification": True,
                          "messages_notification": True,
                          "blocked": False,
                          "unsubscribed": False,
                          # "tags": ["#all", "#bots", "#admin"]
                          }}, upsert=True)
        else:
            users_table.insert_one(
                {'bot_id': bot_id,
                 "chat_id": chat_id,
                 "user_id": user_id,
                 "username": update.effective_user.username,
                 "full_name": update.effective_user.full_name,
                 "timestamp": datetime.now(),
                 # 'registered': False,
                 "is_admin": False,
                 "superuser": False,
                 "regular_messages_blocked": False,
                 "anonim_messages_blocked": False,
                 "order_notification": True,
                 "messages_notification": True,
                 "blocked": False,
                 "unsubscribed": False,
                 # "tags": ["#all", "#bots"]
                 })
    elif user["unsubscribed"]:
        users_table.update_one({"user_id": user_id, "bot_id": context.bot.id},
                               {"$set": {"unsubscribed": False}})
    """if user_id == superuser:
        users_table.update_one(
            {"user_id": user_id, "bot_id": bot_id},
            {"$set": {'bot_id': bot_id,
                      "chat_id": chat_id,
                      "user_id": user_id,
                      "username": update.effective_user.username,
                      "full_name": update.effective_user.full_name,
                      # 'registered': True,
                      "is_admin": True,
                      "superuser": True,
                      "timestamp": datetime.now(),
                      "regular_messages_blocked": False,
                      "anonim_messages_blocked": False,
                      "order_notification": True,
                      "messages_notification": True,
                      "blocked": False,
                      "unsubscribed": False,
                      # "tags": ["#all", "#bots", "#admin"]
                      }}, upsert=True)
    elif not bots:
        users_table.insert_one(
            {'bot_id': bot_id,
             "chat_id": chat_id,
             "user_id": user_id,
             "username": update.effective_user.username,
             "full_name": update.effective_user.full_name,
             "timestamp": datetime.now(),
             # 'registered': False,
             "is_admin": False,
             "superuser": False,
             "regular_messages_blocked": False,
             "anonim_messages_blocked": False,
             "order_notification": True,
             "messages_notification": True,
             "blocked": False,
             "unsubscribed": False,
             # "tags": ["#all", "#bots"]
             })
    elif bots["unsubscribed"]:
        users_table.update_one({"user_id": user_id, "bot_id": context.bot.id},
                               {"$set": {"unsubscribed": False}})"""


def register_admin(update, context):
    """Registers bots as an administrator"""
    # Delete all expired passwords
    for admin_password in admin_passwords_table.find({"bot_id": context.bot.id}):
        if (datetime.today() - admin_password["timestamp"]).total_seconds() > 3600:
            admin_passwords_table.delete_one({"_id": admin_password["_id"]})
    # Check if the bots already admin if so - just back
    if users_table.find_one({"bot_id": context.bot.id,
                             "user_id": update.effective_user.id})["is_admin"]:
        return False
    # Take password from update
    password = update.message.text.split("registration")[-1]
    # Check db for the password. We deleted all the wrong passwords,
    # so if the password is found, then it is valid
    # and never used before(coz we delete password after registration)
    admin_password = admin_passwords_table.find_one({"bot_id": context.bot.id,
                                                     "password": password})
    # Register bots only if the password is correct
    # and date not expired and password never used before
    if admin_password:
        # Invalidate password(delete it)
        admin_passwords_table.delete_one({"_id": admin_password["_id"]})
        # Set bots as administrator
        users_table.update_one(
            {"user_id": update.effective_user.id, "bot_id": context.bot.id},
            {"$set": {
                'bot_id': context.bot.id,
                "chat_id": update.effective_chat.id,
                "user_id": update.effective_user.id,
                "username": update.effective_user.username,
                "full_name": update.effective_user.full_name,
                "timestamp": datetime.now(),
                # 'registered': True,
                "is_admin": True,
                "regular_messages_blocked": False,
                "anonim_messages_blocked": False,
                "order_notification": True,
                "messages_notification": True,
                "superuser": False,
                "blocked": False,
                "unsubscribed": False,
                # "tags": ["#all", "#bots", "#admin"]
            }}, upsert=True)

        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=context.bot.lang_dict["hello_new_admin"].format(
                update.effective_user.full_name),
            reply_markup=helper.dismiss_button(context))

        logger.info(f"New admin {update.effective_user.full_name} "
                    f"on bot {context.bot.first_name}:{context.bot.id}")
        return True
    else:
        logger.info(f"Admin authentication failed for {update.effective_user.full_name} "
                    f"on bot {context.bot.first_name}:{context.bot.id}")
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=context.bot.lang_dict["registration_link_not_active"])
        return False


def initiate_chat_id(update):

    chat_id = update.effective_chat.id
    if update.message:
        txt = ""
        if update.message.text:
            txt = txt + update.message.text
        elif update.message.caption:
            txt = txt + update.message.caption
    else:
        txt=None
    return chat_id, txt


def if_admin(update, context):
    # todo maybe just check is_admin field?
    # if update.message:
    #     user_id = update.message.from_user.id
    # else:
    #     user_id = update.callback_query.from_user.id
    user_id = update.effective_user.id
    superuser = chatbots_table.find_one({"bot_id": context.bot.id})["superuser"]
    if user_id == superuser:
        return True
    admin_chat = users_table.find_one({'user_id': user_id, "bot_id": context.bot.id})
    if admin_chat is not None:
        if (  # admin_chat["registered"] and
                admin_chat["is_admin"]):
            return True
        else:
            return False
    else:
        return False


def superuser_doc() -> dict:
    pass


def regular_user_doc() -> dict:
    pass
