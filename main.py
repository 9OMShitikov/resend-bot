import argparse
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from os import getenv

from config import set_config
import message_handler
import new_group_handler

token = getenv("BOT_TOKEN")


async def main() -> None:
    bot = Bot(token=token)

    dp = Dispatcher()
    dp.include_routers(message_handler.form_router, new_group_handler.group_router)

    bot_commands = [
        BotCommand(
            command="/start",
            description="Начать вводить заявку (ввод предыдущей прерывается)",
        ),
    ]
    await bot.set_my_commands(bot_commands)

    await dp.start_polling(bot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sirius telegram bot")
    parser.add_argument(
        "-cfg", "--config", type=str, default="config.toml", help="config file"
    )

    parser.add_argument(
        "-ch",
        "--chats",
        type=str,
        default="chats.csv",
        help="list of chats the bot is in",
    )

    parser.add_argument(
        "-l",
        "--logfile",
        type=str,
        default="/var/log/siriusbot.log",
        help="log file",
    )

    namespace = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        filemode="a",
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        filename=namespace.logfile,
    )
    set_config(namespace.config, namespace.chats)

    asyncio.run(main())
