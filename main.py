import os
import asyncio
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
bot_name = "bot"

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

# Асинхронная функция для запроса к Mistral AI
async def get_mistral_response(channel, user_message):
    loop = asyncio.get_event_loop()
    
    # Получаем историю сообщений
    messages_history = []
    async for msg in channel.history(limit=message_history_length + 1):
        if msg.id == user_message.id:  # Пропускаем текущее сообщение
            continue
        role = "assistant" if msg.author == bot.user else "user"
        messages_history.insert(0, {"role": role, "content": msg.content})
    
    # Формируем полный контекст
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(messages_history)
    messages.append({"role": "user", "content": user_message.content})
    
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

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if target_channel_id is not None and message.channel.id != target_channel_id:
        return
    
    if "бот" in message.content.lower():
        try:
            response = await get_mistral_response(message.content)
            if response:
                await message.channel.send(response)
            else:
                await message.channel.send("Извините, возникла ошибка при обработке запроса")
        except Exception as e:
            print(f"Ошибка при обработке сообщения: {e}")
            await message.channel.send("Извините, произошла внутренняя ошибка")
    
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Бот {bot.user.name} успешно запущен!')
    print('------')

@bot.command()
async def бот(ctx):
    await ctx.send("я бот")

if __name__ == '__main__':
    bot.run(bot_token)