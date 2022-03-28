import discord

from config import *

token = (Ctoken)
client = discord.Client()

@client.event
async def on_ready():
    channel = client.get_channel(int('856822748693528586'))
    Eembed = discord.Embed(
        title = f"бимбим",
        description = f'бамбам',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    
    if await channel.send(embed=Eembed):
        print('эмбед отправлен')
    else: 
        print('ошибка')

client.run(token)

