from mistralai import Mistral
import discord
from discord.ext import commands

import os
import asyncio
import re
import random
from functools import partial
from dotenv import load_dotenv

load_dotenv() 
api_key = os.environ["MISTRAL_API_KEY"]
model = "mistral-large-latest"
client = Mistral(api_key=api_key)
bot_token = os.environ["DISCORD_BOT_TOKEN"]
bot_prefix = '!'  
bot = commands.Bot(command_prefix=bot_prefix, intents=discord.Intents.all())

system_prompt_path = "system_prompt.txt"
emoji_cache = {}
debug = True

target_channel_id = None
message_history_length = 10
bot_name = "бот"
character_prompt = "ты бот"
answer_to_name = True
random_answer_chance = 0

def load_system_prompt(file_path=system_prompt_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Файл {file_path} не найден. Используется системный промпт по умолчанию.")
        return " "
    except Exception as e:
        print(f"Ошибка при чтении файла системного промпта: {e}")
        return " "
    
system_prompt = load_system_prompt()

# Дискорд криво рендерит эмодзи если они отпралены ботом в формате :emoji: , поэтому меняем формат
def replace_emoji_names(text):
    def replace_match(match):
        emoji_name = match.group(1)  
        emoji = emoji_cache.get(emoji_name)
        if emoji:
            return f"<:{emoji.name}:{emoji.id}>"
        return match.group(0)    
    pattern = r'<?:([a-zA-Z0-9_]+):(\d*)>?'
    return re.sub(pattern, replace_match, text)

# Имя пользователя засовывается в контекст из за чего нейросеть тоже пишет свое имя в начале сообщения
def remove_name(text):
    prefix = f"{bot_name.lower()}: "
    if text.lower().startswith(prefix):
        return text[len(prefix):]
    return text

@bot.command(name='время')
async def set_channel(ctx):
    await ctx.send(f"Дима долбаёб")

@bot.command(name='закрепить')
async def set_channel(ctx):
    """Закрепляет бота в текущем канале"""
    global target_channel_id
    target_channel_id = ctx.channel.id
    await ctx.send(f"Бот закреплен в этом канале (ID: {target_channel_id})")

@bot.command(name='инфа')
async def get_info(ctx):
    """Выводит переменные бота"""
    print(f"Сообщений контекста: {message_history_length}")
    print(f"Имя: {bot_name}")
    print(f"Персонаж: {character_prompt}")
    print(f"Системный промпт: {system_prompt}")
    print(f"Отвечать на имя: {answer_to_name}")
    print(f"Шанс случайного ответа: {random_answer_chance}")
    await ctx.send(f"Сообщений контекста: {message_history_length}")
    await ctx.send(f"Имя: {bot_name}")       
    await ctx.send(f"Персонаж: {character_prompt}")   
    await ctx.send(f"Системный промпт: {system_prompt}")
    await ctx.send(f"Отвечать на имя: {answer_to_name}")
    await ctx.send(f"Шанс случайного ответа: {random_answer_chance}")

@bot.command(name='история')
async def set_history_length(ctx, length: int):
    """Устанавливает количество сообщений в истории (1-20)"""
    global message_history_length
    if 1 <= length <= 20:
        message_history_length = length
        await ctx.send(f"Теперь я учитываю {length} предыдущих сообщений при ответе")
    else:
        await ctx.send("Пожалуйста, укажите число от 1 до 20")

@bot.command(name='имя')
@commands.has_permissions(manage_nicknames=True) 
async def change_nickname(ctx, *, new_nickname: str):
    """Изменяет никнейм бота на сервере"""
    global bot_name
    try:
        # Проверяем длину никнейма (от 1 до 32 символов)
        if len(new_nickname) < 1 or len(new_nickname) > 32:
            await ctx.send("Никнейм должен быть от 1 до 32 символов")
            return
        
        # Меняем никнейм бота на сервере
        await ctx.guild.me.edit(nick=new_nickname)
        bot_name = new_nickname
        
        await ctx.send(f"Моё новое имя на этом сервере: {new_nickname}")
    except discord.Forbidden:
        await ctx.send("У меня нет прав на изменение никнейма!")
    except Exception as e:
        print(f"Ошибка при изменении никнейма: {e}")
        await ctx.send("Произошла ошибка при изменении имени")

@bot.command(name='персонаж')
async def change_character(ctx, *, input_text: str):
    """Изменяет персонажа бота. Формат: имя_персонажа; описание_персонажа"""
    global character_prompt
    
    try:
        if ';' not in input_text:
            await ctx.send("Ошибка: используйте формат `имя_персонажа; описание_персонажа`")
            return
            
        name_part, prompt_part = input_text.split(';', 1)
        new_name = name_part.strip()
        new_prompt = prompt_part.strip()
        
        if not new_name or not new_prompt:
            await ctx.send("Ошибка: обе части (имя и описание) должны быть заполнены")
            return
            
        await ctx.invoke(bot.get_command('имя'), new_nickname=new_name)
        
        character_prompt = new_prompt
        await ctx.send(f"Следую указаниям: {new_prompt}")
            
    except Exception as e:
        print(f"Ошибка при изменении персонажа: {e}")
        await ctx.send("Произошла ошибка при изменении персонажа. Пожалуйста, используйте формат: `имя_персонажа; описание_персонажа`")

@bot.command(name='сохранить')
async def save_personality(ctx):
    """Сохраняет личность в системе бота"""
    if not os.path.exists('characters'):
        os.makedirs('characters')
    filepath = os.path.join('characters', f"{bot_name}.txt")
    
    if os.path.exists(filepath):
        print(f"Файл {filepath} уже существует и будет перезаписан.")
        await ctx.send(f"Файл {filepath} уже существует и будет перезаписан.")

    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            file.write(character_prompt)
        print(f"Личность успешно сохранена в файл {filepath}")
        await ctx.send(f"Личность успешно сохранена в файл")
    except Exception as e:
        print(f"Произошла ошибка при сохранении: {e}")
        await ctx.send(f"Произошла ошибка при сохранении: {e}")

@bot.command(name='загрузить')
async def load_personality(ctx, personality_name: str):
    """Загружает личность из сохраненных файлов в папке characters"""
    personality_name = personality_name.replace('.txt', '')
    filepath = os.path.join('characters', f"{personality_name}.txt")
    
    if not os.path.exists(filepath):
        error_msg = f"Файл личности '{personality_name}' не найден!"
        print(error_msg)
        await ctx.send(error_msg)
        return

    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            global character_prompt
            character_prompt = file.read()
            global bot_name
            bot_name = personality_name
            await ctx.guild.me.edit(nick=bot_name)
            
        success_msg = f"Личность '{personality_name}' успешно загружена!"
        print(success_msg)
        await ctx.send(success_msg)
        
    except Exception as e:
        error_msg = f"Ошибка при загрузке личности: {str(e)}"
        print(error_msg)
        await ctx.send(error_msg)

@bot.command(name='список')
async def list_personalities(ctx):
    """Выводит список всех доступных личностей"""
    if not os.path.exists('characters'):
        await ctx.send("Папка с личностями не существует или пуста!")
        return
    
    files = [f.replace('.txt', '') for f in os.listdir('characters') if f.endswith('.txt')]
    
    if not files:
        await ctx.send("Нет сохраненных личностей!")
        return
    
    message = "Доступные личности:\n" + "\n".join(files)
    await ctx.send(message)

@bot.command(name='удалить')
async def delete_personality(ctx, personality_name: str):
    """Удаляет указанную личность"""
    personality_name = personality_name.replace('.txt', '')
    filepath = os.path.join('characters', f"{personality_name}.txt")
    
    if not os.path.exists(filepath):
        await ctx.send(f"Личность '{personality_name}' не найдена!")
        return
    
    try:
        os.remove(filepath)
        await ctx.send(f"Личность '{personality_name}' успешно удалена!")
    except Exception as e:
        await ctx.send(f"Ошибка при удалении: {str(e)}")

@bot.command(name='ответИмя')
async def toggle_answer(ctx):
    """Переключает ответы на имя (вкл/выкл)"""
    global answer_to_name
    answer_to_name = not answer_to_name
    status = "включены" if answer_to_name else "выключены"
    await ctx.send(f"Ответы на имя теперь {status}!")

@bot.command(name='ответШанс')
async def set_chance(ctx, chance: float):
    """Устанавливает шанс случайного ответа (от 0.0 до 1.0)"""
    global random_answer_chance
    if 0 <= chance <= 1:
        random_answer_chance = chance
        await ctx.send(f"Шанс случайного ответа установлен на {chance * 100}%!")
    else:
        await ctx.send("Ошибка: шанс должен быть между 0.0 и 1.0!")

@bot.command(name='помощь')
async def help(ctx):
    """Отображает список всех доступных команд"""
    
    await ctx.send(f'''{bot_prefix}помощь - Показывает это сообщение
{bot_prefix}инфа - Показывает текущие настройки бота
{bot_prefix}закрепить - Закрепляет бота в текущем канале
{bot_prefix}история [1-20] - Устанавливает глубину истории сообщений
{bot_prefix}ответИмя - Вкл/выкл ответы на упоминание имени
{bot_prefix}ответШанс [0.0-1.0] - Устанавливает шанс случайного ответа''')
    
    await ctx.send(f'''{bot_prefix}имя [новое_имя] - Меняет имя персонажа, на которое бот будет откликаться
{bot_prefix}персонаж [имя;описание] - Меняет имя и описание персонажа
Пример: `!персонаж Eвангелина; Ты - депресивная поэтесса`
{bot_prefix}сохранить - Сохраняет текущую личность в системе бота 
{bot_prefix}загрузить [имя] - Загружает личность из сохранённого файла  
{bot_prefix}список - Показывает все созранённые личности
{bot_prefix}удалить [имя] - Удаляет сохранённую личность ''')

# Функция для запроса к Mistral AI
async def get_mistral_response(channel, user_message):
    loop = asyncio.get_event_loop()
    
    # Получаем историю сообщений
    messages_history = []
    async for msg in channel.history(limit=message_history_length + 1):
        if msg.id == user_message.id:  # Пропускаем текущее сообщение
            continue
        if msg.content.startswith(bot_prefix):
            continue
        if msg.author == bot.user:
            messages_history.insert(0, {"role": "assistant", "content": f"{msg.content}"})
        else:
            messages_history.insert(0, {"role": "user", "content": f"{msg.author.display_name}: {msg.content}"})
    
    messages = [{"role": "system", "content": system_prompt + character_prompt}]
    messages.extend(messages_history)
    messages.append({"role": "user", "content": f"{user_message.author.display_name}: {user_message.content}"})
    if debug:
        print(messages)

    try:
        # Запускаем синхронный запрос в отдельном потоке
        response = await loop.run_in_executor(
            None,
            partial(
                client.chat.complete,
                model=model,
                messages=messages
            )
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Ошибка при обращении к Mistral API: {e}")
        return None

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    if target_channel_id is not None and message.channel.id != target_channel_id:
        return
    await message.guild.me.edit(nick=bot_name)
    
    answer = False
    current_name = bot_name #message.guild.me.display_name if message.guild else bot.user.name
    if ((current_name.lower() in message.content.lower() or 
        bot.user.mention in message.content) and answer_to_name):
        answer = True
    if random.random() < random_answer_chance:
        answer = True

    if answer:
        try:
            response = await get_mistral_response(message.channel, message)
            if debug:
                print("\n" + response)
            if response:
                response = remove_name(response)
                response = replace_emoji_names(response)
                await message.channel.send(response)
            else:
                await message.channel.send("Извините, возникла ошибка при обработке запроса")
        except Exception as e:
            print(f"Ошибка при обработке сообщения: {e}")
            await message.channel.send("Извините, произошла внутренняя ошибка")
    
    await bot.process_commands(message)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        for emoji in guild.emojis:
            emoji_cache[emoji.name] = emoji
    print(f'Бот {bot_name} успешно запущен!')
    print('------')

if __name__ == '__main__':
    bot.run(bot_token)