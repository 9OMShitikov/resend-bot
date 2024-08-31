import tomlkit
import csv

import aiofiles


class Config:
    latency = 0.05
    subjects: dict[str, str] = {}

    chat_cfg_file: str

    chats: dict[str, int]

    def __init__(self, cfg_file: str, chat_cfg_file: str):
        with open(cfg_file, "rb") as f:
            cfg = tomlkit.load(f)

        self.subjects = {subj["subject"]: subj["chat"] for subj in cfg["subjects"]}
        self.latency = cfg["latency"]

        self.chat_cfg_file = chat_cfg_file
        with open(chat_cfg_file, newline="") as f:
            chatreader = csv.reader(f, delimiter=",", quotechar='"')
            self.chats = {chat: int(id) for (chat, id) in chatreader}

    async def add_chat(self, chat_name: str, chat_id: int) -> None:
        self.chats[chat_name] = chat_id
        async with aiofiles.open(self.chat_cfg_file, mode="a") as f:
            await f.write('"{}",{}\n'.format(chat_name, chat_id))


config: Config = None


def set_config(cfg_file: str, chat_cfg_file: str):
    global config
    config = Config(cfg_file, chat_cfg_file)
