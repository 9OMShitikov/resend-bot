import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

import config
import message_handler


async def main() -> None:
    bot = Bot(token=config.config.token)

    dp = Dispatcher()
    dp.include_routers(message_handler.form_router)

    bot_commands = [
        BotCommand(
            command="/start",
            description="Начать вводить заявку (ввод предыдущей прерывается)",
        ),
    ]
    await bot.set_my_commands(bot_commands)

    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, filename="log.txt")
    asyncio.run(main())
