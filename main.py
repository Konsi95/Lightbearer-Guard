import os
import discord
import datetime
from discord.ext import commands, tasks
from discord.ext.commands import has_permissions
from discord.utils import get
from replit import db

prefix = "$"
end = datetime.datetime(2021, 11, 15, 9, 00)
cities = ["Svargrond", "PoH", "Forbidden Lands", "Kazordoon", "Ramoa", "Edron", "Drefia", "Hellgate", "Ankrahmun", "Yalahar"]
cities_str = " - " + "\n - ".join(cities)

lightkeeper_role_name = "lightkeeper_role_name"
status_channel_name = "status_channel_name"
status_message_name = "status_message_name"
alert_time_name = "alert_time_name"
failed = "failed"

bot = commands.Bot(command_prefix=prefix)

async def resettimer(city, update_time, channel):
  db[city] = (update_time.isoformat(), True)
  async for message in channel.history(limit=10):
    if "{}'s".format(city) in message.content:
      await message.delete()

@bot.command()
async def commands(ctx):
  embed = discord.Embed(title="Bot commands")
  embed.add_field(name="{}join".format(prefix), value="Join Lightkeepers to receive notifications about burning out locations", inline=False)
  embed.add_field(name="{}leave".format(prefix), value="Leave Lightkeepers", inline=False)
  embed.add_field(name="{}light [city]".format(prefix), value="Reset basin timer", inline=False)
  embed.add_field(name="{}setTimer [city] [time]".format(prefix), value="Set basin timer\nTime must be provided in HH:MM format", inline=False)
  embed.add_field(name="Cities:", value=cities_str, inline=False)
  await ctx.send(embed=embed)

@bot.command()
async def join(ctx):
  member = ctx.message.author
  role = get(member.guild.roles, id=db[lightkeeper_role_name])
  if not role in member.roles:
    await member.add_roles(role)
    await ctx.send("{} is our new Lightkeeper!".format(member.mention))

@bot.command()
async def leave(ctx):
  member = ctx.message.author
  role = get(member.guild.roles, id=db[lightkeeper_role_name])
  if role in member.roles:
    await member.remove_roles(role)

@bot.command()
async def light(ctx):
  message = ctx.message
  city = message.content[len(prefix) + len("light "):]
  if city in cities:
    await resettimer(city, datetime.datetime.today().replace(microsecond=0), bot.get_channel(db[status_channel_name]))
    print("{}'s timer set to {}".format(city, "2:00"))
    embed = discord.Embed(title="{}'s basin has been renewed!".format(city))
    await ctx.send(embed=embed)
  else:
    await ctx.send('Invalid city: {}'.format(city))

@bot.command()
async def setTimer(ctx):
  message = ctx.message
  data = message.content[len(prefix) + len("setTimer "):].split(" ")
  city = " ".join(data[:-1])
  if city in cities:
    basin_time = data[-1].split(":")
    try:
      time_left = datetime.timedelta(hours=2) - datetime.timedelta(hours=int(basin_time[0]), minutes=int(basin_time[1]))
      db[city] = ((datetime.datetime.today().replace(microsecond=0) - time_left).isoformat(), True)
      print("{}'s timer set to {}".format(city, data[-1]))
      await ctx.send("{}'s timer set to {}".format(city, data[-1]))
    except:
      print('Invalid time format "{}", should be HH:MM'.format(city, data[-1]))
      await ctx.send('Invalid time format "{}", should be HH:MM'.format(city, data[-1]))
  else:
    print('City "{}" not found'.format(city))
    await ctx.send('City "{}" not found'.format(city))

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
  for i in range(0, len(cities)):
    city = cities[i]
    last_update, alert = db[city]
    time_diff = now - datetime.datetime.strptime(last_update, "%Y-%m-%dT%H:%M:%S")
    two_hours = datetime.timedelta(hours=2)
    time_left = two_hours - time_diff
    str_time = str(time_left).split('.')[0]
      
    if time_left < datetime.timedelta(minutes=db[alert_time_name]):
      if alert:
        db[city] = (last_update, False)
        await status_channel.send(content="{} {}'s basin is burning out!".format(light_keeper_role.mention, city))
      if time_left < datetime.timedelta(0):
        db[failed] = True
        str_time = "0:00:00"
      str_time = '''```css\n[{}]```'''.format(str_time)
    else:
      str_time = '''```ini\n[{}]```'''.format(str_time)
    embed.add_field(name=city, value=str_time, inline=True)
  embed.add_field(name="Light Keepers", value="{}".format(len(light_keeper_role.members)), inline=True)
  embed.add_field(name="Event status", value="{}".format(status), inline=True)
  try:
    await (await status_channel.fetch_message(db[status_message_name])).edit(embed=embed)
  except (discord.errors.NotFound, KeyError):
    db[status_message_name] = (await status_channel.send(embed=embed)).id

@bot.command()
@has_permissions(administrator=True)
async def start(ctx):
  if set([lightkeeper_role_name, status_channel_name, alert_time_name]).issubset(db.keys()):
    print("Start timer!")
    db[failed] = False
    now = datetime.datetime.today().replace(microsecond=0)
    for city in cities:
      await resettimer(city, now, bot.get_channel(db[status_channel_name]))
    timerUpdate.start()
  else:
    print("You need to setup bot first!")
    await ctx.send("You need to setup bot first!")

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
async def setRole(ctx):
  roles = ctx.message.role_mentions
  if len(roles) == 1:
    print("Setting Light Keeper role: '{}'".format(roles[0].name))
    db[lightkeeper_role_name] = roles[0].id
  else:
    print("Invalid role")

@bot.command()
@has_permissions(administrator=True)
async def setChannel(ctx):
  channels = ctx.message.channel_mentions
  if len(channels) == 1:
    db[status_channel_name] = channels[0].id
    print("Status channel: {}(id: {})".format(channels[0].name, channels[0].id))
  else:
    print("Invalid syntax")

@bot.command()
@has_permissions(administrator=True)
async def setAlertTime(ctx):
  try:
    alertTime = int(ctx.message.content[len(prefix) + len("setAlertTime "):])
    db[alert_time_name] = alertTime
    print("Set alert time: {}".format(alertTime))
  except:
    print("Invalid format")

@setAlertTime.error
@setChannel.error
@setRole.error
@restart.error
@stop.error
@start.error
async def error(error, ctx):
  pass

bot.run(os.environ['TOKEN'])