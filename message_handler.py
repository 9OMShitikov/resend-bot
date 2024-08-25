import asyncio
import logging
from typing import Any, Dict

from aiogram import F, Router, html
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


class SubjFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        return message.chat.id not in config.config.subjects.values()


class Form(StatesGroup):
    subject = State()
    situation = State()
    where_grade = State()
    where_lesson = State()
    what = State()


subj_markup = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=subj),
        ]
        for subj in config.config.subjects
    ],
    resize_keyboard=True,
)


situation_markup = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text=theme),
        ]
        for theme in situations
    ],
    resize_keyboard=True,
)


grade_markup = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=str(i)) for i in [7, 8, 10, 11]]],
    resize_keyboard=True,
)

start_markup = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="start"),
        ]
    ],
    resize_keyboard=True,
)


@form_router.message(CommandStart(), SubjFilter())
@form_router.message(Command("start"), SubjFilter())
@form_router.message(F.text.casefold() == "start", SubjFilter())
async def command_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Form.subject)
    await state.update_data(lock=asyncio.Lock())
    await message.answer("Какой предмет вас интересует?", reply_markup=subj_markup)


@form_router.message(Form.subject, SubjFilter())
async def process_subject(message: Message, state: FSMContext) -> None:
    subj = message.text
    if subj in config.config.subjects:
        await state.update_data(subject=subj)
        await state.set_state(Form.situation)
        await message.answer("Какая возникла проблема?", reply_markup=situation_markup)
    else:
        await message.reply("Предмет не из списка:", reply_markup=subj_markup)


@form_router.message(Form.situation, F.text == "Была найдена опечатка", SubjFilter())
async def process_typo(message: Message, state: FSMContext) -> None:
    await state.update_data(typo=True)
    await state.set_state(Form.where_grade)
    await message.answer("Какой класс (номер)?", reply_markup=grade_markup)


@form_router.message(Form.where_grade, F.text.isdigit(), SubjFilter())
async def process_typo_grade(message: Message, state: FSMContext) -> None:
    await state.update_data(grade=int(message.text))
    await state.set_state(Form.where_lesson)
    await message.answer("Какой урок (номер)?", reply_markup=ReplyKeyboardRemove())


@form_router.message(Form.where_lesson, F.text.isdigit(), SubjFilter())
async def process_typo_lesson(message: Message, state: FSMContext) -> None:
    await state.update_data(lesson=int(message.text))
    await process_ask(message=message, state=state)


@form_router.message(Form.where_grade, SubjFilter())
async def process_typo_error(message: Message, state: FSMContext) -> None:
    await message.reply("Введите номер класса:", reply_markup=grade_markup)


@form_router.message(Form.where_lesson, SubjFilter())
async def process_typo_error(message: Message, state: FSMContext) -> None:
    await message.reply("Введите номер", reply_markup=ReplyKeyboardRemove())


@form_router.message(Form.situation, F.text == "Другое", SubjFilter())
async def process_ask_other(message: Message, state: FSMContext) -> None:
    await state.update_data(typo=False)
    await process_ask(message=message, state=state)


@form_router.message(Form.situation, SubjFilter())
async def process_ask_none(message: Message, state: FSMContext) -> None:
    await message.reply("Выберите проблему из списка:", situation_markup)


async def process_ask(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.what)
    await message.answer(
        "Опишите проблему, приложите фотографию, если нужно:",
        reply_markup=ReplyKeyboardRemove(),
    )


@form_router.message(Form.what)
async def process_done(message: Message, state: FSMContext) -> None:
    photo = message.photo[-1] if message.photo else None
    text = message.text
    if text is None:
        text = message.caption

    data = await state.get_data()
    l: asyncio.Lock = data["lock"]
    await l.acquire()
    locked_data = await state.get_data()
    if not text:
        text = locked_data.get("text")
    lock_photos: list[str] = locked_data.get("photos", [])
    if photo:
        lock_photos.append(photo.file_id)
    await state.update_data(photos=lock_photos, text=text)
    l.release()

    if "photos" not in locked_data:
        await asyncio.sleep(config.config.latency)

        data = await state.get_data()
        photos = set(data["photos"])
        text = data["text"]

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
            await message.bot.send_media_group(
                chat_id=config.config.subjects[data["subject"]],
                media=[
                    InputMediaPhoto(media=id, caption=text if i == 0 else None)
                    for (i, id) in enumerate(photos)
                ],
            )
        else:
            await message.bot.send_message(
                chat_id=config.config.subjects[data["subject"]],
                text=text,
            )
        await state.clear()
        await message.answer(
            "Принято",
            reply_markup=start_markup,
        )
