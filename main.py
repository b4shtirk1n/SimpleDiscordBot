import discord
import asyncio
import random
import server
import sqlite3
import youtube_dl
import functools
import itertools
import math

from async_timeout import timeout
from discord.utils import get
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord_together import DiscordTogether
from config import *

token = (Gtoken)
prefix = (Gprefix)
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix=(prefix), intents=intents)
bot.remove_command('help') #удаление стандартного "help"
connection = sqlite3.connect('Shkilagames.db')
cursor = connection.cursor()
youtube_dl.utils.bug_reports_message = lambda: ''

class VoiceError(Exception):
    pass

class YTDLError(Exception):
    pass

class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'audioformat': 'mp3',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }

    ytdl = youtube_dl.YoutubeDL(YTDL_OPTIONS)

    def __init__(self, ctx: commands.Context, source: discord.FFmpegPCMAudio, *, data: dict, volume: float = 0.5):
        super().__init__(source, volume)
        self.requester = ctx.author
        self.channel = ctx.channel
        self.data = data
        self.uploader = data.get('uploader')
        self.uploader_url = data.get('uploader_url')
        date = data.get('upload_date')
        self.upload_date = date[6:8] + '.' + date[4:6] + '.' + date[0:4]
        self.title = data.get('title')
        self.thumbnail = data.get('thumbnail')
        self.description = data.get('description')
        self.duration = self.parse_duration(int(data.get('duration')))
        self.tags = data.get('tags')
        self.url = data.get('webpage_url')
        self.views = data.get('view_count')
        self.likes = data.get('like_count')
        self.dislikes = data.get('dislike_count')
        self.stream_url = data.get('url')

    def __str__(self):
        return '**{0.title}** - **{0.uploader}**'.format(self)

    @classmethod
    async def create_source(cls, ctx: commands.Context, search: str, *, loop: asyncio.BaseEventLoop = None):
        loop = loop or asyncio.get_event_loop()
        partial = functools.partial(cls.ytdl.extract_info, search, download=False, process=False)
        data = await loop.run_in_executor(None, partial)
        if data is None:
            raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        if 'entries' not in data:
            process_info = data
        else:
            process_info = None
            
            for entry in data['entries']:
                if entry:
                    process_info = entry
                    break

            if process_info is None:
                raise YTDLError('Couldn\'t find anything that matches `{}`'.format(search))

        webpage_url = process_info['webpage_url']
        partial = functools.partial(cls.ytdl.extract_info, webpage_url, download=False)
        processed_info = await loop.run_in_executor(None, partial)
        if processed_info is None:
            raise YTDLError('Couldn\'t fetch `{}`'.format(webpage_url))

        if 'entries' not in processed_info:
            info = processed_info
        else:
            info = None
            
            while info is None:
                try:
                    info = processed_info['entries'].pop(0)
                except IndexError:
                    raise YTDLError('Couldn\'t retrieve any matches for `{}`'.format(webpage_url))

        return cls(ctx, discord.FFmpegPCMAudio(info['url'], **cls.FFMPEG_OPTIONS), data=info)

    @staticmethod
    def parse_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)
        duration = []
        if days > 0:
            duration.append('{} дней'.format(days))
        if hours > 0:
            duration.append('{} часов'.format(hours))
        if minutes > 0:
            duration.append('{} минут'.format(minutes))
        if seconds > 0:
            duration.append('{} секунд'.format(seconds))

        return ', '.join(duration)

class Song:
    __slots__ = ('source', 'requester')

    def __init__(self, source: YTDLSource):
        self.source = source
        self.requester = source.requester

    def create_embed(self):
        embed = discord.Embed(
            title='сейчас играет',
            description='```css\n{0.source.title}\n```'.format(self),
            color=discord.Color.blurple()
            )
        embed.add_field(
            name='Duration',
            value=self.source.duration
            )
        embed.add_field(
            name='Requested by',
            value=self.requester.mention
            )
        embed.add_field(
            name='Uploader',
            value='[{0.source.uploader}]({0.source.uploader_url})'.format(self)
            )
        embed.add_field(
            name='URL',
            value='[Click]({0.source.url})'.format(self)
            )
        embed.set_thumbnail(url=self.source.thumbnail)
        return embed

class SongQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int):
        del self._queue[index]

class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context):
        self.bot = bot
        self._ctx = ctx
        self.current = None
        self.voice = None
        self.next = asyncio.Event()
        self.songs = SongQueue()
        self._loop = False
        self._volume = 0.5
        self.skip_votes = set()
        self.audio_player = bot.loop.create_task(self.audio_player_task())

    def __del__(self):
        self.audio_player.cancel()

    @property
    def loop(self):
        return self._loop

    @loop.setter
    def loop(self, value: bool):
        self._loop = value

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value: float):
        self._volume = value

    @property
    def is_playing(self):
        return self.voice and self.current

    async def audio_player_task(self):
        while True:
            self.next.clear()
            if not self.loop:
                try:
                    async with timeout(180):
                        self.current = await self.songs.get()
                except asyncio.TimeoutError:
                    self.bot.loop.create_task(self.stop())
                    return

            self.current.source.volume = self._volume
            self.voice.play(self.current.source, after=self.play_next_song)
            await self.current.source.channel.send(embed=self.current.create_embed())
            await self.next.wait()

    def play_next_song(self, error=None):
        if error:
            raise VoiceError(str(error))

        self.next.set()

    def skip(self):
        self.skip_votes.clear()
        if self.is_playing:
            self.voice.stop()

    async def stop(self):
        self.songs.clear()
        if self.voice:
            await self.voice.disconnect()
            self.voice = None

class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}

    def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        if not state:
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            raise commands.NoPrivateMessage('This command can\'t be used in DM channels.')

        return True

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        errorembed = discord.Embed(
            description = "ошибка: {}".format(str(error))
        )
        await ctx.send(embed=errorembed)

    #команды отвечающие за музыку

    @commands.command(name='join' , invoke_without_subcommand=True)
    async def _join(self, ctx: commands.Context):
        destination = ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='summon')
    async def _summon(self, ctx: commands.Context, *, channel: discord.VoiceChannel = None):
        if not channel and not ctx.author.voice:
            raise VoiceError('You are neither connected to a voice channel nor specified a channel to join.')

        destination = channel or ctx.author.voice.channel
        if ctx.voice_state.voice:
            await ctx.voice_state.voice.move_to(destination)
            return

        ctx.voice_state.voice = await destination.connect()

    @commands.command(name='leave', aliases=['disconnect'])
    async def _leave(self, ctx: commands.Context):
        if not ctx.voice_state.voice:
            embed = discord.Embed(
                description = f'не подключён к голосовому каналу'
            )
            return await ctx.send(embed=embed)

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id]

    @commands.command(name='now', aliases=['current', 'playing'])
    async def _now(self, ctx: commands.Context):
        await ctx.send(embed=ctx.voice_state.current.create_embed())

    @commands.command(name='pause')
    async def _pause(self, ctx: commands.Context):
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_playing():
            ctx.voice_state.voice.pause()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='resume')
    async def _resume(self, ctx: commands.Context):
        if ctx.voice_state.is_playing and ctx.voice_state.voice.is_paused():
            ctx.voice_state.voice.resume()
            await ctx.message.add_reaction('⏯')

    @commands.command(name='stop', aliases=['s'])
    async def _stop(self, ctx: commands.Context):
        ctx.voice_state.songs.clear()
        if ctx.voice_state.is_playing:
            ctx.voice_state.voice.stop()
            await ctx.message.add_reaction('⏹')

    @commands.command(name='skip')
    async def _skip(self, ctx: commands.Context):
        if not ctx.voice_state.is_playing:
            embed = discord.Embed(
                description = f'нет трека'
            )
            return await ctx.send(embed=embed)

        voter = ctx.message.author
        if voter == ctx.voice_state.current.requester:
            await ctx.message.add_reaction('⏭')
            ctx.voice_state.skip()

        elif voter.id not in ctx.voice_state.skip_votes:
            ctx.voice_state.skip_votes.add(voter.id)
            total_votes = len(ctx.voice_state.skip_votes)
            if total_votes >= 3:
                await ctx.message.add_reaction('⏭')
                ctx.voice_state.skip()
            else:
                accembed = discord.Embed(
                    description = 'голосование **{}/3**'.format(total_votes)
                )
                await ctx.send(embed=accembed)
        else:
            erembed = discord.Embed(
                description = f'ты не можешь пропускать треки'
            )
            await ctx.send(embed=erembed)

    @commands.command(name='queue')
    async def _queue(self, ctx: commands.Context, *, page: int = 1):
        if len(ctx.voice_state.songs) == 0:
            emptembed = discord.Embed(
                description = f'очередь пуста'
            )
            return await ctx.send(embed=emptembed)

        items_per_page = 10
        pages = math.ceil(len(ctx.voice_state.songs) / items_per_page)
        start = (page - 1) * items_per_page
        end = start + items_per_page
        queue = ''
        
        for i, song in enumerate(ctx.voice_state.songs[start:end], start=start):
            queue += '`{0}.` [**{1.source.title}**]({1.source.url})\n'.format(i + 1, song)

        embed = (discord.Embed(
            description='**{} tracks:**\n\n{}'.format(len(ctx.voice_state.songs), queue))
                 .set_footer(text='страница {}/{}'.format(page, pages)))
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def _shuffle(self, ctx: commands.Context):
        if len(ctx.voice_state.songs) == 0:
            embed = discord.Embed(
                description = f'очередь пуста'
            )
            return await ctx.send(embed=embed)
        
        ctx.voice_state.songs.shuffle()
        await ctx.message.add_reaction('✅')

    @commands.command(name='remove')
    async def _remove(self, ctx: commands.Context, index: int):
        if len(ctx.voice_state.songs) == 0:
            return await ctx.send('Empty queue.')

        ctx.voice_state.songs.remove(index - 1)
        await ctx.message.add_reaction('✅')

    @commands.command(name='loop')
    async def _loop(self, ctx: commands.Context):
        if not ctx.voice_state.is_playing:
            embed = discord.Embed(
                description = f'нет трека'
            )
            return await ctx.send(embed=embed)

        ctx.voice_state.loop = not ctx.voice_state.loop
        await ctx.message.add_reaction('✅')

    @commands.command(name='play', aliases=['p'])
    async def _play(self, ctx: commands.Context, *, search: str):
        if not ctx.voice_state.voice:
            await ctx.invoke(self._join)

        async with ctx.typing():
            try:
                source = await YTDLSource.create_source(ctx, search, loop=self.bot.loop)
            except YTDLError as e:
                await ctx.send('ошибка: {}'.format(str(e)))
            else:
                song = Song(source)
                embed = discord.Embed(
                    title='добавлен в очередь',
                    description='```css\n{0.title}\n```'.format(source),
                    color=discord.Color.blurple()
                    )
                embed.add_field(
                    name='URL',
                    value='[Click]({0.url})'.format(source)
                    )
                await ctx.voice_state.songs.put(song)
                await ctx.send(embed=embed)

    @_join.before_invoke
    @_play.before_invoke
    async def ensure_voice_state(self, ctx: commands.Context):
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError(f'{ctx.author.mention} не подключён к голосовому каналу')

        if ctx.voice_client:
            if ctx.voice_client.channel != ctx.author.voice.channel:
                raise commands.CommandError('бот не может зайти в голосовой канал')

#основные команды

class Command:
    @bot.command(pass_context=True, aliases=['h'])
    async def help(ctx):
        embed = discord.Embed(colour = discord.Colour.from_rgb(255, 255, 255))
        embed.add_field(
            name = f'**основные команды**\n',
            value = f'```python\n{prefix}rcolor "rc" "cl" - включает рандомизацию цвета выбранной роли```'
                f'```python\n{prefix}balance "money" <@пользователь> - баланс пользователя```'
                f'```python\n{prefix}leaderboard "top" "lb" - просмотр топ 10 сервера```'
                f'```python\n{prefix}slots <сумма/all(вся сумма)> - игра в слоты```'
                f'```python\n{prefix}shop - просмотр товаров в магазине```'
                f'```python\n{prefix}buy - покупка товаров в магазине```'
                f'```python\n{prefix}transfer - <сумма> <@пользователь> перевод валюты пользователю```'
                f'```python\n{prefix}watch "w" - просмотр ютуба в голосовом канале```'
                f'```python\n{prefix}ben - спросить что нибудь у Бена```'
                f'```python\n{prefix}clear "c" <число> - очищает определённое количество сообщений```',
            inline = False
            )
        embed.add_field(
            name = f'**реакции**',
            value = f'\n```python\n{prefix}bite <@пользователь/оставить пустым(все)> - укусить```'
                f'```python\n{prefix}cry <@пользователь/оставить пустым(все)> - плакать```'
                f'```python\n{prefix}hug <@пользователь/оставить пустым(все)> - обнять```'
                f'```python\n{prefix}kiss <@пользователь/оставить пустым(все)> - поцеловать```'
                f'```python\n{prefix}nom <@пользователь/оставить пустым(все)> - угостить```'
                f'```python\n{prefix}pat <@пользователь/оставить пустым(все)> - погладить```'
                f'```python\n{prefix}punch <@пользователь/оставить пустым(все)> - ударить```',
            inline = False
            )
        embed.add_field(
            name = f'**музыкальные команды**',
            value = f'\n```python\n{prefix}play "p" <название трека/ссылка> - воспроизведение выбранного трека```'
                f'```python\n{prefix}stop "s" - остановка воспроизведения```'
                f'```python\n{prefix}skip - пропуск трека```'
                f'```python\n{prefix}pause - приостановка воспроизведения```'
                f'```python\n{prefix}resume "r" - продолжить воспроизведения```'
                f'```python\n{prefix}loop - поставить на повтор```'
                f'```python\n{prefix}shuffle - перемешать плейлист```'
                f'```python\n{prefix}queue "q" - показать плейлист```'
                f'```python\n{prefix}now "current" "playing" "n" - что воспроизводится сейчас```'
                f'```python\n{prefix}leave - "l" выгнать бота из голосового канала```',
            inline = False
            )
        embed.add_field(
            name = f'**настройки**',
            value = f'\n```python\n{prefix}mainchannel "mc" <id канала> - назначает канал для бота```'
                f'```python\n{prefix}editmainchannel "emc" <id канала> - меняет назначенный канал для бота```'
                f'```python\n{prefix}dropmainchannel "dmc" <id канала> - снимает назначенный канал для бота```'
                f'```python\n{prefix}addshop <названеи(без пробелов)> <цена> <роль(пожеланию)> - добавляет предмет в магазин```'
                f'```python\n{prefix}dropshop <номер предмета> - убирает предмета из магазина```'
                f'```python\n{prefix}userrole "ur" <@роль> - назначает роль для пользователей```'
                f'```python\n{prefix}dropuserrole "dur" <@роль> - снимает назначенную роль для пользователей```',
            inline = False
            )
        await ctx.send(embed=embed)
        await ctx.message.delete()

    @bot.command(pass_content=True)
    async def bite(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/lyWUM7I.gif",
            "https://i.imgur.com/BDrKixN.gif",
            "https://c.tenor.com/SXXCutLZdb4AAAAC/anime-bite.gif",
            "https://thumbs.gfycat.com/YellowishFrightenedHamster-max-1mb.gif",
            "https://64.media.tumblr.com/b1b7287355aedb3f0321188cb255d5d2/tumblr_p8a7oxomw61th206io3_640.gifv",
            "https://i.gifer.com/IDRa.gif",
            "https://c.tenor.com/sMgdnhlBl3QAAAAS/spongebob-wacky.gif",
            "https://c.tenor.com/nfQnxxQi380AAAAS/tokyo-ghoul.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} укусил(а) всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} укусил(а) {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def cry(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/FoacqyH.gif",
            "https://i.imgur.com/hGzdq7C.gif",
            "https://i.imgur.com/OB50VDV.gif",
            "https://i.imgur.com/EuoGFE2.gif",
            "https://i.imgur.com/f0NP6vY.gif",
            "https://i.imgur.com/sbVIswx.gif",
            "https://c.tenor.com/NVsFK-ScJWUAAAAS/the-promised.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} плачет из-за всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} плачет из-за {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def hug(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/Ltmb8aa.gif",
            "https://i.imgur.com/CxmswPU.gif",
            "https://i.imgur.com/v07ICwl.gif",
            "https://i.imgur.com/sZFpOxH.gif",
            "https://i.imgur.com/eIEKQpx.gif",
            "https://i.imgur.com/10orLRe.gif",
            "https://c.tenor.com/Veq4zvSQkdAAAAAC/hugmati.gif",
            "https://c.tenor.com/4ETvd4HwIf8AAAAS/the-promised-neverland-tpn.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} обнял(а) всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} обнял(а) {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def kiss(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/RDRXp5M.gif",
            "https://i.imgur.com/RDRXp5M.gif",
            "https://i.imgur.com/gXPmxS4.gif",
            "https://i.imgur.com/g78elNJ.gif",
            "https://i.imgur.com/irLqlOi.gif",
            "https://i.imgur.com/4Ad9iwh.gif",
            "https://c.tenor.com/s7s_Ibwt7sEAAAAC/naruto-sasuke.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} поцеловал(а) всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} поцеловал(а) {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def nom(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/Vp3PaGi.gif",
            "https://i.imgur.com/gYqkCsO.gif",
            "https://i.imgur.com/OFMoEr3.gif",
            "https://i.imgur.com/OPvXClz.gif",
            "https://i.imgur.com/ewXFiv4.gif",
            "https://i.imgur.com/PhiUSMm.gif",
            "https://c.tenor.com/DKH5nFv337wAAAAS/jojo-jojos-bizarre-adventure.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} угостил(а) всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} угостил(а) {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def pat(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/TPqMPka.gif",
            "https://i.imgur.com/idRX8tM.gif",
            "https://i.imgur.com/lZst12K.gif",
            "https://i.imgur.com/e0I4N2g.gif",
            "https://i.imgur.com/3wFMOxX.gif",
            "https://i.imgur.com/BNdp27d.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} погладил(а) всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} погладил(а) {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def punch(ctx, member: discord.Member = None):
        imgs = [
            "https://i.imgur.com/0IxjsfM.gif",
            "https://i.imgur.com/sdcuyFg.gif",
            "https://i.imgur.com/C6lqbl8.gif",
            "https://i.imgur.com/zeGUOaI.gif",
            "https://i.imgur.com/DeKiecj.gif",
            "https://i.imgur.com/5kb586d.gif",
            "https://c.tenor.com/ciZ8Qnc3rvAAAAAd/naruto-sasuke.gif",
            "https://c.tenor.com/qrNB6eZr3HQAAAAS/jojo-bizarre-jojos-adventure.gif",
            "https://c.tenor.com/mRUVeqkaRmcAAAAC/the-promised-neverland.gif",
            "https://c.tenor.com/j7NOSQaK2pkAAAAd/jojos-bizarre-adventure-milton-jojo.giff",
            "https://c.tenor.com/ADJfg5Z2dl0AAAAS/minions-minion.gif",
            "https://c.tenor.com/ZgrqWWHGdQYAAAAC/minions-despicable-me.gif"
            ]
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} ударил(а) всех',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'{ctx.author.mention} ударил(а) {member.mention}',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            embed.set_image(url=random.choice(imgs))
            await ctx.send(embed=embed)
            await ctx.message.delete()

    #рандомный цвет роли (роль бота должна быть выше изменяемой роли)

    @bot.command(pass_context=True, aliases=['addrc', 'addcl'])
    @has_permissions(manage_roles=True)
    async def addrcolor(ctx, role):
        if role == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} укажите роль',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            if role == cursor.execute(f"select Role from RColor where Role = {role.id} GuildId = {ctx.guild.id}").fetchone()[0]:
                cursor.execute(f"insert into RColor (GuildId, Role) values ({ctx.guild.id}, {role.id})")
                embed = discord.Embed(
                    description = '✅',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                embed = discord.Embed(
                    description = 'роль уже добавлена',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()

    @bot.command(pass_context=True, aliases=['rc', 'cl'])
    @has_permissions(manage_roles=True)
    async def rcolor(ctx):
        embed = discord.Embed(
            description = '✅',
            colour = discord.Colour.from_rgb(255, 255, 255)
            )
        await(
            await ctx.send(embed=embed)).delete(delay=5)
        await ctx.message.delete()

        while True:
            guild = ctx.guild
            for role in guild.roles:
                for roleid in cursor.execute(f"select Role from RColor").fetchall():
                    for row in roleid:
                        if role.id == int(row):
                            x = random.randint(0, 255)
                            y = random.randint(0, 255)
                            z = random.randint(0, 255)
                            await role.edit(colour = discord.Colour.from_rgb(x, y, z))
                            await asyncio.sleep(40)

    @bot.command(pass_context=True, aliases=['money'])
    async def balance(ctx, member: discord.Member = None):
        if member == None:
            embed = discord.Embed(
                description = f"""Баланс **{ctx.author.mention}** составляет **{cursor.execute(f"select Money from User where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}").fetchone()[0]} :leaves:**""",
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await ctx.send(embed=embed)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f"""Баланс **{member.mention}** составляет **{cursor.execute(f"select Money from User where UserId = {member.id} and GuildId = {ctx.guild.id}").fetchone()[0]} :leaves:**""",
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_context=True, aliases=['top', 'lb'])
    async def leaderboard(ctx):
        embed = discord.Embed(
            title = 'Топ 10 сервера',
            colour = discord.Colour.from_rgb(255, 255, 255)
            )
        counter = 0
        
        for row in cursor.execute(f"select Name, Money from User where GuildId = {ctx.guild.id} order by Money desc limit 10"):
            counter += 1
            embed.add_field(
                name = f'# {counter} | `{row[0]}`',
                value = f'Баланс: {row[1]}',
                inline = False
                )
        await ctx.send(embed=embed)
        await ctx.message.delete()

    @bot.command(pass_context=True)
    async def shop(ctx):
        embed = discord.Embed(
            title = 'магазин',
            colour = discord.Colour.from_rgb(255, 255, 255)
            )
        counter = 0
        
        for row in cursor.execute(f"select Name, Role, Cost from Shop where GuildId = {ctx.guild.id} order by cost asc"):
            counter += 1
            role = row[1]
            if role == None:
                embed.add_field(
                    name = f'# {counter} | {row[0]}',
                    value = f'{row[1]} | цена - {row[2]}',
                    inline = False
                    )
            else:
                role = ctx.guild.get_role(int(role))
                embed.add_field(
                    name = f'# {counter} | {row[0]}',
                    value = f'{role.mention} | цена - {row[2]}',
                    inline = False
                    )
                await ctx.send(embed=embed)
                await ctx.message.delete()

    @bot.command(pass_context=True)
    async def buy(ctx, content: str = None):
        if content == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} укажите товар',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
            return
        else:
            cost = cursor.execute(f"select Cost from Shop where Name = '{content}' and GuildId = {ctx.guild.id}").fetchone()[0]
            money = cursor.execute(f"select Money from User where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}").fetchone()[0]
            if cost > money:
                embed = discord.Embed(
                    description = f'{ctx.author.mention} у вас недостаточно средств',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                cursor.execute(f"update User set Money = Money - {cost} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
                connection.commit()
                embed = discord.Embed(
                    description = '✅',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()

                role = cursor.execute(f"select Role from Shop where Name = '{content}' and GuildId = {ctx.guild.id}").fetchone()[0]
                if role != None:
                    await ctx.author.add_roles(ctx.guild.get_role(int(role)))

    @bot.command(pass_content=True)
    async def watch(ctx):
        link = await bot.togetherControl.create_link(ctx.author.voice.channel.id, 'youtube')
        await ctx.send(link)

    @bot.command(pass_content=True)
    async def Ben(ctx):
        x = random.randint(1, 4)
        if x == 1:
            text = 'ееес'
        if x == 1:
            text = 'ноу'
        if x == 1:
            text = 'ээу'
        if x == 1:
            text = 'ээу'

        embed = discord.Embed(
            description = f'{text}',
            colour = discord.Colour.from_rgb(255, 255, 255)
            )
        await ctx.send(embed=embed)

    @bot.command(pass_content=True)
    @has_permissions(manage_roles=True)
    async def clear(ctx, amount):
        await ctx.channel.purge(limit=int(amount))

    @bot.command(pass_content=True)
    @has_permissions(manage_roles=True)
    async def addshop(ctx, content, amount, role: discord.Role = None):
        if cursor.execute(f"select Name from Shop where Name = '{content}'").fetchone() != None:
            embed = discord.Embed(
                description = 'такой товар уже есть',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = '✅',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            if role == None:
                cursor.execute(f"insert into Shop (GuildId, Name, Cost) values ({ctx.guild.id}, '{content}', {amount})")
                connection.commit()
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                cursor.execute(f"insert into Shop (GuildId, Name, Role, Cost) values ({ctx.guild.id}, '{content}', {role.id}, {amount})")
                connection.commit()
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()

    @bot.command(pass_context=True)
    async def transfer(ctx, amount, member: discord.Member = None):
        amount = int(amount)
        if member == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} укажите пользователя',
                colour = discord.Colour.from_rgb(255, 255, 255)
            )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            if amount <= 0:
                embed = discord.Embed(
                    description = f'{ctx.author.mention} нельзя ставить ноль или меньше',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                money = cursor.execute(f"select Money from User where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}").fetchone()[0]
                if amount > money:
                    embed = discord.Embed(
                        description = f'{ctx.author.mention} у вас недостаточно средств',
                        colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                    await(
                        await ctx.send(embed=embed)).delete(delay=5)
                    await ctx.message.delete()
                else:
                    cursor.execute(f"update User set Money = Money - {amount} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
                    cursor.execute(f"update User set Money = Money + {amount} where UserId = {member.id} and GuildId = {ctx.guild.id}")
                    connection.commit()
                    embed = discord.Embed(
                        description = '✅',
                        colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                    await(
                        await ctx.send(embed=embed)).delete(delay=5)
                    await ctx.message.delete()

    @bot.command(pass_content=True, aliases=['mc'])
    @has_permissions(manage_roles=True)
    async def mainchannel(ctx, content: str = None):
        if content == None:
            embed = discord.Embed(
                description = 'укажите id канала',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            if cursor.execute(f"select MainChannel from Guild where MainChannel = {content}").fetchone() == None:
                cursor.execute(f"update Guild set MainChannel = {content} where GuildId = {ctx.guild.id}")
                connection.commit()
                embed = discord.Embed(
                    description = '✅',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                embed = discord.Embed(
                    description = 'главный канал уже добавлен или такого канала нет',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()

    @bot.command(pass_content=True, aliases=['emc'])
    @has_permissions(manage_roles=True)
    async def editmainchannel(ctx, content: str = None):
        if content == None:
            embed = discord.Embed(
                description = 'укажите id канала',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            if cursor.execute(f"select MainChannel from Guild where GuildId = {ctx.guild.id}").fetchone() != None:
                cursor.execute(f"update Guild set MainChannel = {content} where GuildId = {ctx.guild.id}")
                connection.commit()
                embed = discord.Embed(
                    description = '✅',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                embed = discord.Embed(
                    description = 'главный канал ещё не был определён',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()

    @bot.command(pass_content=True, aliases=['dmc'])
    @has_permissions(manage_roles=True)
    async def dropmainchannel(ctx, content: str = None):
        if content == None:
            embed = discord.Embed(
                description = 'укажите id канала',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            if cursor.execute(f"select MainChannel from Guild where MainChannel = {content}").fetchone() != None:
                cursor.execute(f"update Guild set MainChannel = null where GuildId = {ctx.guild.id}")
                connection.commit()
                embed = discord.Embed(
                    description = '✅',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()
            else:
                embed = discord.Embed(
                    description = f'главный канал ещё не добавлен или такого канала нет',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await(
                    await ctx.send(embed=embed)).delete(delay=5)
                await ctx.message.delete()

    @bot.command(pass_content=True, aliases=['ur'])
    @has_permissions(manage_roles=True)
    async def userrole(ctx, role):
        idrole = role[3:21]
        if cursor.execute(f"select UserRole from Guild where GuildId = {ctx.guild.id}").fetchone()[0] == None:
            cursor.execute(f"update Guild set UserRole = {idrole} where GuildId = {ctx.guild.id}")
            connection.commit()
            embed = discord.Embed(
                description = '✅',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            embed = discord.Embed(
                description = f'роль пользователя уже добавлена или такой роли нет',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await ctx.send(embed=embed)
            await ctx.message.delete()

    @bot.command(pass_content=True)
    async def slots(ctx, content: str = None):
        if content == None:
            embed = discord.Embed(
                description = f'{ctx.author.mention} укажите сумму',
                colour = discord.Colour.from_rgb(255, 255, 255)
                )
            await(
                await ctx.send(embed=embed)).delete(delay=5)
            await ctx.message.delete()
        else:
            if content == 'all':
                money = cursor.execute(f"select Money from User where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}").fetchone()[0]
                amount = int(money)
            else:
                amount = int(content)
                if amount <= 0:
                    embed = discord.Embed(
                        description = f'{ctx.author.mention} нельзя ставить ноль или меньше',
                        colour = discord.Colour.from_rgb(255, 255, 255)
                        )
                    await(
                        await ctx.send(embed=embed)).delete(delay=5)
                    await ctx.message.delete()
                    return
                else:
                    money = cursor.execute(f"select Money from User where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}").fetchone()[0]
                if amount > money:
                    embed = discord.Embed(
                        description = f'{ctx.author.mention} у вас недостаточно средств',
                        colour = discord.Colour.from_rgb(255, 255, 255)
                        )
                    await(
                        await ctx.send(embed=embed)).delete(delay=5)
                    await ctx.message.delete()
                    return

            cursor.execute(f"update User set Money = Money - {amount} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
            connection.commit()

            x = random.randint(1, 3)
            y = random.randint(1, 3)
            z = random.randint(1, 3)
            if x == y == z == 1:
                amount = amount*5
                cursor.execute(f"update User set Money = Money + {amount} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
                connection.commit()
                embed = discord.Embed(
                    description = f'{ctx.author.mention} выйграл {amount}\n',
                    colour = discord.Colour.from_rgb(255, 255, 255)
                    )
                await ctx.send(embed=embed)
                await ctx.message.delete()
            else:
                if x == y == z == 2:
                    amount = amount*10
                    cursor.execute(f"update User set Money = Money + {amount} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
                    connection.commit()
                    embed = discord.Embed(
                        description = f'{ctx.author.mention} выйграл {amount}',
                        colour = discord.Colour.from_rgb(255, 255, 255)
                        )
                    await ctx.send(embed=embed)
                    await ctx.message.delete()
                else:
                    if x == y == z == 3:
                        amount = amount*15
                        cursor.execute(f"update User set Money = Money + {amount} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
                        connection.commit()
                        embed = discord.Embed(
                            description = f'{ctx.author.mention} выйграл {amount}',
                            colour = discord.Colour.from_rgb(255, 255, 255)
                            )
                        await ctx.send(embed=embed)
                        await ctx.message.delete()
                    else:
                        embed = discord.Embed(
                            description = f'{ctx.author.mention} проиграл {amount}',
                            colour = discord.Colour.from_rgb(255, 255, 255)
                            )
                        await ctx.send(embed=embed)
                        await ctx.message.delete()

#задачи

class Task:
    @tasks.loop(minutes=5)
    async def voice_check():
        for guild in bot.guilds:
            for channel in guild.voice_channels != guild.afk_channel:
                for member in channel.members:
                    if member.voice.mute == False or member.voice.self_mute == False or member.voice.afk == False or member.status == discord.Status.idle or member.Bot == False:
                        money = random.randint(5, 40)
                        cursor.execute(f"update User set Money = Money + {money} where UserId = {member.id} and GuildId = {member.guild.id}")
                        connection.commit()

#события

class Event:
    @bot.event
    async def on_ready():
        cursor.execute("""create table if not exists [User](
                Id integer primary key autoincrement not null,
                UserId nchar(18),
                Name text,
                Money bigint,
                GuildId nchar(18)
            )"""
        )

        cursor.execute("""create table if not exists Shop(
                Id integer primary key autoincrement not null,
                GuildId nchar(18),
                Name text,
                Role nchar(18),
                Cost bigint
            )"""
        )

        cursor.execute("""create table if not exists Guild(
                Id integer primary key autoincrement not null,
                GuildId nchar(18),
                MainChannel nchar(18),
                UserRole nchar(18)
            )"""
        )

        cursor.execute("""create table if not exists RColor(
                Id integer primary key autoincrement not null,
                GuildId nchar(18),
                Role nchar(18)
            )"""
        )

        for guild in bot.guilds:
            for member in guild.members:
                if cursor.execute(f"select UserId from User where UserId = {member.id} and GuildId = {guild.id}").fetchone() == None:
                    cursor.execute(f"insert into User (UserId, Name, Money, GuildId) values ({member.id}, '{member}', 0, {guild.id})")
                    connection.commit()

        bot.togetherControl = await DiscordTogether(token)
        await bot.change_presence(
            status = discord.Status.online,
            activity = discord.Game(f'{prefix}help')
            )

    @bot.event
    async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
        channel = bot.get_channel(int(961653938036305940))
        member = payload.member
        if channel.id == payload.channel_id:
            if str(payload.emoji.name) == '1️⃣':
                await member.add_roles(member.guild.get_role(961654860229525574))

            if str(payload.emoji.name) == '2️⃣':
                await member.add_roles(member.guild.get_role(961636575576481852))

            if str(payload.emoji.name) == '3️⃣':
                await member.add_roles(member.guild.get_role(961628644437008455))

    @bot.event
    async def on_raw_reaction_remove(payload: discord.RawReactionActionEvent):
        channel = bot.get_channel(int(961653938036305940))
        message = await channel.fetch_message(payload.message_id)
        member = get(message.guild.members, id=payload.user_id)
        role = message.guild.get_role(961654860229525574)
        role2 = message.guild.get_role(961636575576481852)
        role3 = channel.guild.get_role(961628644437008455)
        if channel.id == payload.channel_id:
            if str(payload.emoji.name) == '1️⃣':
                await member.remove_roles(role)

            if str(payload.emoji.name) == '2️⃣':
                await member.remove_roles(role2)

            if str(payload.emoji.name) == '3️⃣':
                await member.remove_roles(role3)

    @bot.event
    async def on_member_join(member):
        if cursor.execute(f"select UserId from User where UserId = {member.id} and GuildId = {member.guild.id}").fetchone() == None:
            cursor.execute(f"insert into User (UserId, Name, Money, GuildId) values ({member.id}, '{member.name}', 0, {member.guild.id})")
            connection.commit()
            role = cursor.execute(f"select UserRole from Guild where GuildId = {member.guild.id}").fetchone()[0]

            await member.add_roles(member.guild.get_role(int(role)), atomic=True)

    @bot.event
    async def on_member_left(member):
        if cursor.execute(f"select UserId from User where UserId = {member.id} and GuildId = {member.guild.id}").fetchone() == None:
            cursor.execute(f"delete from User where UserId = {member.id} and GuildId = {member.guild.id}")
            connection.commit()

    @bot.event
    async def on_guild_join(guild):
        for guild in bot.guilds:
            for member in guild.members:
                if cursor.execute(f"select GuildId from Guild where GuildId = {guild.id}").fetchone() == None:
                    cursor.execute(f"insert into User (UserId, Name, Money, GuildId) values ({member.id}, '{member}', 0, {guild.id})")
                    cursor.execute(f"insert into Guild (GuildId) values ({guild.id})")
                    connection.commit()

    @bot.event
    async def on_message(ctx):
        if cursor.execute(f"select MainChannel from Guild where GuildId = {ctx.guild.id}").fetchone()[0] == None:
            await bot.process_commands(ctx)
        else:
            gchannel = cursor.execute(f"select MainChannel from Guild where GuildId = {ctx.guild.id}").fetchone()[0]
            cmdChannel = bot.get_channel(int(gchannel))
            if ctx.content.lower().startswith(prefix):
                if ctx.channel.id == cmdChannel.id:
                    await bot.process_commands(ctx)
                else:
                    embed = discord.Embed(
                        title = '**чел ты...**',
                        description = 'писать нужно в этот канал {}'.format(cmdChannel.mention),
                        colour = discord.Colour.from_rgb(255, 255, 255)
                        )
                    await(
                        await ctx.channel.send(embed=embed)).delete(delay=5)
                    await ctx.delete()

        #канал для бота

        ideach = bot.get_channel(int(956606428683051018))
        if ctx.author.id != 958040720403472454:
            if ctx.channel.id == ideach.id:
                if ctx.content.lower().startswith(prefix):
                    await bot.process_commands(ctx)
                else:
                    text = ctx.content
                    embed = discord.Embed(
                        title = f'Идея от: **{ctx.author}**',
                        description = f'{text}',
                        colour = discord.Colour.from_rgb(255, 255, 255)
                        )
                    message = await ideach.send(embed=embed)
                    await message.add_reaction('✅')
                    await message.add_reaction('❌')
                    await ctx.delete()

        log = 'сервер - {0.guild} канал - {0.channel}, Сообщение от {0.author}: {0.content}. дата: {0.created_at}'.format(ctx)
        print(log, file=open('msglog.txt', 'a'))
        print(log)

        #выдача валюты, если сообщение длиннее 15 символов

        if len(ctx.content) > 15 and ctx.author.bot == False:
            money = random.randint(5, 40)
            cursor.execute(f"update User set Money = Money + {money} where UserId = {ctx.author.id} and GuildId = {ctx.guild.id}")
            connection.commit()

#запуск бота

class Run:
    server.server()
    bot.add_cog(Music(bot))
    bot.run(token)
    Task.voice_check.start()