import os
import datetime
import nextcord

from nextcord import Interaction, SlashOption
from nextcord.ext import commands, tasks
from nextcord.ext.commands import has_permissions

from sqlitedict import SqliteDict

TOKEN = os.environ['TOKEN']
GUILD_ID = os.environ['SERVERID']

db = SqliteDict('./{}.sqlite'.format(GUILD_ID), autocommit=True)

all_cities = "All"
cities = ["Svargrond", "Plains of Havoc", "Forbidden Lands", "Kazordoon", "Ramoa", "Edron", "Drefia", "Hellgate",
          "Ankrahmun", "Yalahar"]
city_options = cities.copy()
city_options.append(all_cities)

LIGHTKEEPER_ROLE = "lightkeeper_role"
LIGHTKEEPER_ROLE_EMOJI = "lightkeeper_role_emoji"
STATUS_CHANNEL = "status_channel"
STATUS_MESSAGE = "status_message"
ALERT_TIME = "alert_time"
FAILED = "failed"

start_date = datetime.datetime(2022, 11, 11, 10, 00)
end_date = datetime.datetime(2022, 11, 15, 10, 00)
update_interval = 10  # seconds


def log(message):
    now = datetime.datetime.today().replace(microsecond=0)
    log_message = "{} {}".format(now, message).encode('ascii', 'ignore').decode()
    print(log_message)
    with open("{}.log".format(GUILD_ID), "a") as logfile:
        logfile.write("{}\n".format(log_message))


class LightbearerBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lightkeeper_role = None
        self.emoji = None
        self.status_message = None
        self.status_channel = None

    async def __fix_roles(self):
        if self.status_message is not None and self.emoji is not None and self.lightkeeper_role is not None:
            for reaction in self.status_message.reactions:
                if reaction.emoji == self.emoji:
                    async for user in reaction.users():
                        is_bot = user.id == self.user.id
                        is_member = isinstance(user, nextcord.Member)  # ignore users who left the server
                        is_lightkeeper = self.lightkeeper_role in user.roles
                        if not is_bot and is_member and not is_lightkeeper:
                            log("Adding missing role to {}".format(user.name))
                            await user.add_roles(self.lightkeeper_role)

    async def on_ready(self):
        if LIGHTKEEPER_ROLE_EMOJI in db.keys():
            self.emoji = nextcord.PartialEmoji.from_str(db[LIGHTKEEPER_ROLE_EMOJI])
            log("emoji set from db: {}".format(self.emoji))

        if STATUS_CHANNEL in db.keys():
            self.status_channel = self.get_channel(db[STATUS_CHANNEL])
            log("channel set from db: {}".format(self.status_channel))
            if LIGHTKEEPER_ROLE in db.keys():
                self.lightkeeper_role = nextcord.utils.get(bot.status_channel.guild.roles, id=db[LIGHTKEEPER_ROLE])
                log("light keeper role set from db: {}".format(self.lightkeeper_role))
            if STATUS_MESSAGE in db.keys():
                try:
                    self.status_message = await self.status_channel.fetch_message(db[STATUS_MESSAGE])
                    log("message set from db: {}".format(self.status_message))
                except (nextcord.errors.NotFound, KeyError):
                    pass

        if ALERT_TIME in db.keys():
            log("alert time set from db: {}".format(db[ALERT_TIME]))

        self.__fix_roles()

        if FAILED not in db.keys():
            db[FAILED] = False
        elif not db[FAILED]:
            now = datetime.datetime.today().replace(microsecond=0)
            if now > start_date:
                log("Restarting ongoing event")
                self.timer_update.start()

    @tasks.loop(seconds=update_interval)
    async def timer_update(self):
        now = datetime.datetime.today().replace(microsecond=0)
        if db[FAILED]:
            self.timer_update.stop()
            log("Event failed")
            status = "FAILED"
        elif now >= end_date:
            self.timer_update.stop()
            log("Event won")
            status = "WON"
        else:
            status = "ONGOING"

        embed = nextcord.Embed(title="Basin timers")
        for city in cities:
            last_update, alert, pm = db[city]
            time_diff = now - datetime.datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%S")
            two_hours = datetime.timedelta(hours=2)
            time_left = two_hours - time_diff
            str_time = str(time_left).split('.')[0]

            if time_left < datetime.timedelta(0):
                db[FAILED] = True
                str_time = "```[0:00:00]```"
            elif db[ALERT_TIME] > 0 and time_left < datetime.timedelta(minutes=db[ALERT_TIME]):
                message = "{} basin is burning out!".format(city)
                if alert:
                    alert = False
                    log(message)
                    await self.status_channel.send(content="{} {}".format(self.lightkeeper_role.mention, message))
                    str_time = '```http\n[{}]```'.format(str_time)
                if pm and time_left < datetime.timedelta(minutes=int(db[ALERT_TIME]/2)):
                    log("{} Sending PM to Lightkeepers".format(message))
                    pm = False
                    str_time = '```css\n[{}]```'.format(str_time)
                    for user in self.lightkeeper_role.members:
                        await user.send("{} {} Only 10 minutes left!".format(user.mention, message))
                db[city] = (last_update, alert, pm)
            else:
                str_time = '```ini\n[{}]```'.format(str_time)
            embed.add_field(name=city, value=str_time, inline=True)
        embed.add_field(name="Lightkeepers", value="{}".format(len(self.lightkeeper_role.members)), inline=True)
        embed.add_field(name="Event status", value="{}".format(status), inline=True)
        if bot.emoji is not None:
            embed.add_field(name="NOTIFICATIONS",
                            value="To join {} leave reaction {}".format(self.lightkeeper_role.mention, bot.emoji))
        try:
            await self.status_message.edit(embed=embed)
        except (nextcord.errors.NotFound, KeyError):
            self.status_message = await self.status_channel.send(embed=embed)
            db[STATUS_MESSAGE] = self.status_message.id

    @timer_update.before_loop
    async def before_timer_update(self):
        await self.wait_until_ready()

    async def on_raw_reaction_add(self, payload: nextcord.RawReactionActionEvent):
        if self.user.id == payload.member.id:
            return

        if self.emoji is None or payload.message_id != self.status_message.id:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            return

        if self.lightkeeper_role is None:
            return

        try:
            await payload.member.add_roles(self.lightkeeper_role)
            log("Adding {} {} role".format(payload.member.name, self.lightkeeper_role.name))
            if not self.timer_update.is_running():
                await prepareForEvent(None)
        except nextcord.HTTPException:
            log("Cannot manage roles")
            pass

    async def on_raw_reaction_remove(self, payload: nextcord.RawReactionActionEvent):
        if self.emoji is None or payload.message_id != self.status_message.id:
            return

        guild = self.get_guild(payload.guild_id)
        if guild is None:
            return

        if self.lightkeeper_role is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            return

        if self.user.id == member.id:
            return

        try:
            await member.remove_roles(self.lightkeeper_role)
            log("Removing {} role from {}".format(self.lightkeeper_role.name, member.name))
            if not self.timer_update.is_running():
                await prepareForEvent(None)
        except nextcord.HTTPException:
            log("Cannot manage roles")
            pass


intents = nextcord.Intents.default()  # Allow the use of custom intents
intents.members = True
intents.message_content = True
bot = LightbearerBot(command_prefix="/", case_insensitive=True, intents=intents)


def does_intersect(lst1, lst2):
    temp = set(lst2)
    lst3 = [value for value in lst1 if value in temp]
    return len(lst3)


async def set_basin_timer(channel, city, reset_time):
    db[city] = (reset_time.isoformat(), True, True)
    async for message in channel.history(limit=10):
        if city in message.content:
            await message.delete()


@bot.slash_command(name="lit",
                   description="Reset basin timer",
                   guild_ids=[int(GUILD_ID)])
async def lit(interaction: Interaction,
              city: str = SlashOption(name="city",
                                      description="Basin location",
                                      choices=city_options,
                                      required=True,
                                      verify=True)):
    await interaction.response.defer()
    log('{} called /lit city:{}'.format(interaction.user.name, city))
    if not bot.timer_update.is_running():
        log('But the event has not started yet.')
        await interaction.followup.send('{}, the event has not started yet.'.format(interaction.user.name))
        return
    now = datetime.datetime.today().replace(microsecond=0)
    if city == all_cities:
        for c in cities:
            db[c] = (now.isoformat(), True, True)
            log("{} timer set to {}".format(c, "2:00"))
        async for message in bot.status_channel.history(limit=10):
            if any(c in message.content for c in cities):
                await message.delete()
        embed = nextcord.Embed(title="All basins have been renewed!")
    else:
        await set_basin_timer(bot.status_channel, city, now)
        log("{} timer set to {}".format(city, "2:00"))
        embed = nextcord.Embed(title="{} basin has been renewed!".format(city))
    await interaction.followup.send(embed=embed)


@bot.slash_command(name="time",
                   description="Set basin timer",
                   guild_ids=[int(GUILD_ID)])
async def time(interaction: Interaction,
               city: str = SlashOption(name="city",
                                       description="Basin location",
                                       choices=cities,
                                       required=True,
                                       verify=True),
               timer: str = SlashOption(name="timer",
                                        description="Basin timer. Time must be provided in HH:MM format (max. 2:00).",
                                        required=True,
                                        verify=True)):
    await interaction.response.defer()
    log('{} called /time city:{} timer:{}'.format(interaction.user.name, city, timer))
    if not bot.timer_update.is_running():
        log('But the event has not started yet.')
        await interaction.followup.send('{}, the event has not started yet.'.format(interaction.user.name))
        return
    basin_time = timer.split(":")
    try:
        hours = int(basin_time[0])
        minutes = int(basin_time[1])
        if hours < 0 or hours > 2 or minutes < 0 or minutes > 59 or (hours == 2 and minutes != 0):
            raise ValueError("Invalid time format")
        time_left = datetime.timedelta(hours=2) - datetime.timedelta(hours=hours, minutes=minutes)
        await set_basin_timer(bot.status_channel, city, (datetime.datetime.today().replace(microsecond=0) - time_left))
        log("{} timer set to {}".format(city, timer))
        embed = nextcord.Embed(title="{} timer set to {}".format(city, timer))
        await interaction.followup.send(embed=embed)
    except (ValueError, IndexError):
        log('Invalid time format "{}", should be HH:MM (max. 2:00)'.format(timer))
        await interaction.followup.send('Invalid time format "{}", should be HH:MM (max. 2:00)'.format(timer))


@bot.command(name="commands",
             guild_ids=[int(GUILD_ID)])
async def commands(ctx):
    embed = nextcord.Embed(title="Bot slash commands")
    embed.add_field(name="/lit city:[city]",
                    value="Reset basin timer\n"
                          "/lit city:All resets timers for all basins.\n"
                          "Note: Only Time Guardians can use this command.\n"
                          "e.g. /lit city:Edron",
                    inline=False)
    embed.add_field(name="/time city:[city] timer:[time]",
                    value="Set basin timer\n"
                          "Time must be provided in HH:MM format\n"
                          "Note: Only Time Guardians can use this command.\n"
                          "e.g. /time city:Edron timer:1:43",
                    inline=False)
    await ctx.send(embed=embed)


@bot.command(name="start",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def start(ctx):
    log('{} called /start'.format(ctx.message.author.name))
    if bot.timer_update.is_running():
        log('The event is already running.')
        await ctx.send('{}, the event is already running.'.format(ctx.message.author.name))
        return
    if {LIGHTKEEPER_ROLE, STATUS_CHANNEL, ALERT_TIME}.issubset(db.keys()):
        log("Start timer!")
        now = datetime.datetime.today().replace(microsecond=0)
        for city in cities:
            db[city] = (now.isoformat(), True, True)
            log("{} timer set to {}".format(city, "2:00"))
        async for message in bot.status_channel.history(limit=10):
            if any(city in message.content for city in cities):
                await message.delete()
        db[FAILED] = False
        bot.timer_update.start()
        await ctx.send("Starting the event")
    else:
        log("You need to setup bot first: lightkeeperRole, timeGuardianRole, statusChannel, alertTime")
        await ctx.send("You need to setup bot first: lightkeeperRole, timeGuardianRole, statusChannel, alertTime")


@bot.command(name="stop",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def stop(ctx):
    log('{} called /stop'.format(ctx.message.author.name))
    bot.timer_update.stop()
    log("Stopping the event")
    await ctx.send("Stopping the event")


@bot.command(name="restart",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def restart(ctx):
    log('{} called /restart'.format(ctx.message.author.name))
    if set(cities).issubset(db.keys()):
        log("Restarting the event")
        await ctx.send("Restarting the event")
        db[FAILED] = False
        now = datetime.datetime.today().replace(microsecond=0)
        for city in cities:
            last_update, _, _ = db[city]
            time_diff = now - datetime.datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%S")

            if time_diff > datetime.timedelta(hours=2):
                await set_basin_timer(bot.status_channel, city, now)
                log("{} timer needs to be fixed".format(city))
                await ctx.send("{} timer needs to be fixed".format(city))
        bot.timer_update.start()
    else:
        log("Cannot restart the event that has not started yet")
        await ctx.send("Cannot restart the event that has not started yet")


@bot.command(name="reset",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def reset(ctx):
    log('{} called /reset'.format(ctx.message.author.name))
    bot.timer_update.stop()
    for key in db.keys():
        del db[key]
    bot.lightkeeper_role = None
    bot.emoji = None
    bot.status_message = None
    bot.status_channel = None
    log("Hard reset. All settings have been removed.")
    await ctx.send("Hard reset. All settings have been removed.")


@bot.command(name="soft_reset",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def soft_reset(ctx):
    log('{} called /soft_reset'.format(ctx.message.author.name))
    for key in db.keys():
        if key not in [LIGHTKEEPER_ROLE, LIGHTKEEPER_ROLE_EMOJI, STATUS_CHANNEL, ALERT_TIME, STATUS_MESSAGE]:
            del db[key]
    db[FAILED] = False
    log("Soft reset (timers only)")
    await ctx.send("Soft reset (timers only)")


@bot.command(name="prepareForEvent",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def prepareForEvent(ctx):
    if ctx is not None:
        log('{} called /prepareForEvent'.format(ctx.message.author.name))
    embed = nextcord.Embed(title="Basin timers")
    for city in cities:
        embed.add_field(name=city, value='```ini\n[-:--:--]```', inline=True)
    embed.add_field(name="Lightkeepers", value="{}".format(len(bot.lightkeeper_role.members)), inline=True)
    now = datetime.datetime.today().replace(microsecond=0)
    if db[FAILED]:
        status = "FAILED"
    elif now >= end_date:
        status = "WON"
    else:
        status = "PENDING"
    embed.add_field(name="Event status", value=status, inline=True)
    if bot.emoji is not None:
        embed.add_field(name="NOTIFICATIONS",
                        value="To join {} leave reaction {}".format(bot.lightkeeper_role.mention, bot.emoji))
    try:
        await(await bot.status_channel.fetch_message(db[STATUS_MESSAGE])).edit(embed=embed)
    except (nextcord.errors.NotFound, KeyError):
        bot.status_message = await bot.status_channel.send(embed=embed)
        db[STATUS_MESSAGE] = bot.status_message.id
        if bot.emoji is not None:
            await bot.status_message.add_reaction(bot.emoji)
    log("Prepared status message on {}".format(bot.status_channel.mention))
    if ctx is not None:
        await ctx.send("Prepared status message on {}".format(bot.status_channel.mention))


@bot.command()
@has_permissions(administrator=True)
async def lightkeeperRole(ctx):
    log('{} called /lightkeeperRole'.format(ctx.message.author.name))
    roles = ctx.message.role_mentions
    if len(roles) == 1:
        bot.lightkeeper_role = roles[0]
        db[LIGHTKEEPER_ROLE] = bot.lightkeeper_role.id
        log("Setting Lightkeeper role: '{}'".format(bot.lightkeeper_role.name))
        await ctx.send("Setting Lightkeeper role: '{}'".format(bot.lightkeeper_role.name))
    elif roles:
        log("/lightkeeperRole - Too many roles have been mentioned: {}".format([role.name for role in roles]))
        await ctx.send("Please mention only one role")
    else:
        log("/lightkeeperRole - None role has been mentioned")
        await ctx.send("Please mention Lightkeeper role")


@bot.command()
@has_permissions(administrator=True)
async def lightkeeperEmoji(ctx):
    log('{} called /lightkeeperEmoji'.format(ctx.message.author.name))
    db[LIGHTKEEPER_ROLE_EMOJI] = ctx.message.content[1 + len("lightkeeperEmoji "):]
    bot.emoji = nextcord.PartialEmoji.from_str(db[LIGHTKEEPER_ROLE_EMOJI])
    log("Setting Lightkeeper emoji: '{}'".format(db[LIGHTKEEPER_ROLE_EMOJI]))
    await ctx.send("Lightkeeper emoji: '{}'".format(db[LIGHTKEEPER_ROLE_EMOJI]))
    if bot.status_message is not None:
        log("Adding reaction to the status message")
        await bot.status_message.add_reaction(bot.emoji)
        await prepareForEvent(None)


@bot.command()
@has_permissions(administrator=True)
async def statusChannel(ctx):
    log('{} called /statusChannel'.format(ctx.message.author.name))
    channels = ctx.message.channel_mentions
    if len(channels) == 1:
        bot.status_channel = channels[0]
        db[STATUS_CHANNEL] = bot.status_channel.id
        log("Setting status channel: {}(id: {})".format(bot.status_channel.name, bot.status_channel.id))
        await ctx.send("Setting status channel: {}".format(bot.status_channel.name))
    elif channels:
        log("/statusChannel - Too many channels have been mentioned: {}".format([channel.name for channel in channels]))
        await ctx.send("Please mention only one channel")
    else:
        log("/statusChannel - None channel has been mentioned")
        await ctx.send("Please mention status channel")


@bot.command(name="alertTime",
             guild_ids=[int(GUILD_ID)])
@has_permissions(administrator=True)
async def alertTime(ctx):
    log('{} called /alertTime'.format(ctx.message.author.name))
    alert_time = ctx.message.content[len("alertTime ") + 1:]
    try:
        db[ALERT_TIME] = int(alert_time)
        log("Set alert time: {}".format(db[ALERT_TIME]))
        await ctx.send("Set alert time: {}".format(db[ALERT_TIME]))
    except ValueError:
        log('Invalid time format "{}", should be MM'.format(alert_time))
        await ctx.send("Invalid time format, should be: MM")


@alertTime.error
@statusChannel.error
@lightkeeperEmoji.error
@lightkeeperRole.error
@prepareForEvent.error
@restart.error
@soft_reset.error
@reset.error
@stop.error
@start.error
async def error(ctx, _):
    await ctx.send('You have no permission to use that command')

bot.run(TOKEN)
