import os
import asyncio
import re
import random
from functools import partial
from dotenv import load_dotenv
load_dotenv() 

from mistralai import Mistral

import discord
from discord.ext import commands

api_key = os.environ["MISTRAL_API_KEY"]
model = "mistral-large-latest"
client = Mistral(api_key=api_key)

bot_token = os.environ["DISCORD_BOT_TOKEN"]
bot_prefix = '!'  
bot = commands.Bot(command_prefix=bot_prefix, intents=discord.Intents.all())

system_prompt_path = "system_prompt.txt"

target_channel_id = None
message_history_length = 10
bot_name = "бот"
character_prompt = "ты бот"
emoji_cache = {}
debug = True
answer_to_name = True
random_answer_chance = 0

# Загрузка системного промпта из файла
def load_system_prompt(file_path=system_prompt_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        print(f"Файл {file_path} не найден. Используется промпт по умолчанию.")
        return " "
    except Exception as e:
        print(f"Ошибка при чтении файла промпта: {e}")
        return " "

system_prompt = load_system_prompt()

def replace_emoji_names(text):
    def replace_match(match):
        emoji_name = match.group(1)  # Имя эмодзи без двоеточий
        emoji = emoji_cache.get(emoji_name)
        if emoji:
            return f"<:{emoji.name}:{emoji.id}>"
        return match.group(0)  # Если эмодзи не найден, оставляем как было
    
    pattern = r'(?<!<):([a-zA-Z0-9_]+):(?!\d+>)'
    return re.sub(pattern, replace_match, text)

def remove_name(text):
    prefix = f"{bot_name}: "
    if text.startswith(prefix):
        return text[len(prefix):]
    return text

# Асинхронная функция для запроса к Mistral AI
async def get_mistral_response(channel, user_message):
    loop = asyncio.get_event_loop()
    
    # Получаем историю сообщений
    messages_history = []
    async for msg in channel.history(limit=message_history_length + 1):
        if msg.id == user_message.id:  # Пропускаем текущее сообщение
            continue
        if msg.content.startswith(bot_prefix):
            continue
        role = "assistant" if msg.author == bot.user else "user"
        messages_history.insert(0, {"role": role, "content": f"{msg.author.display_name}: {msg.content}"})
    
    # Формируем полный контекст
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
    await ctx.send(f"Сообщений контекста: {message_history_length}")
    await ctx.send(f"Имя: {bot_name}")       
    await ctx.send(f"Персонаж: {character_prompt}")   
    await ctx.send(f"Системный промпт: {system_prompt}")

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
@commands.has_permissions(manage_nicknames=True)  # Только для пользователей с правами управления никнеймами
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

@bot.command(name='ОтветИмя')
async def toggle_answer(ctx):
    """Переключает ответы на имя (вкл/выкл)"""
    global answer_to_name
    answer_to_name = not answer_to_name
    status = "включены" if answer_to_name else "выключены"
    await ctx.send(f"Ответы на имя теперь {status}!")

@bot.command(name='ОтветШанс')
async def set_chance(ctx, chance: float):
    """Устанавливает шанс случайного ответа (от 0.0 до 1.0)"""
    global random_answer_chance
    if 0 <= chance <= 1:
        random_answer_chance = chance
        await ctx.send(f"Шанс случайного ответа установлен на {chance * 100}%!")
    else:
        await ctx.send("Ошибка: шанс должен быть между 0.0 и 1.0!")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if target_channel_id is not None and message.channel.id != target_channel_id:
        return
    
    answer = False
    if (bot_name in message.content.lower()) and answer_to_name:
        answer = True

    if random.random() < random_answer_chance:
        answer = True

    if answer:
        try:
            response = await get_mistral_response(message.channel, message)
            if debug:
                print("\n" + response)
            if response:
                response = replace_emoji_names(response)
                response = remove_name(response)
                await message.channel.send(response)
            else:
                await message.channel.send("Извините, возникла ошибка при обработке запроса")
        except Exception as e:
            print(f"Ошибка при обработке сообщения: {e}")
            await message.channel.send("Извините, произошла внутренняя ошибка")
    
    await bot.process_commands(message)

@bot.command(name='помощь')
async def help(ctx):
    """Отображает список всех доступных команд"""
    help_embed = discord.Embed(
        title=f"Список команд бота {bot_name}",
        description="Вот все команды, которые вы можете использовать:",
        color=discord.Color.blue()
    )
    
    help_embed.add_field(
        name="Основные команды",
        value=(
            f"`{bot_prefix}помощь` - Показывает это сообщение\n"
            f"`{bot_prefix}инфа` - Показывает текущие настройки бота\n"
            f"`{bot_prefix}закрепить` - Закрепляет бота в текущем канале\n"
            f"`{bot_prefix}история [1-20]` - Устанавливает глубину истории сообщений\n"
            f"`{bot_prefix}ОтветИмя` - Вкл/выкл ответы на упоминание имени\n"
            f"`{bot_prefix}ОтветШанс [0.0-1.0]` - Устанавливает шанс случайного ответа"
        ),
        inline=False
    )
    
    help_embed.add_field(
        name="Настройка персонажа",
        value=(
            f"`{bot_prefix}имя [новое_имя]` - Меняет имя бота\n"
            f"`{bot_prefix}персонаж [имя;описание]` - Меняет персонажа бота\n"
            "Пример: `!персонаж Квангелина; Ты - деприсивная поэтесса`"
        ),
        inline=False
    )
    
    help_embed.set_footer(text=f"Бот отвечает на имя '{bot_name}' и случайные сообщения с шансом {random_answer_chance*100}%")
    
    await ctx.send(embed=help_embed)

@bot.event
async def on_ready():
    for guild in bot.guilds:
        for emoji in guild.emojis:
            emoji_cache[emoji.name] = emoji
    print(f'Бот {bot.user.name} успешно запущен!')
    print('------')

if __name__ == '__main__':
    bot.run(bot_token)