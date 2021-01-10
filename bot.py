import asyncio
import discord
import os
import time
import threading
from collections import defaultdict
from discord.ext import commands

# get token from environment vars or secrets file
if 'token' not in os.environ:
  from secrets import token
else:
  token = os.environ['token']

bot = commands.Bot(command_prefix='!')

# each guild can have multiple threads for each user being mooved
# guild -> moov threads
threads_in_guild = defaultdict(lambda: [])

# used to make sure a member cannot be mooved by multiple threads
# guild -> members being mooved
members_mooving_in_guild = defaultdict(lambda: [])

@bot.command(name='moov')
async def moov_user(ctx, *args):
  if len(args) != 2:
    await ctx.send(f'Usage: !moov <@user> <times>')
    return
  times = int(args[1])

  if ctx.guild is None:
    return
  guild = ctx.guild

  # make sure author has permission to move users
  author = ctx.message.author
  if not author.guild_permissions.move_members:
    await ctx.send('You do not have permission to use this command')
    return
  
  # get target from mentions
  if len(ctx.message.mentions) != 1:
    await ctx.send(f'Usage: !moov <@user> <times>')
    return
  target = ctx.message.mentions[0]

  # make sure target is connected to a voice channel
  if target.voice.channel is None:
    await ctx.send(f'{args[0]} was not found, are you sure they\'re connected to a voice channel?')
    return
  
  # make sure target is not already being mooved
  if target in members_mooving_in_guild[guild]:
    await ctx.send(f'{args[0]} is already being moved.')
    return
  
  # get original channel to return target to
  original_channel = target.voice.channel
  
  # find all channels user has permission to connect to
  available_channels = []
  for vc in guild.voice_channels:
    if target.permissions_in(vc).connect:
      available_channels.append(vc)
  
  await ctx.send(f'Moving {args[0]} {times} times')

  # get event loop to allow thread to use asyncio
  moover_loop = asyncio.get_running_loop()

  # start thread to move user
  moov_thread = MooverThread(target, available_channels, original_channel, guild, times, moover_loop)
  moov_thread.start()

  # add thread to threads in guild dict and add target to members being moved
  threads_in_guild[guild].append(moov_thread)
  members_mooving_in_guild[guild].append(target)

@bot.command()
async def mstop(ctx):
  if ctx.guild is None:
    return
  guild = ctx.guild

  # stop all threads
  for thread in list(threads_in_guild[guild]):
    thread.stop()
    thread.join()

  # clear tracked threads and members being mooved
  threads_in_guild[guild] = []
  members_mooving_in_guild[guild] = []

  await ctx.send('Stopped')

class MooverThread(threading.Thread):
  def __init__(self, target, available_channels, original_channel, guild, times, moover_loop):
    super(MooverThread, self).__init__()
    self.stop_event = threading.Event()

    self.target = target
    self.available_channels = available_channels
    self.original_channel = original_channel
    self.guild = guild
    self.times = times
    self.loop = moover_loop
  
  def stop(self):
    self.stop_event.set()
  
  def run(self):
    # check that stop condition is not met
    while True:
      for channel in self.available_channels:
        self.times -= 1
        if self.times < 0 or self.stop_event.is_set():
          # move target to original channel
          asyncio.run_coroutine_threadsafe(self.target.move_to(self.original_channel, reason='moovr bot'), self.loop)

          # remove thread from dict
          threads_in_guild[self.guild].remove(self)
          return

        # move target to next channel
        asyncio.run_coroutine_threadsafe(self.target.move_to(channel, reason='moovr bot'), loop)
        time.sleep(1)

try:
  loop = asyncio.get_event_loop()
  loop.run_until_complete(bot.start(token))
except KeyboardInterrupt:
  loop.run_until_complete(bot.logout())
  # cancel all tasks lingering
finally:
  loop.close()
