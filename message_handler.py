import asyncio
import logging
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InputMediaPhoto,
)
import config
import dialogue_tree

form_router = Router()


# Проверка, что сообщение от пользователя, а не из чата учителей
class SubjFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.id not in config.config.chats.values()


# Максимальное суммарное к-во символов в кнопках строки
TG_LINE_LEN = 10


# Состояния чата пользователя:
class Form(StatesGroup):
    # дерево диалога
    tree = State()
    # какая именно проблема (пересылаемое сообщение с фото)
    what = State()


# `кнопки` с вариантами ответов
def get_opt_markup(node: dialogue_tree.DialogueNode):
    if node.options:
        options = node.options.keys()
        if sum(map(len, options)) > TG_LINE_LEN:
            keyboard = [[KeyboardButton(text=opt)] for opt in options]
        else:
            keyboard = [[KeyboardButton(text=opt) for opt in options]]

        return ReplyKeyboardMarkup(
            keyboard=keyboard,
            resize_keyboard=True,
        )
    return ReplyKeyboardRemove()


# `кнопка` старта
start_markup = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="start"),
        ]
    ],
    resize_keyboard=True,
)


# Начало общения (или после нажатия на старт)
@form_router.message(CommandStart(), SubjFilter())
@form_router.message(Command("start"), SubjFilter())
@form_router.message(F.text.casefold() == "start", SubjFilter())
async def command_start(message: Message, state: FSMContext) -> None:
    logging.info(
        "start message: @{}, chat_id: {}".format(
            message.from_user.username, message.chat.id
        )
    )
    await state.clear()
    await state.update_data(node=None, next=None, fields={}, lock=asyncio.Lock())
    await state.set_state(Form.tree)
    await process_msg(message, state, node=config.config.tree)


# вопрос диалога
async def process_msg(
    message: Message, state: FSMContext, node: dialogue_tree.DialogueNode
) -> None:
    await state.update_data(node=node, next=node.next)
    await message.answer(
        node.question,
        reply_markup=get_opt_markup(node),
    )


# неправильный ответ на вопрос диалога
async def process_resend(message: Message, node: dialogue_tree.DialogueNode) -> None:
    question = node.resend_question
    if question is None:
        question = node.question
    await message.reply(
        question,
        reply_markup=get_opt_markup(node),
    )


# обработка полученного ответа, вопрос о проблеме
@form_router.message(Form.tree, SubjFilter())
async def process_answer(message: Message, state: FSMContext) -> None:
    answer = message.text
    state_data = await state.get_data()
    node: Optional[dialogue_tree.DialogueNode] = state_data.get("node")
    next: Optional[dialogue_tree.DialogueNode] = state_data.get("next")
    fields = state_data["fields"]
    if node is not None:
        if node.options is not None:
            if option := node.options.get(answer):
                if option.chat:
                    await state.update_data(chat_id=option.chat)
                if node.field:
                    fields[node.field] = answer
                    await state.update_data(fields=fields)
                if option.next is not None:
                    next = option.next
                if next is not None:
                    await process_msg(message, state, next)
                else:
                    await process_ask(message, state)
            else:
                await process_resend(message, node)
        else:
            if answer.isdigit():
                if node.field:
                    fields[node.field] = answer
                    await state.update_data(fields=fields)
                if next is not None:
                    await process_msg(message, state, next)
                else:
                    await process_ask(message, state)
            else:
                await process_resend(message, node)


# Вопрос о проблеме (с фото)
async def process_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.what)
    await message.answer(
        "Опишите проблему, приложите фотографию, если нужно:",
        reply_markup=ReplyKeyboardRemove(),
    )


# Ожидание ответов о проблеме (каждое фото присылается в отдельном сообщении)
@form_router.message(Form.what)
async def process_done(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1] if message.photo else None
    text = message.text
    if text is None:
        text = message.caption

    data = await state.get_data()
    # Обновление списка сообщений, не смог обойтись без блокировки
    # иначе возможны пропуски в списке фото при одновременной обработке двух и более сообщений с фото
    l: asyncio.Lock = data["lock"]
    async with l:
        locked_data = await state.get_data()
        if not text:
            text = locked_data.get("text")
        lock_photos: list[str] = locked_data.get("photos", [])
        if photo:
            lock_photos.append(photo.file_id)
        await state.update_data(photos=lock_photos, text=text)

    # Первое принятое сообщение
    if "photos" not in locked_data:
        # Ожидание остальных сообщений
        await asyncio.sleep(config.config.latency)

        data = await state.get_data()
        photos = set(data["photos"])
        text = data["text"]

        logging.info(
            "resent message: @{}; chat_id: {}; message_id: {}; photos: {}".format(
                message.from_user.username,
                message.chat.id,
                message.message_id,
                ", ".join(photos),
            )
        )

        fields = data["fields"]
        if fields["type"] != "другое":
            problem = "ошибка в учебных материалах\n"
            if "discipline" in fields:
                problem += "Дисциплина: {}\n".format(fields["discipline"])
            problem += "Класс: {}\nУрок: {}\n".format(fields["grade"], fields["lesson"])
        else:
            problem = "другое\n"
        text = ("Пользователь: @{}, {}\nПроблема: {}Текст: {}").format(
            message.from_user.username, message.from_user.url, problem, text
        )

        if photos:
            # Пересылка со списком фото (по ссылкам)
            msg = await message.bot.send_media_group(
                chat_id=data["chat_id"],
                media=[
                    InputMediaPhoto(media=id, caption=text if i == 0 else None)
                    for (i, id) in enumerate(photos)
                ],
            )
        else:
            # Пересылка чистого текста
            msg = await message.bot.send_message(
                chat_id=data["chat_id"],
                text=text,
            )
        logging.info("resent to chat `{}` ({})".format(msg.chat.title, msg.chat.id))

        await state.clear()
        await message.answer(
            "Принято, спасибо!",
            reply_markup=start_markup,
        )
