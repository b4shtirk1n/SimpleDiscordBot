import discord

from config import *

token = (Gtoken)
bot = discord.Client()

@bot.event
async def on_ready():
    channel = bot.get_channel(int(''))
    embed = discord.Embed(
        title = f"бимбим",
        description = f'бамбам',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    if await channel.send(embed=embed):
        print('эмбед отправлен')
    else: 
        print('ошибка')

bot.run(token)

