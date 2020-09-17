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

threads_in_guild = defaultdict(lambda: [])

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

  # get all connected members
  connected_members = []
  for vc in guild.voice_channels:
    connected_members.extend(vc.members)
  
  # get target from mentions
  if len(ctx.message.mentions) != 1:
    await ctx.send(f'Usage: !moov <@user> <times>')
    return
  target = ctx.message.mentions[0]

  # make sure target is connected to a voice channel
  if target not in connected_members:
    await ctx.send(f'{args[0]} was not found, are you sure they\'re connected to a voice channel?')
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
  moov_thread = threading.Thread(target=moover, args=(target, available_channels, original_channel, guild, times, moover_loop), daemon=True)
  moov_thread.start()

  # add thread to guild to thread dict
  threads_in_guild[guild].append(moov_thread)

@bot.command()
async def mstop(ctx):
  if ctx.guild is None:
    return
  guild = ctx.guild

  # stop all threads
  for thread in threads_in_guild[guild]:
    thread.stop = True
    thread.join()

  # clear tracked threads
  threads_in_guild[guild] = []
  await ctx.send('Stopped')

def moover(target, channels, original_channel, guild, times, loop):
  # check that stop condition is not met
  t = threading.currentThread()
  while True:
    for channel in channels:
      times -= 1
      if times < 0 or getattr(t, "stop", False):
        # move target to original channel
        asyncio.run_coroutine_threadsafe(target.move_to(original_channel, reason='moovr bot'), loop)

        # remove thread from dict
        threads_in_guild[guild].remove(t)
        return

      # move target to next channel
      asyncio.run_coroutine_threadsafe(target.move_to(channel, reason='moovr bot'), loop)
      time.sleep(1)

bot.run(token)
