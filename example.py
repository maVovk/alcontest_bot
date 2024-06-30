#!/usr/bin/env python
# pylint: disable=unused-argument
# This program is dedicated to the public domain under the CC0 license.

"""Simple inline keyboard bot with multiple CallbackQueryHandlers.

This Bot uses the Application class to handle the bot.
First, a few callback functions are defined as callback query handler. Then, those functions are
passed to the Application and registered at their respective places.
Then, the bot is started and runs until we press Ctrl-C on the command line.
Usage:
Example of a bot that uses inline keyboard that has multiple CallbackQueryHandlers arranged in a
ConversationHandler.
Send /start to initiate the conversation.
Press Ctrl-C on the command line to stop the bot.
"""


import json
import logging
import threading
import random

from contest_import import Contest
from database import DataBase
from sheets import load_to_sheets
import replies

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.FileHandler('bot.log', 'a+', 'utf-8')
handler.setFormatter(logging.Formatter("%(asctime)s: %(message)s", "%H:%M:%S"))
logger.addHandler(handler)

START_ROUTES, MIDDLE_ROUTES, END_ROUTES = range(3)
MENU, SHELL, CASINO, BET, CHECK, SHELL_RESULT, CASINO_RESULT, BET_RESULT, HELP, MAKE_BET = range(10)

threads = []

def sliced(arr, cols=1):
    result = []

    for i in range(0, len(arr), cols):
        result.append(arr[i:i + cols])
    
    return result 

settings = {}

try:
    with open("settings.json", "r", encoding='utf-8') as file:
        settings = json.loads(file.read())
        print(settings)
except Exception as e:
    print(e, "Проблема при чтении настроек")

logger.info(f'Инициализируем БД c настройками: {settings}')
db = DataBase(settings["REGISTRATED_TEAMS_FILE"], settings["CONTEST_ID"])
db.update()
db.save()
db.save_table_to_csv()
load_to_sheets(csv_data="table_budget.csv")
logger.info('Инициализация БД закончена')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.message.from_user
    logger.info(f"{user.name} начал регистрацию.")

    tg_id = context._user_id
    db.add_in_reg_queue(tg_id)

    await update.message.reply_text(replies.greeting_message, parse_mode='Markdown')

    return START_ROUTES


async def registration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    tg_id = context._user_id
    message = update.message.text
    reply_text = ''

    if db.in_registration_queue(tg_id):
        if db.registrate(tg_id, message):
            reply_text = replies.succesfull_registration.format(db.team_of(tg_id))
            logger.info(f'{update.message.from_user} зарегалася в тиму {db.team_of(tg_id)}')

            keyboard = [
                [
                    InlineKeyboardButton("Ставка на задачу", callback_data=str(BET)),
                ],
                [
                    InlineKeyboardButton("Рулетка", callback_data=str(CASINO)),
                    InlineKeyboardButton("Напёрстки", callback_data=str(SHELL)),
                ],
                [
                    InlineKeyboardButton("Баланс", callback_data=str(CHECK)),
                    InlineKeyboardButton("Правила", callback_data=str(HELP)),
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(reply_text, reply_markup=reply_markup, parse_mode='Markdown')

            return MIDDLE_ROUTES
        else:
            text = replies.unsuccessfull_registration

            await update.message.reply_text(text, parse_mode='Markdown') 
            return START_ROUTES

    reply_text = replies.unknown_command
    keyboard = [
        [
            InlineKeyboardButton("Меню", callback_data=str(MENU)),
        ],
        [
            InlineKeyboardButton("Список развлечений", callback_data=str(HELP)),
        ]
    ]
            
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        reply_text, reply_markup=reply_markup, parse_mode='Markdown'
    )

    return MIDDLE_ROUTES


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("Ставка на задачу", callback_data=str(BET)),
        ],
        [
            InlineKeyboardButton("Рулетка", callback_data=str(CASINO)),
            InlineKeyboardButton("Напёрстки", callback_data=str(SHELL)),
        ],
        [
            InlineKeyboardButton("Баланс", callback_data=str(CHECK)),
            InlineKeyboardButton("Правила", callback_data=str(HELP)),
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    reply_text = replies.menu_text
    await query.edit_message_text(
        text=reply_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
        )

    return MIDDLE_ROUTES


async def bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tg_id = context._user_id
    team_name = db.team_of(tg_id)
    team_obj = db.team_obj_by_name(team_name)
    free_tasks = team_obj.get_unsolveed_tasks()

    if (len(free_tasks) == 0):
        keyboard = [
            [
                InlineKeyboardButton("В меню", callback_data=str(MENU)),
            ]
        ]

        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            replies.all_tasks_tried,
            reply_markup=reply_markup
            )
        return MIDDLE_ROUTES

    keyboard = sliced([InlineKeyboardButton(task, callback_data=f"task={task}") for task in free_tasks], 4)
    keyboard.append([InlineKeyboardButton("Назад", callback_data=str(MENU))])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text='Выбирай задачу, на которую поставишь',
        reply_markup=reply_markup
    )

    return MIDDLE_ROUTES


async def make_bet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tg_id = context._user_id
    task_name = query.data.split('=')[1]

    keyboard = [
        [
            InlineKeyboardButton("Назад", callback_data=str(MENU))
        ]
    ]

    # print(key)/

    db.user_choosed_task(tg_id, task_name)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=replies.set_task_bet.format(task_name),
        reply_markup=reply_markup
    )

    return END_ROUTES


async def bet_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message.text

    if not str.isdecimal(message):
        await update.message.reply_text(
            replies.task_bet_int_error
            )
        return END_ROUTES
    
    bet = int(message)
    tg_id = context._user_id

    team = db.team_of(tg_id)
    chosen_task = db.task_chosen_for_bet(tg_id)

    keyboard = [
        [
            InlineKeyboardButton("В меню", callback_data=str(MENU)),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if db.team_obj_by_name(team).make_bet(bet, chosen_task):
        db.bet_has_been_approved(tg_id)

        logger.info(f"{db.team_of(tg_id)} поставила {bet} на решение задачи {chosen_task}")

        await update.message.reply_text(
            replies.task_bet_success.format(bet, chosen_task),
            reply_markup=reply_markup
        )
    else:
        logger.info(f"У {db.team_of(tg_id)} не хватило на {bet}, задача {chosen_task}")

        await update.message.reply_text(
            replies.task_bet_not_enough_money,
            reply_markup=reply_markup
        )
    
    return MIDDLE_ROUTES


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tg_id = context._user_id
    team_name = db.team_of(tg_id)

    keyboard = [
        [
            InlineKeyboardButton("Слить всё до копейки", callback_data=str(MENU)),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=f'На балансе: {db.team_obj_by_name(team_name).get_budget()}',
        reply_markup=reply_markup
    )

    return MIDDLE_ROUTES


async def casino(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tg_id = context._user_id
    team_name = db.team_of(tg_id)
    budget = db.team_obj_by_name(team_name).get_budget()

    if budget < 10:
        keyboard = [InlineKeyboardButton("В меню", callback_data=str(MENU))]

        await query.edit_message_text(
            replies.task_bet_not_enough_money,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return MIDDLE_ROUTES

    keyboard = [
        [
            InlineKeyboardButton("КРУТИТЬ КРУТИТЬ КРУТИТЬ", callback_data=str(CASINO_RESULT)),
        ],
        [
            InlineKeyboardButton("В меню", callback_data=str(MENU)),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text='Испытаешь удачу?',
        reply_markup=reply_markup
    )

    return END_ROUTES


async def casino_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [
            InlineKeyboardButton("ХОЧУ ЕЩЁ", callback_data=str(CASINO)),
        ],
        [
            InlineKeyboardButton("В меню", callback_data=str(MENU)),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    tg_id = context._user_id
    team_name = db.team_of(tg_id)

    res = int(round(random.random() ** 1.25 * 20))
    logger.info(f'{db.team_obj_by_name(team_name)} играет в казино в выбивает {res}')

    db.team_obj_by_name(team_name).add_money(res - 10)
    if (res < 10):
        res = ' ' + str(res)
    else:
        res = str(res)

    await query.edit_message_text(
        text=replies.casino_result.format(res),
        reply_markup=reply_markup,
        parse_mode='MarkdownV2'
    )

    return MIDDLE_ROUTES


async def shell(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tg_id = context._user_id
    team_name = db.team_of(tg_id)
    budget = db.team_obj_by_name(team_name).get_budget()

    if budget < 10:
        keyboard = [InlineKeyboardButton("В меню", callback_data=str(MENU))]

        await query.edit_message_text(
            replies.task_bet_not_enough_money,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return MIDDLE_ROUTES

    keyboard = [
        [
            InlineKeyboardButton("ТЫК", callback_data="nap="+str(i)) for i in range(3)
        ],
        [
            InlineKeyboardButton("В меню", callback_data=str(MENU)),
        ]
    ]

    logger.info(f'{db.team_obj_by_name(team_name)} играет в напёрстки')
    db.team_obj_by_name(team_name).add_money(-10)

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=replies.shell_start,
        reply_markup=reply_markup
    )

    return END_ROUTES

async def shell_result(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    tg_id = context._user_id
    prize = random.randint(0, 2)
    res = ['❌', '❌', '❌']
    res[prize] = "🎁" 
    tapped_shell = int(query.data.split('=')[1])
    reply_text = None

    if tapped_shell == prize:
        money_prize = random.randint(20,30)
        team = db.team_of(tg_id)
        db.team_obj_by_name(team).add_money(money_prize)
        
        reply_text = replies.shell_win.format('  '.join(res), money_prize)

        logger.info(f'{db.team_obj_by_name(team)} выигрывает {money_prize} в напёрстках')
    else:
        reply_text = replies.shell_loss.format('  '.join(res))
    
    keyboard = [
        [
            InlineKeyboardButton("Сыграть ещё раз", callback_data=str(SHELL)),
        ],
        [
            InlineKeyboardButton("В меню", callback_data=str(MENU)),
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        text=reply_text,
        reply_markup=reply_markup
    )

    return MIDDLE_ROUTES


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [
            InlineKeyboardButton("Меню", callback_data=str(MENU)),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await update.message.reply_text(
            text=replies.help_command,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception as e:
        query = update.callback_query
        await query.answer()

        await query.edit_message_text(
            text=replies.help_command,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    return MIDDLE_ROUTES


async def error_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("ААААА ТЫ ВСЁ СЛОМАЛ НАПИШИ \n /menu ")
    return START_ROUTES


def main() -> None:
    application = Application.builder().token(settings['BOT_TOKEN']).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start)
  #          CommandHandler("admin-start", )
   #         CommandHandler("admin-load-db", )
    #        CommandHandler("admin-end", )    
            ],
        states={
            START_ROUTES: [
                MessageHandler(None, registration),
                CommandHandler("menu", menu),
                CallbackQueryHandler(help, pattern="^" + str(HELP) + "$"),
            ],
            MIDDLE_ROUTES: [
                CallbackQueryHandler(menu, pattern="^" + str(MENU) + "$"),
                CallbackQueryHandler(bet, pattern="^" + str(BET) + "$"),
                CallbackQueryHandler(make_bet, pattern="^task=[a-zA-Z]+$"),
                CallbackQueryHandler(casino, pattern="^" + str(CASINO) + "$"),
                CallbackQueryHandler(check, pattern="^" + str(CHECK) + "$"),
                CallbackQueryHandler(shell, pattern="^" + str(SHELL) + "$"),
                CallbackQueryHandler(help, pattern="^" + str(HELP) + "$"),
            ],
            END_ROUTES: [
                MessageHandler(None, bet_result),
                CallbackQueryHandler(menu, pattern="^" + str(MENU) + "$"),
                CallbackQueryHandler(casino_result, pattern="^" + str(CASINO_RESULT) + "$"),
                CallbackQueryHandler(shell_result, pattern="^nap=(\d)+$"),
                CallbackQueryHandler(help, pattern="^" + str(HELP) + "$"),
            ]
        },
        fallbacks=[
            CommandHandler("help", help),
            MessageHandler(None, error_message)
        ],
    )

    # Add ConversationHandler to application that will be used for handling updates
    application.add_handler(conv_handler)

    update_thread = threading.Thread(target=db.parralel_update_sycle)
    update_thread.start()

    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()