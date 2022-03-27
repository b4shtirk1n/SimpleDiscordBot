import discord

token = ('OTA1NDUxNTk0Njg0OTY0OTE0.YYKRgg.Uyoz6xmh2dgP5RGx9mOUos-UD0E')
client = discord.Client()

@client.event
async def on_ready():
    print('start')
    channel = client.get_channel(int('856822748693528586'))
    embed = discord.Embed(
        title = f"бимбим",
        description = f'бамбам',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    await channel.send(embed=embed)

client.run(token)

