from contest_import import Contest
from database import DataBase
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler
import time
import threading
import random
from sheets import load_to_sheets

threads = []

def sliced(arr=[], cols=1):
    i = 0
    n = len(arr)
    res = []
    while (i < n):
        res.append(arr[i:i+cols])
        i += cols
    return res 

settings = {}

try:
    with open("settings.set", "r") as file:
        text= file.read()
        exec(f"settings = {text}")

except Exception as e:
    print(e, "ASDASDASDASD")

db = DataBase(settings["REGISTRATED_TEAMS_FILE"], settings["CONTEST_ID"])
db.update()
db.save()
db.save_table_to_csv()
load_to_sheets(csv_data="table_budget.csv")


async def identify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Пожалуйста, укажите номер команды, чтобы мы знали, от чьего лица вы делаете ставки."
    tg_id = context._user_id
    db.add_in_reg_queue(tg_id)
    await update.message.reply_text(text)
    
        
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = \
'''*Добро пожаловать на лучшее мероприятие этого лета!*
У вас есть несколько способов делать ставки:

*Рулетка:*
Фиксированная ставка в 10 баллов, вам может выпасть как больше, так и меньше. 
        
*Ставка на задачу:*
Вы ставите выбранное количество баллов на одну из задач, по которой еще не было попыток. Если вы ее сдаете с первого раза, вы получаете свои баллы назад в удвоенном размере. 

*Игра в три наперстка:*
Мы загадываем кладем подарок под одну из кнопок. Если вы угадываете, под какую, вы его получаете. Попытка так же стоит 10 баллов. 

_В любой непонятной ситуации пишите /menu ))_'''
    await update.message.reply_text(text, parse_mode="Markdown")  

async def random_msg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = context._user_id
    msg = update.message.text
    text = ""

    if (db.in_registration_queue(tg_id)):
        if db.registrate(tg_id, msg):
            text = f"Регистрация прошла успешно! Вы теперь участник команды: {db.team_of(tg_id)} !!!\n"
        else:
            text = "Неверный код команды. Попробуй еще или попроси помощи более трезвого товарища."
        await update.message.reply_text(text) 
        return None

    chosen_task = db.task_chosen_for_bet(tg_id)

    if (chosen_task != None):
        if not str.isdecimal(msg):
            await update.message.reply_text("Ставка должна быть целым числом.")
            return None
        bet = int(msg)
        team = db.team_of(tg_id)
        if db.team_obj_by_name(team).make_bet(bet, chosen_task):
            db.bet_has_been_approved(tg_id)
            await update.message.reply_text(f"Ваша команда успешно поставила {bet} баллов на решение задачи {chosen_task} с первого раза")
        else:
            await update.message.reply_text("Нужно больше золота.")
        return None        

    text = "Ты думал тут что-то будет?"
    await update.message.reply_text(text) 
    return None

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_id = context._user_id

    if not db.is_registrated_user(tg_id):
        await identify(update, context)
        return None

    keyboard = [
        [
            InlineKeyboardButton("Ставка на задачу", callback_data="task"),
        ],
        [   
            InlineKeyboardButton("КРУТИТЬ", callback_data="casino"),
            InlineKeyboardButton("Узнать баллы", callback_data="money"),
        ],
        [
            InlineKeyboardButton("Играем в наперстки.", callback_data="naperstki"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Что Вам угодно?", reply_markup=reply_markup)

async def naperstki(tg_id, query):
    team_name = db.team_of(tg_id)
    budget = db.team_obj_by_name(team_name).get_budget()
    if (budget < 10):
        await query.edit_message_text("Нужно больше золота.")
        return 
    
    db.team_obj_by_name(team_name).add_money(-10)
    keyboard_ = [[InlineKeyboardButton("ТЫК", callback_data="nap="+str(i)) for i in range(3)]]
    reply_markup = InlineKeyboardMarkup(keyboard_)
    await query.edit_message_text("Вжух-вжух-вжух\nДа начнется игра!", reply_markup=reply_markup)
    pass 

async def casino(tg_id, query):
    team_name = db.team_of(tg_id)
    budget = db.team_obj_by_name(team_name).get_budget()
    if (budget < 10):
        await query.edit_message_text("Нужно больше золота.")
        return 
    
    res = round(random.random()**1.25 * 20)

    db.team_obj_by_name(team_name).add_money(res - 10)
    if (res < 10):
        res = '0' + str(res)
    else:
        res = str(res)
    await query.edit_message_text(f"Вы выбили ||{res}|| баллов", parse_mode="MarkdownV2")

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE, query):
    tg_id = context._user_id
    team_name = db.team_of(tg_id)
    team_obj = db.team_obj_by_name(team_name)
    free_tasks = team_obj.get_unsolveed_tasks()

    if (len(free_tasks) == 0):
        await query.edit_message_text("По всем задачам уже есть попытки. Попытайте счастье в другом месте!")
        return None 
    
    keyboard = sliced([InlineKeyboardButton(task, callback_data="task="+task) for task in free_tasks], 4)
    reply_markup = InlineKeyboardMarkup(keyboard, )
    await query.edit_message_text("Выберите задачу", reply_markup=reply_markup)
    await query.answer()
    return None


async def money(tg_id):
    team_name = db.team_of(tg_id)
    return f"На данный момент у вашей команды в рапоряжении {db.team_obj_by_name(team_name).get_budget()} баллов."

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery

    tg_id = context._user_id

    await query.answer()
    text = ""

    if (query.data == "casino"):
        await casino(tg_id, query)

    elif (query.data == "task"):
        await task(update, context, query)
    
    elif (query.data == "money"):
        text = await money(tg_id)
        await query.edit_message_text(text=text)
    
    elif (query.data == "naperstki"):
        await naperstki(tg_id, query)

    elif (query.data[:5] == "task="):
        name = query.data[5:]
        text = f"Вы выбрали задачу {name}. Сколько баллов вы хотите на нее поставить?"
        db.user_choosed_task(tg_id, name)
        await query.edit_message_text(text)
    
    elif (query.data[:4] == "nap="):
        prize = random.randint(0, 2)
        naperrst = int(query.data[4:])
        res = ['❌', '❌', '❌']
        res[prize] = "🎁" 
        res = '  '.join(res) + "\n\n"
        if prize == naperrst:
            money_prize = random.randint(20,30)
            team = db.team_of(tg_id)
            db.team_obj_by_name(team).add_money(money_prize)
            res += f"Мда, я проиграл... Держи {money_prize} Баллов." 
        else:
            res += "Программируешь, ты, конечно, лучше... Иди займись чем-нибудь полезным и возварщайся с новыми быллами."
        await query.edit_message_text(res)



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays info on how to use the bot."""
    await update.message.reply_text("Use /start to test this bot.")


def main() -> None:
    application = Application.builder().token(settings["BOT_TOKEN"]).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(None, random_msg))

    # Run the bot until the user presses Ctrl-C
    update_thread = threading.Thread(target=db.parralel_update_sycle)
    update_thread.start()

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
