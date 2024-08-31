import asyncio
import logging

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

form_router = Router()

situations = ["Была найдена опечатка", "Другое"]


# Проверка, что сообщение от пользователя, а не из чата учителей
class SubjFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.id not in config.config.chats.values()


# Состояния чата пользователя:
class Form(StatesGroup):
    # вопрос о предмете
    subject = State()
    # вопрос о ситуации (опечатка, нет)
    situation = State()
    # если опечатка, какой класс
    where_grade = State()
    # если опечатка, какой урок
    where_lesson = State()
    # какая именно проблема (пересылаемое сообщение с фото)
    what = State()


# `кнопки` с названиями предметов (т.к. список подгружается из конфига, то функция)
def get_subj_markup():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=subj),
            ]
            for subj in config.config.subjects
        ],
        resize_keyboard=True,
    )


# `кнопки` с ситуациями
situation_markup = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=theme),
        ]
        for theme in situations
    ],
    resize_keyboard=True,
)


# `кнопки` с номерами класса
grade_markup = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=str(i)) for i in [7, 8, 10, 11]]],
    resize_keyboard=True,
)


# `кнопка` старта
start_markup = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="start"),
        ]
    ],
    resize_keyboard=True,
)


# Начало общения (или после нажатия на старт), вопрос о предмете
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
    await state.set_state(Form.subject)
    await state.update_data(lock=asyncio.Lock())
    await message.answer(
        "Какой предмет вас интересует?", reply_markup=get_subj_markup()
    )


# Обработка полученного предмета, вопрос о проблеме
@form_router.message(Form.subject, SubjFilter())
async def process_subject(message: Message, state: FSMContext) -> None:
    subj = message.text
    if chat_name := config.config.subjects.get(subj):
        # Нашли название чата предмета, ищем соответствующий id
        if chat_id := config.config.chats.get(chat_name):
            # Нашли id предмета, обновляем состояние
            await state.update_data(subject=subj)
            await state.update_data(chat_id=chat_id)
            await state.set_state(Form.situation)
            await message.answer(
                "Какая возникла проблема?", reply_markup=situation_markup
            )
        else:
            # Нашли название чата предмета, но в списке чатов бота такого нет
            logging.info(
                "chat {} corresponding to {} doesn't correspond to any of chat ids".format(
                    chat_name, subj
                )
            )
            await message.reply(
                "Неверная внутренняя конфигурация, обратитесь к администратору:",
                reply_markup=get_subj_markup(),
            )
    else:
        await message.reply("Предмет не из списка:", reply_markup=get_subj_markup())


# Пользователь сказал, что опечатка
@form_router.message(Form.situation, F.text == "Была найдена опечатка", SubjFilter())
async def process_typo(message: Message, state: FSMContext) -> None:
    await state.update_data(typo=True)
    await state.set_state(Form.where_grade)
    await message.answer("Какой класс (номер)?", reply_markup=grade_markup)


# Пользователь сказал, что опечатка, вопрос о классе
@form_router.message(Form.where_grade, F.text.isdigit(), SubjFilter())
async def process_typo_grade(message: Message, state: FSMContext) -> None:
    await state.update_data(grade=int(message.text))
    await state.set_state(Form.where_lesson)
    await message.answer("Какой урок (номер)?", reply_markup=ReplyKeyboardRemove())


# Пользователь сказал, что опечатка, вопрос о номере урока
@form_router.message(Form.where_lesson, F.text.isdigit(), SubjFilter())
async def process_typo_lesson(message: Message, state: FSMContext) -> None:
    await state.update_data(lesson=int(message.text))
    await process_ask(message=message, state=state)


# Неправильный номер класса (не из списка)
@form_router.message(Form.where_grade, SubjFilter())
async def process_typo_grade_error(message: Message, state: FSMContext) -> None:
    await message.reply("Введите номер класса:", reply_markup=grade_markup)


# Неправильный номер урока (ненатуральное число)
@form_router.message(Form.where_lesson, SubjFilter())
async def process_typo_lesson_error(message: Message, state: FSMContext) -> None:
    await message.reply("Введите номер", reply_markup=ReplyKeyboardRemove())


# Не опечатка, другое
@form_router.message(Form.situation, F.text == "Другое", SubjFilter())
async def process_ask_other(message: Message, state: FSMContext) -> None:
    await state.update_data(typo=False)
    await process_ask(message=message, state=state)


# Неправильный выбор ситуации (не из списка)
@form_router.message(Form.situation, SubjFilter())
async def process_ask_none(message: Message, state: FSMContext) -> None:
    await message.reply("Выберите проблему из списка:", situation_markup)


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

        if data["typo"]:
            problem = "опечатка, {} класс, {} урок".format(
                data["grade"], data["lesson"]
            )
        else:
            problem = "другое"
        text = ("Пользователь: @{}, {}\nПроблема: {}\nТекст: {}").format(
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
