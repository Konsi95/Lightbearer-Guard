import os
import discord
import datetime
from discord.ext import commands, tasks
from discord.utils import get

prefix = "$"
cities = ["Svargrond", "PoH", "Forbidden Lands", "Kazordoon", "Ramoa", "Edron", "Drefia", "Hellgate", "Ankrahmun", "Yalahar"]
cities_str = " - " + "\n - ".join(cities)

last_update = []
alert = []

announcement_message = None
light_keeper_role = None
failed = False

bot = commands.Bot(command_prefix=prefix)

@bot.command(pass_context=True)
async def register(ctx):
    member = ctx.message.author
    role = get(member.guild.roles, name="Light Keeper")
    if not role in member.roles:
      await member.add_roles(role)
      await ctx.send("{} is our new Light Keeper!".format(member.mention))

@bot.command(pass_context=True)
async def light(ctx):
  message = ctx.message
  city = message.content[len(prefix) + len("light "):]
  if city in cities:
    idx = cities.index(city)
    last_update[idx] = datetime.datetime.today().replace(microsecond=0)
    alert[idx] = True
    embed = discord.Embed(title="{}'s basin has been renewed!".format(city))
    await ctx.send(embed=embed)
  else:
    embed = discord.Embed(title="Usage", description="{}light [city]".format(prefix))
    embed.add_field(name="Available cities:", value=cities_str)
    await ctx.send(embed=embed)

@tasks.loop(seconds=1.0)
async def timerUpdate():
  global failed
  global announcement_message
  if failed:
    timerUpdate.cancel()
  if not announcement_message is None:
    global light_keeper_role
    embed = discord.Embed(title="Basin timers")
    now = datetime.datetime.today().replace(microsecond=0)
    for i in range(0, len(cities)):
      city = cities[i]
      time_diff = now - last_update[i]
      two_hours = datetime.timedelta(hours=2)
      time_left = two_hours - time_diff
      str_time = str(time_left).split('.')[0]
        
      if time_left < datetime.timedelta(minutes=10):
        if alert[i]:
          alert[i] = False
          await announcement_message.channel.send(content="{} {}'s basin is burning out!".format(light_keeper_role.mention, city))
        if time_left < datetime.timedelta(0):
          failed = True
          str_time = "0:00:00"
        str_time = '''```css\n[{}]```'''.format(str_time)
      else:
        str_time = '''```ini\n[{}]```'''.format(str_time)
      embed.add_field(name=city, value=str_time, inline=True)
    embed.add_field(name="Light Keepers", value="{}".format(len(light_keeper_role.members)), inline=True)
    embed.add_field(name="Event status", value="{}".format("FAILED" if failed else "ONGOING"), inline=True)
    try:
      await announcement_message.edit(embed=embed)
    except discord.errors.NotFound:
      announcement_message = await announcement_message.channel.send(embed=embed)

@bot.command(pass_context=True)
async def here(ctx):
  global last_update
  global alert
  last_update = [datetime.datetime.today().replace(microsecond=0) for _ in cities]
  alert = [True for _ in cities]
  embed = discord.Embed(title="Basin timers")
  [embed.add_field(name=city, value="0:00:00") for city in cities]
  global announcement_message
  announcement_message = await ctx.send(embed=embed)
  
  global light_keeper_role
  light_keeper_role = get(ctx.message.author.guild.roles, name="Light Keeper")
  timerUpdate.start()

@bot.command(pass_context=True)
async def setTimer(ctx):
  global last_update
  message = ctx.message
  data = message.content[len(prefix) + len("setTimer "):].split(" ")
  city = data[0]
  if city in cities:
    basin_time = data[1].split(":")
    idx = cities.index(city)
    time_left = datetime.timedelta(hours=2) - datetime.timedelta(hours=int(basin_time[0]), minutes=int(basin_time[1]))
    last_update[idx] = datetime.datetime.today().replace(microsecond=0) - time_left
    alert[idx] = True

bot.run(os.environ['TOKEN'])