import logging

from aiogram import Router
from aiogram.filters import IS_MEMBER, IS_NOT_MEMBER
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter
from aiogram.types import ChatMemberUpdated

import config

group_router = Router()


# Добавили в чат, обновляем список чатов (название: id)
@group_router.my_chat_member(ChatMemberUpdatedFilter(IS_NOT_MEMBER >> IS_MEMBER))
async def on_user_join(event: ChatMemberUpdated):
    logging.info("added to `{}`({})".format(event.chat.full_name, event.chat.id))
    await config.config.add_chat(event.chat.full_name, event.chat.id)
