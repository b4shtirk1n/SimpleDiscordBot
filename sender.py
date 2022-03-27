import discord

from config import *

token = (Ctoken)
client = discord.Client()

@client.event
async def on_ready():
    channel = client.get_channel(int(input('id канала: ')))
    while True:
        text = input('введите сообщение: ')
        await channel.send(text)

client.run(token)

