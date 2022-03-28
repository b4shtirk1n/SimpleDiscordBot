import discord

from config import *

token = (Ctoken)
client = discord.Client()

@client.event
async def on_message(message):
    if client.get_channel(Cserver):
        print('канал - {0.channel}, Сообщение от {0.author}: {0.content}. дата: {0.created_at}'.format(message))
        print('канал - {0.channel}, Сообщение от {0.author}: {0.content}. дата: {0.created_at}'.format(message), file=open('msglog.txt', 'a'))

client.run(token)

