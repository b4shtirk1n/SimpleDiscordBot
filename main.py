import discord
import asyncio
import random
import server

from discord.ext import commands
from config import *

token = (Ctoken)
prefix = (Cprefix)
bot = commands.Bot(command_prefix=(prefix))
bot.remove_command('help') #удаление стандартного "help"

#канал для бота

@bot.event
async def on_message(ctx):
    cmdChannel = bot.get_channel(int(Cchannel))
    if ctx.content.lower().startswith(prefix):
        if ctx.channel.id == cmdChannel.id:
            await bot.process_commands(ctx)
        else:
            embed = discord.Embed(
                title = '**чел ты...**',
                description = 'писать нужно в этот канал {}'.format(cmdChannel.mention),
                colour = discord.Colour.from_rgb(255,255,255)
            )
            await (
                await ctx.channel.send(embed=embed)).delete(delay=5)
            await ctx.delete()

#команды

@bot.command(pass_context=True, aliases=['h'])
async def help(ctx):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    embed = discord.Embed(
        title = f'**ПОМОЩЬ**',
        description = f'**{prefix}hello - поздароваться с ботом**\n'
            f'**{prefix}rcolor - включает рандомизацию цвета роли овнера**\n'
            f'**{prefix}info - мнформацмя о боте**\n'
            f'**{prefix}bite - укусить**\n'
            f'**{prefix}cry - плакать**\n'
            f'**{prefix}hug - обнять**\n'
            f'**{prefix}kiss - поцеловать**\n'
            f'**{prefix}nom - угостить**\n'
            f'**{prefix}pat - погладить**\n'
            f'**{prefix}punch - ударить**\n\n'
            f'**СОКРАЩЕНИЯ**\n\n'
            f'**{prefix}hello - hi**\n'
            f'**{prefix}help - h**\n'
            f'**{prefix}rcolor - color, rc, cl**\n'
            f'**{prefix}info - about, i, inf**\n',
        colour = discord.Colour.from_rgb(255,255,255)
    )
    await ctx.send(embed=embed)

@bot.command(pass_context=True, brief='hi')
async def hello(ctx):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    await ctx.send(f'**hello, {author.mention}!**')

@bot.command(pass_context=True, brief='about', aliases=['i', 'inf'])
async def info(ctx):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    embed = discord.Embed(
        title = f'**О БОТЕ**',
        description = f'**простой бот сделаный по приколу**',
        colour = discord.Colour.from_rgb(255,255,255)
    )
    await ctx.send(embed=embed)

#рандомный цвет роли (из перечня цветов)
#роль бота должна быть выше изменяемой роли

@bot.command(pass_context=True, brief='color', aliases=['rc', 'cl'])
async def rcolor(ctx):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    embed = discord.Embed(
        description = ' 💹',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    await (
        await ctx.send(embed=embed)).delete(delay=3)
    await ctx.message.delete()
    colours = [0xff0000, 0xff9f00,0x72ff00, 0x00ff6d, 0x00acff, 0x0200ff, 0xc500ff, 0xff0053, 0xFA8072, 0xFF7F50, 0x00CED1, 0x800080, 0x696969]
    role = discord.utils.get(ctx.guild.roles, id=856831519318081556)
    x = 0
    while (x != 1):
        await role.edit(colour=random.choice(colours))
        await asyncio.sleep(20)

@bot.command(pass_content=True)
async def bite(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/lyWUM7I.gif",
      "https://i.imgur.com/BDrKixN.gif",
      "https://c.tenor.com/SXXCutLZdb4AAAAC/anime-bite.gif",
      "https://thumbs.gfycat.com/YellowishFrightenedHamster-max-1mb.gif",
      "https://64.media.tumblr.com/b1b7287355aedb3f0321188cb255d5d2/tumblr_p8a7oxomw61th206io3_640.gifv",
      "https://i.gifer.com/IDRa.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} укусил(а) {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command(pass_content=True)
async def cry(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/FoacqyH.gif",
      "https://i.imgur.com/hGzdq7C.gif",
      "https://i.imgur.com/OB50VDV.gif",
      "https://i.imgur.com/EuoGFE2.gif",
      "https://i.imgur.com/f0NP6vY.gif",
      "https://i.imgur.com/sbVIswx.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} плачет из-за {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command(pass_content=True)
async def hug(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/Ltmb8aa.gif",
      "https://i.imgur.com/CxmswPU.gif",
      "https://i.imgur.com/v07ICwl.gif",
      "https://i.imgur.com/sZFpOxH.gif",
      "https://i.imgur.com/eIEKQpx.gif",
      "https://i.imgur.com/10orLRe.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} обнял(а) {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command(pass_content=True)
async def kiss(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/RDRXp5M.gif",
      "https://i.imgur.com/RDRXp5M.gif",
      "https://i.imgur.com/gXPmxS4.gif",
      "https://i.imgur.com/g78elNJ.gif",
      "https://i.imgur.com/irLqlOi.gif",
      "https://i.imgur.com/4Ad9iwh.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} поцеловал(а) {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command(pass_content=True)
async def nom(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/Vp3PaGi.gif",
      "https://i.imgur.com/gYqkCsO.gif",
      "https://i.imgur.com/OFMoEr3.gif",
      "https://i.imgur.com/OPvXClz.gif",
      "https://i.imgur.com/ewXFiv4.gif",
      "https://i.imgur.com/PhiUSMm.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} угостил(а) {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command(pass_content=True)
async def pat(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/TPqMPka.gif",
      "https://i.imgur.com/idRX8tM.gif",
      "https://i.imgur.com/lZst12K.gif",
      "https://i.imgur.com/e0I4N2g.gif",
      "https://i.imgur.com/3wFMOxX.gif",
      "https://i.imgur.com/BNdp27d.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} погладил(а) {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command(pass_content=True)
async def punch(ctx, member: discord.Member = None):
    author = ctx.message.author
    print(f'@{author.name}')
    print(f'{author.id}')
    imgs = [
      "https://i.imgur.com/0IxjsfM.gif",
      "https://i.imgur.com/sdcuyFg.gif",
      "https://i.imgur.com/C6lqbl8.gif",
      "https://i.imgur.com/zeGUOaI.gif",
      "https://i.imgur.com/DeKiecj.gif",
      "https://i.imgur.com/5kb586d.gif"
    ]
    if member == None:
        return
    embed = discord.Embed(
        description = f'{ctx.author.mention} ударил(а) {member.mention}',
        colour = discord.Colour.from_rgb(255,255,255)
        )
    embed.set_image(url=random.choice(imgs))
    await ctx.send(embed=embed)
    await ctx.message.delete()

#status

@bot.event
async def on_ready():
    await bot.change_presence(
        status = discord.Status.online,
        activity = discord.Game (f'{prefix}help')
        )

#запуск бота

server.server()
bot.run(token)

