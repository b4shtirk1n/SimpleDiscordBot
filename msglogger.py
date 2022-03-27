import discord

token = ('OTA1NDUxNTk0Njg0OTY0OTE0.YYKRgg.Uyoz6xmh2dgP5RGx9mOUos-UD0E')
client = discord.Client()

@client.event
async def on_message(message):
    print('канал - {0.channel}, Сообщение от {0.author}: {0.content}. дата: {0.created_at}'.format(message))
    print('канал - {0.channel}, Сообщение от {0.author}: {0.content}. дата: {0.created_at}'.format(message), file=open('msglog.txt', 'a'))

client.run(token)

