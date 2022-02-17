import os

from pymongo import MongoClient

client = MongoClient('localhost', 27017)

db = client['chatbots']

# Bot
chatbots_table = db["crowdbot_chatbots"]
custom_buttons_table = db["custom_buttons"]
admin_passwords_table = db["admin_passwords"]
users_table = db["users"]
user_mode_table = db["user_mode"]
users_messages_to_admin_table = db["users_messages_to_admin_bot"]
conflict_notifications_table = db["conflict_notifications"]
# Shop
products_table = db["products"]
carts_table = db["carts"]
categories_table = db["categories"]
shop_categories_table = db["shop_categories"]
shop_customers_contacts_table = db["customers_contacts"]
orders_table = db["orders"]
# Not used for now
mailing_history = db["mailing_history"]
user_categories_table = db["user_categories"]
channels_table = db["channels"]
groups_table = db["groups_table"]
donations_table = db['donations_table']
surveys_table = db["surveys"]