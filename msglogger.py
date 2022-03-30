import discord

from config import *

token = (Ctoken)
client = discord.Client()

@client.event
async def on_message(message):
    if client.get_guild(Cserver):
        log = print('канал - {0.channel}, Сообщение от {0.author}: {0.content}. дата: {0.created_at}'.format(message), file=open('msglog.txt', 'a'))
        print(log)

client.run(token)

