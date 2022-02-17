import os
import discord
import datetime
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.utils import get
from sqlitedict import SqliteDict

db = SqliteDict('./db.sqlite', autocommit=True)
prefix = "$"
end = datetime.datetime(2021, 11, 15, 10, 00)
cities = ["svargrond", "plains of havoc", "forbidden lands", "kazordoon", "ramoa", "edron", "drefia", "hellgate",
          "ankrahmun", "yalahar"]
cities_str = " - " + "\n - ".join(city.title() for city in cities)

lightkeeper_role_name = "lightkeeper_role"
time_guardian_role_name = "time_guardian_role"
status_channel_name = "status_channel"
status_message_name = "status_message"
alert_time_name = "alert_time"
failed = "failed"

intents = discord.Intents.default()  # Allow the use of custom intents
intents.members = True
bot = commands.Bot(command_prefix=prefix, case_insensitive=True, intents=intents)


def doesIntersect(lst1, lst2):
    temp = set(lst2)
    lst3 = [value for value in lst1 if value in temp]
    return len(lst3)


@bot.command()
async def commands(ctx):
    embed = discord.Embed(title="Bot commands")
    embed.add_field(name="{}join".format(prefix),
                    value="Join Lightkeepers to receive notifications about burning out basins", inline=False)
    embed.add_field(name="{}leave".format(prefix), value="Leave Lightkeepers", inline=False)
    embed.add_field(name="{}lit [city]".format(prefix),
                    value="Reset basin timer\nNote: Only Time Guardians can use this command.\ne.g. {}lit Edron".format(
                        prefix), inline=False)
    embed.add_field(name="{}time [city] [time]".format(prefix),
                    value="Set basin timer\nTime must be provided in HH:MM format\nNote: Only Time Guardians can use this command.\ne.g. {}time Edron 1:43".format(
                        prefix), inline=False)
    embed.add_field(name="Cities:",
                    value=cities_str + "\nYou can also use any unequivocal abbreviation (e.g. PoH = Plains of Havoc, Svar = Svargrond, Kaz = Kazordoon, ed = Edron)",
                    inline=False)
    await ctx.send(embed=embed)


@bot.command()
async def join(ctx):
    member = ctx.message.author
    role = get(member.guild.roles, id=db[lightkeeper_role_name])
    if role not in member.roles:
        await member.add_roles(role)
        await ctx.send("{} is our new Lightkeeper!".format(member.mention))
    else:
        await ctx.send("{}, you are already among the Lightkeepers".format(member.mention))
    if not timerUpdate.is_running():
        await prepareForEvent(ctx)


@bot.command()
async def leave(ctx):
    member = ctx.message.author
    role = get(member.guild.roles, id=db[lightkeeper_role_name])
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send("{} is no longer a Lightkeeper".format(member.mention))
    if not timerUpdate.is_running():
        await prepareForEvent(ctx)


@bot.command()
async def lit(ctx):
    if not timerUpdate.is_running():
        print('{}, the event has not started yet.'.format(ctx.message.author.name))
        await ctx.send('{}, the event has not started yet.'.format(ctx.message.author.name))
        return
    message = ctx.message
    if not doesIntersect([role.id for role in message.author.roles], db[time_guardian_role_name]):
        await ctx.send('You have no permission to use that command')
        return
    location = message.content[len(prefix) + len("lit "):].lower()
    if location == "poh":
        location = "plains of havoc"
    channel = bot.get_channel(db[status_channel_name])
    now = datetime.datetime.today().replace(microsecond=0)
    applicable_cities = [city for city in cities if location in city]
    if applicable_cities:
        if len(applicable_cities) == 1:
            location = applicable_cities[0]
            db[location] = (now.isoformat(), True)
            async for message in channel.history(limit=10):
                if "{}".format(location.title()) in message.content:
                    await message.delete()
            print("{} timer set to {}".format(location.title(), "2:00"))
            embed = discord.Embed(title="{} basin has been renewed!".format(location.title()))
            await ctx.send(embed=embed)
        else:
            print('Be more precise. Too many possible cities: {}'.format(
                ', '.join(city.title() for city in applicable_cities)))
            await ctx.send('Be more precise. Too many possible cities: {}'.format(
                ', '.join(city.title() for city in applicable_cities)))
    elif location == "all":
        for city in cities:
            db[city] = (now.isoformat(), True)
        async for message in channel.history(limit=10):
            if any(city in message.content for city in cities):
                await message.delete()
        print("All timers set to 2:00")
        embed = discord.Embed(title="All basins have been renewed!")
        await ctx.send(embed=embed)
    else:
        print('Invalid city: {}'.format(location))
        await ctx.send('Invalid city: {}'.format(location))


@bot.command()
async def time(ctx):
    if not timerUpdate.is_running():
        print('{}, the event has not started yet.'.format(ctx.message.author.name))
        await ctx.send('{}, the event has not started yet.'.format(ctx.message.author.name))
        return
    message = ctx.message
    data = message.content[len(prefix) + len("time "):].split(" ")
    location = " ".join(data[:-1]).lower()
    if location == "poh":
        location = "plains of havoc"
    applicable_cities = [city for city in cities if location in city]
    if applicable_cities:
        if len(applicable_cities) == 1:
            location = applicable_cities[0]
            basin_time = data[-1].split(":")
            try:
                channel = bot.get_channel(db[status_channel_name])
                time_left = datetime.timedelta(hours=2) - datetime.timedelta(hours=int(basin_time[0]),
                                                                             minutes=int(basin_time[1]))
                db[location] = ((datetime.datetime.today().replace(microsecond=0) - time_left).isoformat(), True)
                print("{} timer set to {}".format(location.title(), data[-1]))
                embed = discord.Embed(title="{} timer set to {}".format(location.title(), data[-1]))
                await ctx.send(embed=embed)
                async for message in channel.history(limit=10):
                    if "{}".format(location.title()) in message.content:
                        await message.delete()
            except:
                print('Invalid time format "{}", should be HH:MM'.format(location.title(), data[-1]))
                await ctx.send('Invalid time format "{}", should be HH:MM'.format(location.title(), data[-1]))
        else:
            print('Be more precise. Too many possible cities: {}'.format(
                ', '.join(city.title() for city in applicable_cities)))
            await ctx.send('Be more precise. Too many possible cities: {}'.format(
                ', '.join(city.title() for city in applicable_cities)))
    else:
        print('Invalid city: {}'.format(location))
        await ctx.send('Invalid city: {}'.format(location))


@tasks.loop(seconds=1.0)
async def timerUpdate():
    now = datetime.datetime.today().replace(microsecond=0)
    if db[failed]:
        timerUpdate.stop()
        status = "FAILED"
    elif now >= end:
        timerUpdate.stop()
        status = "WON"
    else:
        status = "ONGOING"

    status_channel = bot.get_channel(db[status_channel_name])
    light_keeper_role = get(status_channel.guild.roles, id=db[lightkeeper_role_name])
    embed = discord.Embed(title="Basin timers")
    for city in cities:
        last_update, alert = db[city]
        time_diff = now - datetime.datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%S")
        two_hours = datetime.timedelta(hours=2)
        time_left = two_hours - time_diff
        str_time = str(time_left).split('.')[0]

        if time_left < datetime.timedelta(minutes=db[alert_time_name]):
            if alert:
                db[city] = (last_update, False)
                await status_channel.send(
                    content="{} {} basin is burning out!".format(light_keeper_role.mention, city.title()))
            if time_left < datetime.timedelta(0):
                db[failed] = True
                str_time = "0:00:00"
            str_time = '```css\n[{}]```'.format(str_time)
        else:
            str_time = '```ini\n[{}]```'.format(str_time)
        embed.add_field(name=city.title(), value=str_time, inline=True)
    embed.add_field(name="Lightkeepers", value="{}".format(len(light_keeper_role.members)), inline=True)
    embed.add_field(name="Event status", value="{}".format(status), inline=True)
    try:
        await(await status_channel.fetch_message(db[status_message_name])).edit(embed=embed)
    except (discord.errors.NotFound, KeyError):
        db[status_message_name] = (await status_channel.send(embed=embed)).id


@bot.command()
@has_permissions(administrator=True)
async def start(ctx):
    if set([lightkeeper_role_name, time_guardian_role_name, status_channel_name, alert_time_name]).issubset(db.keys()):
        print("Start timer!")
        db[failed] = False
        now = datetime.datetime.today().replace(microsecond=0)
        for city in cities:
            db[city] = (now.isoformat(), True)
        async for message in bot.get_channel(db[status_channel_name]).history(limit=10):
            if any(city in message.content for city in cities):
                await message.delete()
        timerUpdate.start()
    else:
        print("You need to setup bot first: lightkeeperRole, timeGuardianRole, statusChannel, alertTime")
        await ctx.send("You need to setup bot first: lightkeeperRole, timeGuardianRole, statusChannel, alertTime")


@bot.command()
@has_permissions(administrator=True)
async def stop(ctx):
    timerUpdate.stop()


@bot.command()
@has_permissions(administrator=True)
async def restart(ctx):
    timerUpdate.start()


@bot.command()
@has_permissions(administrator=True)
async def reset(ctx):
    for key in db.keys():
        del db[key]


@bot.command()
@has_permissions(administrator=True)
async def softreset(ctx):
    for key in db.keys():
        if key not in [lightkeeper_role_name, time_guardian_role_name, status_channel_name, alert_time_name,
                       status_message_name]:
            del db[key]


@bot.command()
@has_permissions(administrator=True)
async def prepareForEvent(ctx):
    status_channel = bot.get_channel(db[status_channel_name])
    light_keeper_role = get(status_channel.guild.roles, id=db[lightkeeper_role_name])
    embed = discord.Embed(title="Basin timers")
    for city in cities:
        embed.add_field(name=city.title(), value='```ini\n[-:--:--]```', inline=True)
    embed.add_field(name="Lightkeepers", value="{}".format(len(light_keeper_role.members)), inline=True)
    embed.add_field(name="Event status", value="PENDING", inline=True)
    try:
        await(await status_channel.fetch_message(db[status_message_name])).edit(embed=embed)
    except (discord.errors.NotFound, KeyError):
        db[status_message_name] = (await status_channel.send(embed=embed)).id


@bot.command()
@has_permissions(administrator=True)
async def lightkeeperRole(ctx):
    roles = ctx.message.role_mentions
    if len(roles) == 1:
        print("Setting Lightkeeper role: '{}'".format(roles[0].name))
        await ctx.send("Setting Lightkeeper role: '{}'".format(roles[0].name))
        db[lightkeeper_role_name] = roles[0].id
    elif roles:
        print("Please mention only one role")
        await ctx.send("Please mention only one role")
    else:
        print("Please mention Lightkeeper role")
        await ctx.send("Please mention Lightkeeper role")


@bot.command()
@has_permissions(administrator=True)
async def timeGuardianRole(ctx):
    roles = ctx.message.role_mentions
    if roles:
        print("Setting Time Guardian roles: {}".format(', '.join(role.name for role in roles)))
        await ctx.send("Setting Time Guardian roles: {}".format(', '.join(role.name for role in roles)))
        db[time_guardian_role_name] = [role.id for role in roles]
    else:
        print("Please mention Time Guardian role")
        await ctx.send("Please mention Time Guardian role")


@bot.command()
@has_permissions(administrator=True)
async def statusChannel(ctx):
    channels = ctx.message.channel_mentions
    if len(channels) == 1:
        db[status_channel_name] = channels[0].id
        print("Setting status channel: {}(id: {})".format(channels[0].name, channels[0].id))
        await ctx.send("Setting status channel: {}".format(channels[0].name))
    elif channels:
        print("Please mention only one channel")
        await ctx.send("Please mention only one channel")
    else:
        print("Please mention status channel")
        await ctx.send("Please mention status channel")


@bot.command()
@has_permissions(administrator=True)
async def alertTime(ctx):
    try:
        alertTime = int(ctx.message.content[len(prefix) + len("alertTime "):])
        db[alert_time_name] = alertTime
        print("Set alert time: {}".format(alertTime))
        await ctx.send("Set alert time: {}".format(alertTime))
    except:
        print("Invalid time format, should be: MM")
        await ctx.send("Invalid time format, should be: MM")


@bot.command()
@has_permissions(administrator=True)
async def dumpDB(ctx):
    for key in db.keys():
        print("{}={}".format(key, db[key]))
        await ctx.send("{}={}".format(key, db[key]))


def parseValue(dbValue):
    if dbValue == "True":
        return True
    elif dbValue == "False":
        return False
    elif dbValue.isnumeric():
        return int(dbValue)
    elif dbValue[0] == "'":
        return dbValue[1:-1]
    else:
        return dbValue


def parseList(dbValue):
    return [parseValue(val) for val in dbValue[1:-1].split(", ")]


def parseTuple(dbValue):
    return tuple(parseValue(val) for val in dbValue[1:-1].split(", "))


def parse(dbValue):
    if dbValue[0] == '[':
        return parseList(dbValue)
    elif dbValue[0] == '(':
        return parseTuple(dbValue)
    else:
        return parseValue(dbValue)


@bot.command()
@has_permissions(administrator=True)
async def loadDB(ctx):
    content = ctx.message.content
    for line in content[len(prefix) + len("loadDB") + 1:].split("\n"):
        key, value = line.split("=")
        db[key] = parse(value)
        print("SAVED: {} = {}".format(key, db[key]))


@loadDB.error
@dumpDB.error
@alertTime.error
@statusChannel.error
@lightkeeperRole.error
@timeGuardianRole.error
@prepareForEvent.error
@restart.error
@softreset.error
@reset.error
@stop.error
@start.error
async def error(error, ctx):
    await ctx.send('You have no permission to use that command')


bot.run(os.environ['TOKEN'])
