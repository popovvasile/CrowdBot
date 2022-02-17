from datetime import datetime
from uuid import uuid4
import html

from bson.objectid import ObjectId
from telegram.error import BadRequest
from telegram.constants import MAX_CAPTION_LENGTH
from telegram import (ParseMode, InputMediaPhoto)

from helper_funcs.helper import currency_limits_dict
from helper_funcs.misc import get_obj, get_promise_msg
from helper_funcs.constants import MAX_TEMP_DESCRIPTION_LENGTH, MAX_PRODUCT_NAME_LENGTH
from modules.shop.helper.helper import send_media_arr
from database import products_table, categories_table, orders_table, chatbots_table


class Product(object):
    def __init__(self, context, obj: (ObjectId, dict, str) = None):
        self.context = context
        product = get_obj(products_table, obj)
        # Change _id attribute to id_
        self._id = product.get("_id")
        self.bot_id = context.bot.id
        self.article = product.get("article")
        self.price = product.get("price")
        self.description = product.get("description", "")
        self.name = product.get("name")
        self.discount_price = product.get("discount_price", 0)
        self.order_ids = product.get("order_ids", list())
        self.content = product.get("content", list())
        self.in_trash = product.get("in_trash")
        self.category_id = product.get("category_id")
        # Quantity of the product to show in the shop.
        # Reduce quantity after customer order
        self.quantity = product.get("quantity")
        self.unlimited = product.get("unlimited")

    @property
    def category_id(self):
        return self._category_id

    @category_id.setter
    def category_id(self, _id):
        if type(_id) is str:
            _id = ObjectId(_id)
        self._category_id = _id
        self.category = categories_table.find_one({"_id": _id})

    @property
    def id_(self):
        """a name prefixed with an underscore
        should be treated as a non-public part of the API"""
        return self._id

    @property
    def on_sale(self):
        """To check if at least one product unit is ready for sale"""
        if self.in_trash or (not self.unlimited and self.quantity == 0):
            return False
        else:
            return True

    @property
    def files_str(self):
        return self.context.bot.lang_dict["files_counter"].format(len(self.content))

    @property
    def quantity_str(self):
        if self.unlimited:
            return self.context.bot.lang_dict["unlimited"]
        else:
            return str(self.quantity)

    def price_as_str(self, currency=None):
        if not currency:
            currency = chatbots_table.find_one(
                {"bot_id": self.context.bot.id})["shop"]["currency"]
        if self.discount_price:
            return f"💥 <s>{self.price}</s> <u>{self.discount_price} {currency}</u>"
        else:
            return f"<u>{self.price} {currency}</u>"

    @property
    def status_str(self):
        new_orders = orders_table.find(
            {"bot_id": self.context.bot.id,
             "status": False,
             "in_trash": False,
             "items.product_id": self._id})
        # Admin product status string.
        # Product was deleted
        if self.in_trash:
            status = self.context.bot.lang_dict["product_deleted_status"]
        # At least on item of the product on sale
        elif self.on_sale:
            status = self.context.bot.lang_dict["product_on_sale_status"]
        # Product not on sale because it is in the NEW order
        elif new_orders.count():
            status = self.context.bot.lang_dict["product_unfinished_orders"].format(
                new_orders.count())
        else:
            status = self.context.bot.lang_dict["product_sold_status"]
        return status

    @staticmethod
    def create_price(update, context):
        """Text in update required"""
        currency = chatbots_table.find_one({"bot_id": context.bot.id})["shop"]["currency"]
        currency_limits = currency_limits_dict[currency]
        result = dict()
        try:
            assert currency_limits["min"] < float(update.message.text) < currency_limits["max"]
        except AssertionError:
            result["ok"] = False
            result["error_message"] = context.bot.lang_dict["shop_admin_price_wrong"].format(
                    currency_limits["min"], currency, currency_limits["max"], currency)
            return result
        except (ValueError, OverflowError):
            result["ok"] = False
            result["error_message"] = (
                context.bot.lang_dict["add_product_wrong_floating_point_number"])
            return result

        result["ok"] = True
        result["price"] = float(format(float(update.message.text), '.2f'))
        return result

    @staticmethod
    def create_quantity(update, context):
        """Text in update required"""
        result = dict()
        try:
            assert int(float(update.message.text)) > 0
        except (AssertionError, ValueError, OverflowError):
            result["ok"] = False
            result["error_message"] = context.bot.lang_dict["shop_admin_number_wrong"]
            return result

        if len(update.message.text) <= 10:
            result["ok"] = True
            result["quantity"] = int(float(update.message.text))
        else:
            result["ok"] = False
            result["error_message"] = context.bot.lang_dict["shop_admin_quantity_too_big"]
        return result

    def send_short_template(self, update, context,
                            text=None, reply_markup=None):
        """Send short representation of the product.
        Must pass only short templates to this method

        Works for the both bots and admin side.
        All templates, strings and keyboard must be passed as arguments"""
        try:
            if len(self.content):
                self.send_content(
                    update.effective_chat.id, context, self.content[0],
                    caption=text, reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML)

            else:
                context.user_data["to_delete"].append(
                    context.bot.send_message(chat_id=update.effective_chat.id,
                                             text=text,
                                             reply_markup=reply_markup,
                                             parse_mode=ParseMode.HTML))

        except (BadRequest, IndexError):
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=context.bot.lang_dict["shop_admin_image_exception"]
                    + "\n\n" + text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup))

    def send_full_template(self, update, context,
                           text=None, reply_markup=None):
        """Send full representation of the product.
        text: full template of the product

        Works for the both bots and admin side.
        All templates, strings and keyboard must be passed as arguments
        """
        reply_to_message_id = None

        if len(self.content) == 0:
            if len(self.description) > MAX_TEMP_DESCRIPTION_LENGTH:
                context.user_data["to_delete"].append(
                    context.bot.send_message(update.effective_chat.id,
                                             self.description, quote=False))
                reply_to_message_id = get_promise_msg(
                    context.user_data["to_delete"][-1]).message_id
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=reply_to_message_id))

        elif len(self.content) == 1:
            if len(self.description) > MAX_TEMP_DESCRIPTION_LENGTH:
                if len(self.description) > MAX_CAPTION_LENGTH:
                    self.send_content(update.effective_chat.id,
                                      context, self.content[0],
                                      caption=html.escape(self.name, quote=False))
                    reply_to_message_id = get_promise_msg(
                        context.user_data["to_delete"][-1]).message_id
                    context.user_data["to_delete"].append(
                        context.bot.send_message(
                            update.effective_chat.id,
                            self.description,
                            reply_to_message_id=reply_to_message_id))
                    context.user_data["to_delete"].append(
                        context.bot.send_message(
                            update.effective_chat.id,
                            text=text,
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.HTML,
                            reply_to_message_id=reply_to_message_id))
                else:
                    self.send_content(update.effective_chat.id,
                                      context, self.content[0],
                                      caption=html.escape(self.description, quote=False))
                    reply_to_message_id = get_promise_msg(
                        context.user_data["to_delete"][-1]).message_id
                    context.user_data["to_delete"].append(
                        context.bot.send_message(
                            update.effective_chat.id,
                            text=text,
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.HTML,
                            reply_to_message_id=reply_to_message_id))
            else:
                self.send_content(update.effective_chat.id,
                                  context, self.content[0],
                                  caption=text, reply_markup=reply_markup)
        else:
            if all(content_dict["type"] == "photo_file"
                   for content_dict in self.content):
                full_media_group = [
                    InputMediaPhoto(content_dict["file_id"])
                    for content_dict in self.content]
                send_media_arr(full_media_group, update, context)
            else:
                # First file - title file
                self.send_content(update.effective_chat.id,
                                  self.context, self.content[0])

                images = list()
                other_types = list()
                for content_dict in self.content[1:]:
                    if content_dict["type"] == "photo_file":
                        images.append(content_dict)
                    else:
                        other_types.append(content_dict)

                # Then goes all images
                if len(images) >= 2:
                    full_media_group = [
                        InputMediaPhoto(content_dict["file_id"])
                        for content_dict in images]
                    send_media_arr(full_media_group, update, context)
                elif len(images) == 1:
                    other_types.insert(0, images[0])

                # And then goes all other types of content
                for content_dict in other_types:
                    self.send_content(update.effective_chat.id,
                                      self.context, content_dict)

            reply_to_message_id = get_promise_msg(
                context.user_data["to_delete"][-len(self.content)]).message_id

            if len(self.description) > MAX_TEMP_DESCRIPTION_LENGTH:
                context.user_data["to_delete"].append(
                    context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=html.escape(self.description, quote=False),
                        reply_to_message_id=reply_to_message_id,
                        parse_mode=ParseMode.HTML))
            context.user_data["to_delete"].append(
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=reply_to_message_id))

    def add_content_dict(self, update, to_save=False):
        # todo use create_content_dict from misc(note about text video_note_file and sticker_file)
        """Create content_dict from update and add it to product.
        If to_save == True - save it to db

        video_note_file and sticker_file - don't have captions

         "id" field coz of -
        https://github.com/python-telegram-bot/python-telegram-bot/issues/1267
        """
        content_dict = {}
        if update.message.photo:
            photo_file = update.message.photo[-1].file_id
            content_dict = {"file_id": photo_file,
                            "type": "photo_file",
                            "id": str(uuid4())}

        elif update.message.audio:
            audio_file = update.message.audio.file_id
            content_dict = {"file_id": audio_file,
                            "type": "audio_file",
                            "name": update.message.audio.title,
                            "id": str(uuid4())}

        elif update.message.voice:
            voice_file = update.message.voice.file_id
            content_dict = {"file_id": voice_file,
                            "type": "voice_file",
                            "id": str(uuid4())}

        elif update.message.document:
            document_file = update.message.document.file_id
            content_dict = {"file_id": document_file,
                            "type": "document_file",
                            "name": update.message.document.file_name,
                            "id": str(uuid4())}

        elif update.message.video:
            video_file = update.message.video.file_id
            content_dict = {"file_id": video_file,
                            "type": "video_file",
                            "id": str(uuid4())}

        elif update.message.animation:
            animation_file = update.message.animation.file_id
            content_dict = {"file_id": animation_file,
                            "type": "animation_file",
                            "id": str(uuid4())}
        if content_dict:
            self.content.append(content_dict)
            if to_save:
                products_table.find_and_modify(
                    {"_id": self._id}, {"$push": {"content": content_dict}})
                self.refresh()
        return content_dict

    @staticmethod
    def send_content(chat_id, context, content_dict,
                     caption=None, parse_mode=ParseMode.HTML,
                     reply_markup=None):
        # todo use send_content_dict from misc(note about text, video_note_file and sticker_file)
        """Sends one content_dict

        video_note_file and sticker_file - don't have captions"""

        if content_dict["type"] == "audio_file":
            context.user_data["to_delete"].append(
                context.bot.send_audio(chat_id,
                                       content_dict["file_id"],
                                       caption=caption,
                                       parse_mode=parse_mode,
                                       reply_markup=reply_markup))

        if content_dict["type"] == "voice_file":
            context.user_data["to_delete"].append(
                context.bot.send_voice(chat_id,
                                       content_dict["file_id"],
                                       caption=caption,
                                       parse_mode=parse_mode,
                                       reply_markup=reply_markup))

        if content_dict["type"] == "video_file":
            context.user_data["to_delete"].append(
                context.bot.send_video(chat_id,
                                       content_dict["file_id"],
                                       caption=caption,
                                       parse_mode=parse_mode,
                                       reply_markup=reply_markup))

        if content_dict["type"] == "document_file":
            if (".png" in content_dict["file_id"] or
                    ".jpg" in content_dict["file_id"]):
                context.user_data["to_delete"].append(
                    context.bot.send_photo(chat_id,
                                           content_dict["file_id"],
                                           caption=caption,
                                           parse_mode=parse_mode,
                                           reply_markup=reply_markup))
            else:
                context.user_data["to_delete"].append(
                    context.bot.send_document(chat_id,
                                              content_dict["file_id"],
                                              caption=caption,
                                              parse_mode=parse_mode,
                                              reply_markup=reply_markup))

        if content_dict["type"] == "photo_file":
            context.user_data["to_delete"].append(
                context.bot.send_photo(chat_id,
                                       content_dict["file_id"],
                                       caption=caption,
                                       parse_mode=parse_mode,
                                       reply_markup=reply_markup,
                                       # mime_type="image"
                                       ))

        if content_dict["type"] == "animation_file":
            context.user_data["to_delete"].append(
                context.bot.send_animation(chat_id,
                                           content_dict["file_id"],
                                           caption=caption,
                                           parse_mode=parse_mode,
                                           reply_markup=reply_markup))

    def update(self, json):
        # todo findAndModify
        products_table.update_one({"_id": self._id}, {"$set": json})
        self.refresh()

    def refresh(self, obj=None):
        if not obj:
            product = get_obj(products_table, self._id)
        else:
            product = get_obj(products_table, obj)

        self._id = product.get("_id")
        self.article = str(self._id)
        self.price = product.get("price")
        self.description = product.get("description", "")
        self.name = product.get("name")
        self.discount_price = product.get("discount_price")
        self.order_ids = product.get("order_ids", list())
        self.content = product.get("content", list())
        self.in_trash = product.get("in_trash")
        self.category_id = product.get("category_id")
        self.quantity = product.get("quantity")
        self.unlimited = product.get("unlimited")

    def to_dict(self):
        return {
            "_id": self._id,
            "bot_id": self.bot_id,
            "article": self.article,
            "price": self.price,
            "description": self.description,
            "name": self.name,
            "discount_price": self.discount_price,
            "order_ids": self.order_ids,
            "content": self.content,
            "in_trash": self.in_trash,
            "category_id": self.category_id,
            "quantity": self.quantity,
            "unlimited": self.unlimited,
        }

    def create(self):
        products_table.insert_one({
            "bot_id": self.context.bot.id,
            "article": str(uuid4()).upper()[:6],
            "price": self.price,
            "discount_price": self.discount_price,
            "description": self.description,
            "name": self.name,
            "category_id": self.category_id,
            "content": self.content,
            "in_trash": False,
            "on_sale": True,
            "order_ids": list(),
            "creation_timestamp": datetime.now(),
            # refresh after product restore from trash or order canceling
            # - to show on the first page
            "last_modify_timestamp": datetime.now(),
            "quantity": self.quantity,
            "unlimited": self.unlimited,
        })


# TODO put special logic here
class AdminProduct(Product):
    def __init__(self, context, obj: (ObjectId, dict, str) = None):
        super(AdminProduct, self).__init__(context, obj)


# TODO put special logic here
class UserProduct(Product):
    def __init__(self, context, obj: (ObjectId, dict, str) = None):
        super(UserProduct, self).__init__(context, obj)


# TODO put special logic here
class CartProduct(Product):
    def __init__(self, context,  obj: (ObjectId, dict, str) = None):
        super(CartProduct, self).__init__(context, obj)
