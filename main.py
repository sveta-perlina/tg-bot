import os
import json
import re
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import telebot
from telebot import types
from telebot.handler_backends import StatesGroup, State
from telebot.storage import StateMemoryStorage

TOKEN = "7245388868:AAHZ6T99DqkYH-cI1k22WDzoHT6Fyx_tcLQ"
CACHE_DIR = "data"
os.makedirs(CACHE_DIR, exist_ok=True)

class BotStates(StatesGroup):
    waiting_for_program = State()
    waiting_for_background = State()
    waiting_for_question = State()

state_storage = StateMemoryStorage()
bot = telebot.TeleBot(TOKEN, state_storage=state_storage)

PROGRAMS = {
    "ai": {
        "url": "https://abit.itmo.ru/program/master/ai",
        "name": "Магистратура 'Искусственный интеллект' (AI)"
    },
    "ai_product": {
        "url": "https://abit.itmo.ru/program/master/ai_product",
        "name": "Магистратура 'AI-продукты' (AI Product)"
    }
}

def parse_program(program_id: str) -> Dict:
    cache_file = os.path.join(CACHE_DIR, f"{program_id}.json")
    
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    
    url = PROGRAMS[program_id]["url"]
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    disciplines = []
    for semester in soup.find_all("div", class_="semester"):
        semester_num = semester.find("h3").text.strip()
        
        for disc in semester.find_all("div", class_="discipline"):
            name = disc.find("div", class_="name").text.strip()
            disc_type = disc.find("div", class_="type").text.strip()
            credits = disc.find("div", class_="credits").text.strip()
            
            disciplines.append({
                "name": name,
                "type": disc_type,
                "semester": semester_num,
                "credits": credits
            })
    
    program_data = {
        "name": PROGRAMS[program_id]["name"],
        "url": url,
        "disciplines": disciplines
    }
    
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(program_data, f, ensure_ascii=False, indent=2)
    
    return program_data

def get_recommendations(program_id: str, background: str) -> List[str]:
    program = parse_program(program_id)
    elective_courses = [d for d in program["disciplines"] if "выбор" in d["type"].lower()]
    
    background = background.lower()
    recommendations = []
    
    if program_id == "ai":
        if "математик" in background or "статистик" in background:
            recommendations.extend([
                "Продвинутые методы машинного обучения",
                "Теория вероятностей и математическая статистика"
            ])
        if "программист" in background or "разработчик" in background:
            recommendations.extend([
                "Глубокое обучение с подкреплением",
                "Обработка естественного языка"
            ])
    
    elif program_id == "ai_product":
        if "менедж" in background or "управл" in background:
            recommendations.extend([
                "Управление AI-продуктами",
                "Бизнес-аналитика для AI"
            ])
        if "дизайн" in background or "ux" in background:
            recommendations.extend([
                "Дизайн AI-интерфейсов",
                "UX-исследования для AI-продуктов"
            ])
    
    recommendations = list(set(recommendations))
    
    if not recommendations:
        popular = [d["name"] for d in elective_courses[:3]]
        return [
            "На основе вашего бэкграунда сложно дать точные рекомендации.",
            "Можем предложить следующие популярные курсы:",
            *popular
        ]
    
    return recommendations

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, 
        "Привет! Я помогу тебе выбрать магистерскую программу в ITMO и спланировать обучение.\n"
        "Доступные программы:\n"
        "1. Искусственный интеллект (AI)\n"
        "2. AI-продукты (AI Product)\n\n"
        "Выбери программу или задай вопрос о них."
    )
    bot.set_state(message.from_user.id, BotStates.waiting_for_program, message.chat.id)


@bot.message_handler(content_types='text', state=BotStates.waiting_for_program)
def handle_program_choice(message):
    text = message.text.lower()
    print(text)
    
    if "1" in text or ("ai" in text and "product" not in text) or "интеллект" in text:
        program_id = "ai"
    elif "2" in text or "product" in text or "продукт" in text:
        program_id = "ai_product"
    else:
        bot.reply_to(message, 
            "Пожалуйста, выбери программу:\n"
            "1 - Искусственный интеллект (AI)\n"
            "2 - AI-продукты (AI Product)\n\n"
            "Можно ввести номер или название программы"
        )
        return
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        data["program_id"] = program_id
    
    bot.reply_to(message,
        f"Ты выбрал программу: {PROGRAMS[program_id]['name']}\n"
        "Расскажи немного о своем бэкграунде (образование, опыт работы, интересы), "
        "чтобы я мог дать рекомендации по выбору дисциплин."
    )
    bot.set_state(message.from_user.id, BotStates.waiting_for_background, message.chat.id)

@bot.message_handler(content_types='text', state=BotStates.waiting_for_background)
def handle_background(message):
    background = message.text
    
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        program_id = data["program_id"]
    
    recommendations = get_recommendations(program_id, background)
    
    response = [
        f"Спасибо за информацию! Вот рекомендации для программы {PROGRAMS[program_id]['name']}:",
        *recommendations,
        "\nТеперь ты можешь задавать вопросы об учебном плане или ввести /restart для выбора другой программы."
    ]
    
    bot.reply_to(message, "\n".join(response))
    bot.set_state(message.from_user.id, BotStates.waiting_for_question, message.chat.id)

@bot.message_handler(content_types='text', state=BotStates.waiting_for_question)
def handle_questions(message):
    text = message.text.lower()
    with bot.retrieve_data(message.from_user.id, message.chat.id) as data:
        program_id = data.get("program_id", "")
    
    if not program_id:
        bot.reply_to(message, "Пожалуйста, сначала выбери программу.")
        bot.set_state(message.from_user.id, BotStates.waiting_for_program, message.chat.id)
        return
    
    if "перезапуск" in text or "/restart" in text:
        send_welcome(message)
        return
    
    program_data = parse_program(program_id)
    
    if any(w in text for w in ["обязательные", "обязательн", "базовые"]):
        mandatory = [d["name"] for d in program_data["disciplines"] if "обяз" in d["type"].lower()]
        response = "Обязательные дисциплины:\n" + "\n".join(mandatory)
    elif any(w in text for w in ["выборные", "по выбору", "электив"]):
        elective = [d["name"] for d in program_data["disciplines"] if "выбор" in d["type"].lower()]
        response = "Дисциплины по выбору:\n" + "\n".join(elective)
    elif any(w in text for w in ["семестр", "график", "расписание"]):
        semesters = {}
        for d in program_data["disciplines"]:
            semesters.setdefault(d["semester"], []).append(d["name"])
        response = "Дисциплины по семестрам:\n"
        for sem, discs in semesters.items():
            response += f"\n{sem}:\n" + "\n".join(f"  - {d}" for d in discs)
    elif any(w in text for w in ["что такое", "расскажи о", "информация о"]):
        disc_name = None
        for d in program_data["disciplines"]:
            if d["name"].lower() in text:
                disc_name = d["name"]
                break
        
        if disc_name:
            response = f"Информация о дисциплине '{disc_name}':\n(Здесь должна быть подробная информация с сайта)"
        else:
            response = "Не могу найти такую дисциплину в учебном плане."
    else:
        response = (
            "Я могу ответить на вопросы об обязательных и выборных дисциплинах, "
            "учебном плане по семестрам или рассказать о конкретной дисциплине. "
            "Попробуй задать вопрос более конкретно."
        )
    
    bot.reply_to(message, response)

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()

