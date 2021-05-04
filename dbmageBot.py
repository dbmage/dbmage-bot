#!/usr/bin/python3
import sys
import docker
import aiocron
import discord
import sqlite3
import argparse
import logging as log
from glob import glob
from time import sleep
from random import randint
from lazylog import Logger
from shutil import copyfile
from datetime import datetime,timedelta
from json import loads as jloads
from os import path,getenv,system,execv
from subprocess import Popen, PIPE
from discord.ext import commands as dcomm

currentdir = path.dirname(path.abspath(__file__))
config = jloads(open("%s/config.json" % (currentdir)).read())
parser = argparse.ArgumentParser(description='DBMage discord bot')
parser.add_argument('-d', action='store_true', dest='dev', help='Run in dev mode')
args = parser.parse_args()

MODE = 'live'
config['logspecs']['filespecs']['level'] = getattr(log, config['logspecs']['filespecs']['level'], 'INFO')
if args.dev == True:
    MODE = 'dev'
    config['logspecs']['filespecs']['level'] = getattr(log, 'DEBUG')
# Set filename and init logger
config['logspecs']['filespecs']['filename'] = config['logspecs']['filespecs']['filename'].replace('%s', MODE)
Logger.init(config['logdir'], termSpecs=config['logspecs']['termspecs'], fileSpecs=[config['logspecs']['filespecs']])
# Set discord module logging
log.getLogger("discord").setLevel(log.WARNING)

TOKEN = config['tokens'][MODE]
DB = "%s/bot-%s.db" % (currentdir, MODE)
if len(TOKEN) < 1:
    print("Please set the bots TOKEN")
    log.error("No token in config")
    sys.exit(1)
DESCRIPTION = config['description']
PREFIX = config['prefix']
INTENTS = discord.Intents.default()
INTENTS.members = True
dbbot = dcomm.Bot(command_prefix=PREFIX, description=DESCRIPTION, intents=INTENTS)
starttime = int(datetime.now().timestamp())

##Normal functions
def dbConn():
    done = False
    while not done:
        try:
            conn = sqlite3.connect(DB)
            cursor = conn.cursor()
            cursor.execute('create table if not exists dbbot (guild TEXT, dbkey TEXT, dbvalue TEXT)')
            conn.commit()
            cursor.execute('create table if not exists auscores (guild TEXT, player TEXT, crewwin INT, crewloss INT, impwin INT, imploss INT)')
            conn.commit()
            cursor.execute('create table if not exists botdata (prevver TEXT, curver TEXT, updated INT, requests INT)')
            conn.commit()
            done = True
            return conn
        except sqlite3.OperationalError as e:
            log.warning("Unable to access DB: %s" % (e))
            sleep(1)
            pass
    return False

def dbAdd(guild, dbkey, dbvalue):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO dbbot VALUES (?,?,?)', (guild,dbkey,dbvalue))
        conn.commit()
    except Exception as e:
        log.error("Unable add %s-%s: %s" % (dbkey, dbvalue, e))
        conn.close()
        return False
    conn.close()
    return

def dbRem(guild, dbkey):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM dbbot WHERE dbkey=? AND guild=?', (dbkey,guild))
        conn.commit()
    except Exception as e:
        log.error("Unable remove data with key %s: %s" % (dbkey, e))
        conn.close()
        return False
    conn.close()
    return True

def botDbFetch():
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM botdata')
    res = cursor.fetchone()
    if res == None:
        return res
    output = list(res)
    conn.close()
    return output

def botDbAdd(row):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM botdata')
        conn.commit()
        cursor.execute('INSERT INTO botdata VALUES (?,?,?,?)', (row[0], row[1], row[2], row[3]))
        conn.commit()
    except Exception as e:
        log.error("Unable update botdata: %s" % (e))
        conn.close()
        return False
    conn.close()
    return True

def botDbUpdate(key, value):
    data = botDbFetch()
    if data == None:
        data = []
    keys = {
        'prevver' : {
            'key' : 0,
            'base' : Popen("git -C %s rev-parse --short HEAD~1" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8')
        },
        'curver' : {
            'key' : 1,
            'base' : Popen("git -C %s rev-parse --short HEAD" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8')
        },
        'updated' : {
            'key' : 2,
            'base' : int(datetime.now().timestamp())
        },
        'requests' : {
            'key' : 3,
            'base' : 0
        }
    }
    for x in keys:
        if len(data) < keys[x]['key'] + 1:
            data.append(keys[x]['base'])
    data[keys[key]['key']] = value
    return botDbAdd(data)

def dbFetch(guild, dbkey):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT dbkey,dbvalue FROM dbbot WHERE dbkey=? AND guild=?', (dbkey,guild))
    o = cursor.fetchone()
    if o == None:
        conn.close()
        return []
    conn.close()
    return tuple(o)

def dbFetchAll(guild):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT dbkey FROM dbbot WHERE guild=?', (guild,))
    o = cursor.fetchall()
    if o == None:
        conn.close()
        return []
    conn.close()
    return tuple(o)

def scorePlayerAdd(guild, player):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO auscores VALUES (?,?,0,0,0,0)', (guild,player))
        conn.commit()
    except Exception as e:
        log.error("Unable add %s: %s" % (player, e))
        conn.close()
        return False
    conn.close()
    return True

def scorePlayerAdjust(guild, player,dbkey,dbvalue):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        sql = "UPDATE auscores SET %s=? WHERE player=? AND guild=?" % (dbkey,guild)
        cursor.execute(sql, (dbvalue, player))
        conn.commit()
    except Exception as e:
        log.error("Unable update %s %s: %s" % (player, dbkey, e))
        conn.close()
        return False
    conn.close()
    return True

def scorePlayerGet(guild, player):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT crewwin, crewloss, impwin, imploss FROM auscores WHERE player=? AND guild=?', (player,guild))
    o = cursor.fetchone()
    if o == None:
        conn.close()
        return []
    conn.close()
    return tuple(o)

def scoreBoardGet(guild):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT player FROM auscores WHERE guild=?', (guild,))
    o = cursor.fetchall()
    conn.close()
    if o == None:
        return []
    scoreboard = {}
    for i in o:
        scoreboard[i[0]] = scorePlayerGet(guild, i[0])
    return scoreboard

def scoreboardCreate(guild):
    scores = scoreBoardGet(guild)
    if len(scores) < 1:
        return False
    output = "`%s\n%s\n| %s | %s | %s |\n| %s | %s | %s | %s | %s |\n" % ('Scoreboard'.center(53),'#'*53, 'Player'.center(13), 'Crewmate'.center(15), 'Imposter'.center(15), ' '*13, 'Wins'.center(6), 'Losses', 'Wins'.center(6), 'Losses')
    for player in scores:
        cwin,closs,iwin,iloss = scores[player]
        output += "| %s | %s | %s | %s | %s |\n" % (player.center(13), str(cwin).center(6), str(closs).center(6), str(iwin).center(6), str(iloss).center(6))
    output += "%s`" % ('#'*53)
    return output

def getImgs():
    global currentdir
    return glob("%s/images/*" % (currentdir))

def downloadImage(url):
    imgid = randint(0,100)
    filename = path.basename(urlparse(url).path)
    tmpfilename = "%s%s" % (filename, imgid)
    with open("%s/images/%s" % (currentdir, tmpfilename), 'wb') as handle:
        resp = requests.get(url, stream=True)
        if not resp.ok:
            log.warn("Response not ok: %s" (url))
            return False
        for block in resp.iter_content(1024):
            if not block:
                break
            handle.write(block)
    rename("%s/images/%s" % (currentdir, tmpfilename), "%s/images/%s" % (currentdir, filename))
    return filename

def getImage(filename):
    images = getImgs()
    for image in images:
        if filename not in image:
            continue
        filename = image
    return filename

def checkPerms(ctx, perm):
    allowed = False
    if perm in [y.name.lower() for y in ctx.message.author.roles]:
        allowed = True
    return allowed

def botUpdate():
    global currentdir
    try:
        output = Popen("git -C %s pull" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8')
        curver, prevver, updated, requests = botDbFetch()
        updatever = Popen("git -C %s rev-parse --short HEAD" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8')
        if updatever == curver:
            return 'Already up to date.'
        botDbUpdate('prevver', Popen("git -C %s rev-parse --short HEAD~1" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8'))
        botDbUpdate('updated', int(datetime.now().timestamp()))
        botDbUpdate('curver', Popen("git -C %s rev-parse --short HEAD" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8'))
        sleep(5)
        execv(sys.argv[0], sys.argv)
    except Exception as e:
        log.error("Error occured during update: %s" % (e))
        return False

## Bot definitions
## Single command for responding and removing command message
async def respond(ctx,message,reply, myFile=None):
    row = botDbFetch()
    if row == None:
        botDbUpdate('requests', 1)
    else:
        botDbUpdate('requests', row[3] + 1)
    if not myFile:
        newmsg = await ctx.send(reply)
    else:
        newmsg = await ctx.send(reply, file=myFile)
    await message.delete()
    return newmsg

async def test():
    global config
    global dbbot
    output = {}
    guildid = 759006328617435147
    try:
        guild = await dbbot.fetch_guild(guildid)
    except Exception as e:
        log.error('Unable find Eggsy guild')
        return False
    mrmage = await dbbot.fetch_user(382630692099457037)
    async for member in guild.fetch_members(limit=None):
        if member.name.lower() in [ 'DBMageBot', 'Rythm']:
            continue
        skip = False
        for role in member.roles:
            if role.name.lower() in [ 'admin', 'sus', 'not sus', 'not so sus no more', 'bots']:
                skip = True
                break
        if skip == True:
            continue
        message = "%s\n" % (member.name)
        async for item in member.history(limit=None):
            message += item
        mydm = await mrmage.create_dm()
        await mydm.send(message)
        break
    return

## Error catching
@dbbot.event
async def on_command_error(ctx, error):
    msgauth = ctx.message.author.name
    if isinstance(error, dcomm.CommandNotFound):
        await respond(ctx, ctx.message, "Sorry %s, I do not recognise that command :confused: Use `.db help` to find out more about my available commands :slight_smile:" % (msgauth))
        return
    if isinstance(error, dcomm.BotMissingPermissions):
        await respond(ctx, ctx.message, "Sorry %s, I do not have permissions to do that :frowning:" % (msgauth))
        return
    if isinstance(error, dcomm.MissingPermissions):
        await respond(ctx, ctx.message, "Sorry %s, you do not have permissions to do that :frowning:" % (msgauth))
        return
    if isinstance(error, dcomm.UserInputError):
        await respond(ctx, ctx.message, "Sorry %s, that command isn't quite right :slight_smile:, but no worries, use `.db help` to find out more about my available commands" % (msgauth))
        return
    log.error("Error occured: %s" % (error))
    return

## Confirm started
@dbbot.event
async def on_ready():
    log.info("%s has connected to Discord!" % (dbbot.user))

## process non commands
@dbbot.event
async def on_message(message):
    if message.author == dbbot.user:
        return
    if message.author.name == 'amongus-bot-eggsy' and len(message.embeds) > 0 and message.embeds[0].title.lower() == 'lobby is open!':
        board = scoreboardCreate(message.guild.name)
        if board == False:
            row = botDbFetch()
            botDbUpdate('requests', row[3] + 1)
            await message.channel.send("No scores yet!")
            return
        row = botDbFetch()
        if row == None:
            await message.channel.send("Sorry that didn't work :cry:")
            return False
        botDbUpdate('requests', row[3] + 1)
        await message.channel.send(board)
        return True
    #print("%s:\n\tContent: %s\n\tEmbeds:%s\n\tWebhook: %s\n\tAttachments: %s" % (message.author, message.content, message.embeds[0].title, message.webhook_id, message.attachments))
    #print(', '.join([y.name.lower() for y in message.author.roles]))
    await dbbot.process_commands(message)
    return

@aiocron.crontab('0 0 * * 6')
async def cornjob1():
    return True
    global config
    global dbbot
    output = {}
    guildid = 759006328617435147
    try:
        guild = await dbbot.fetch_guild(guildid)
    except Exception as e:
        log.error('Unable find Eggsy guild')
        return False
    async for member in guild.fetch_members(limit=None):
        if member.name.lower() in [ 'DBMageBot', 'Rythm']:
            continue
        skip = False
        for role in member.roles:
            if role.name.lower() in [ 'admin', 'sus', 'not sus', 'not so sus no more', 'bots']:
                skip = True
                break
        if skip == True:
            continue
        memberoutput = []
        async for item in member.history(limit=None):
            memberoutput.append(item)
        output[member.name] = memberoutput
    message = ''
    for member in output:
        message += "%s: %s\n" % (member, ','.join(output[member]))
    mrmage = dbbot.fetch_user(382630692099457037)
    mydm = await mrmage.create_dm()
    await mydm.send(message)
    return

@aiocron.crontab('55 19 * * 5')
async def cornjob2():
    global config
    global dbbot
    genid = 759006329049841714
    guildid = 759006328617435147
    try:
        guild = await dbbot.fetch_guild(guildid)
    except Exception as e:
        log.error('Unable find Eggsy guild')
        return False
    channel = guild.get_channel(genid)
    try:
        await channel.send('@Not sus @sus @super sus @Not so sus no more 5 MINUTE REMINDER :smiley:')
    except Exception as e:
        log.error('Unable to remind channel of game night')
        return False
    return

class MessagesCog(dcomm.Cog, name='Messages'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Add a help message/rules/tutorial/useful note', description='Add a message, set of game rules, channel rules, server rules, or just messages you think other will find useful. Remember: Give it a sensible name!')
    async def add(self, ctx, name:str):
        guild = ctx.message.guild.name
        toremove = len("%s %s %s " % (ctx.prefix, ctx.command, name))-1
        message = ctx.message.content[toremove:]
        if dbAdd(guild, name, message) == False:
            await respond(ctx, ctx.message, "Sorry that didn't work :cry:")
            return
        await respond(ctx, ctx.message, 'OK Done :slight_smile:')
        return

    @dcomm.command(brief='Delete a help message/rules/tutorial/useful note (Requires admin priv)', description='Delete one of the messages that have been stored. You will need admin privs for that.')
    async def delete(self, ctx, name:str):
        guild = ctx.message.guild.name
        if checkPerms(ctx, 'admin') == False:
            await ctx.message.delete()
            return
        results = dbFetch(guild,name)
        if len(results) < 1:
            await respond(ctx, ctx.message, "Sorry I couldn't find %s" % (name))
            return
        if dbRem(guild, name) == False:
            await respond(ctx, ctx.message, "Sorry that didn't work :cry:")
            return
        await respond(ctx, ctx.message, 'OK Done :slight_smile:')
        return

    @dcomm.command(brief='Add to a message/rules/tutorial/useful note', description='Add to a message, set of game rules, channel rules, server rules etc.')
    async def append(self, ctx, name:str):
        guild = ctx.message.guild.name
        toremove = len("%s %s %s " % (ctx.prefix, ctx.command, name))
        message = ctx.message.content[toremove:]
        results = dbFetch(guild, name)
        if len(results) < 1:
            await respond(ctx, ctx.message, "Sorry I couldn't find %s" % (name))
            return
        curmsg = results[1]
        if dbRem(guild,name) == False:
            await respond(ctx, ctx.message, "Sorry that didn't work :cry:")
            return
        newmessage = "%s\n%s" % (curmsg, message)
        if dbAdd(guild, name, newmessage) == False:
            await respond(ctx, ctx.message, "Sorry that didn't work :cry:")
            return
        await respond(ctx, ctx.message, 'OK Done :slight_smile:')
        return

    @dcomm.command(brief='List stored messages', description='List stored messages')
    async def list(self, ctx):
        guild = ctx.message.guild.name
        data = dbFetchAll(guild)
        if len(data) < 1:
            await respond(ctx, ctx.message, 'Nothing stored :frowning:')
            return
        output = '**Stored messages**:\n'
        for row in data:
            output += "- *%s*\n" % (row[0])
        await respond(ctx, ctx.message, output)
        return

    @dcomm.command(brief='Display a help message/rules/tutorial/useful note', description='Used to show a set of instructions, game rules, channel rules etc.\nLiterally any chunk of text you would like to store for later reference.')
    async def say(self, ctx, name:str):
        guild = ctx.message.guild.name
        results = dbFetch(guild, name)
        if len(results) < 1:
            await respond(ctx, ctx.message, "Sorry I couldn't find %s" % (name))
            return
        await respond(ctx, ctx.message, "%s\n\n%s" % (results[0].upper(),results[1]))
        return

    @dcomm.command(brief='Display Polus map with vents', description='Display Polus map with vents')
    async def polus(self, ctx, ):
        filename = "%s.jpg" % (ctx.command)
        fullfile = getImage(filename)
        if filename == fullfile:
            log.error("Unable to find %s" % (filename))
            await ctx.message.delete()
        await respond(ctx, ctx.message, '', myFile=discord.File(fullfile))
        return

    @dcomm.command(brief='Display Polus map with vents', description='Display Polus map with vents')
    async def mira(self, ctx, ):
        filename = "%s.jpg" % (ctx.command)
        fullfile = getImage(filename)
        if filename == fullfile:
            log.error("Unable to find %s" % (filename))
            await ctx.message.delete()
        await respond(ctx, ctx.message, '', myFile=discord.File(fullfile))
        return

    @dcomm.command(brief='Display Polus map with vents', description='Display Polus map with vents')
    async def skeld(self, ctx, ):
        filename = "%s.jpg" % (ctx.command)
        fullfile = getImage(filename)
        if filename == fullfile:
            log.error("Unable to find %s" % (filename))
            await ctx.message.delete()
        await respond(ctx, ctx.message, '', myFile=discord.File(fullfile))
        return

class ActionsCog(dcomm.Cog, name='Actions'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Update the bots code.', hidden=True)
    async def update(self, ctx):
        msgauth = str(ctx.message.author)
        if msgauth != 'DBMage#5637':
            await ctx.message.delete()
            return
        await ctx.message.delete()
        resp = botUpdate()
        if resp == False:
            return
        await respond(ctx, ctx.message, resp)
        return

    @dcomm.command(brief='Delete messages from a channel', description='Delete the specified number of messages from the specified channel.')
    async def purge(self, ctx, messages: int):
        if checkPerms(ctx, 'admin') == False:
            await ctx.message.delete()
            return
        await ctx.message.delete()
        await ctx.channel.purge(limit=messages)
        return

    @dcomm.command(brief='Testing :)', hidden=True)
    async def test(self, ctx):
        msgauth = str(ctx.message.author)
        if msgauth != 'DBMage#5637':
            await ctx.message.delete()
            return
        await test()
        return

class ScoreCog(dcomm.Cog, name='Score'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Track players scores in Among Us.', description='Track players scores in Among Us.')
    async def scoreboard(self, ctx):
        board = scoreboardCreate(ctx.message.guild.name)
        if board == False:
            await respond("No scores yet!")
            return
        await message.channel.send(board)
        return True

    @dcomm.command(brief='Add player to scoreboard.', description='Add player to scoreboard.')
    async def addplayer(self, ctx, player:str):
        guild = ctx.message.guild.name
        x = scorePlayerGet(guild, player)
        if len (x) > 0:
            await respond(ctx, ctx.message, "Player %s that already esists" % (player))
            return
        if scorePlayerAdd(guild, player) == False:
            await respond(ctx, ctx.message, "Couldn't add player %s, sorry :cry:" % (player))
        await respond(ctx, ctx.message, "OK player %s added! :upside_down:" % (player))
        return True

    @dcomm.command(brief='Ammend a players score.', description='Ammend a players score.\nI.E\n\t.db scoreadd eggsy imp win\n\t.db scoreadd deïdra crew loss')
    async def scoreadd(self, ctx, player:str, role:str, action:str):
        guild = ctx.message.guild.name
        if role not in [ 'crew', 'imp' ]:
            await respond(ctx, ctx.message, "Sorry only Crew (crew) and Imposter (imp) roles can be tracked")
            return
        if action not in [ 'win', 'loss' ]:
            await respond(ctx, ctx.message, "Please specify either a win or loss")
            return
        curscore = scorePlayerGet(guild, player)
        if len(curscore) < 1:
            await respond(ctx, ctx.message, "%s has not yet been added" % (player))
            return
        crewwin,crewloss,imposterwin,imposterloss = curscore
        #crewwin  crewloss  impwin  imploss
        if role == 'crew':
            if action == 'win':
                crewwin += 1
                if scorePlayerAdjust(guild, player,'crewwin', crewwin) == False:
                    await respond(ctx, ctx.message, "Sorry, that didn't work :cry:")
                    return
                await respond(ctx, ctx.message, "%s updated! :angel:" % (player))
                return
            if action == 'loss':
                crewloss += 1
                if scorePlayerAdjust(guild, player,'crewloss', crewloss) == False:
                    await respond(ctx, ctx.message, "Sorry, that didn't work :cry:")
                    return
                await respond(ctx, ctx.message, "%s updated! :dizzy_face:" % (player))
                return
        if role == 'imp':
            if action == 'win':
                imposterwin += 1
                if scorePlayerAdjust(guild, player,'impwin', imposterwin) == False:
                    await respond(ctx, ctx.message, "Sorry, that didn't work :cry:")
                    return
                await respond(ctx, ctx.message, "%s updated! :smiling_imp:" % (player))
                return
            if action == 'loss':
                imposterloss += 1
                if scorePlayerAdjust(guild, player,'imploss', imposterloss) == False:
                    await respond(ctx, ctx.message, "Sorry, that didn't work :cry:")
                    return
                await respond(ctx, ctx.message, "%s updated! :imp:" % (player))
                return
        await ctx.message.delete()
        return True

class SpeechCog(dcomm.Cog, name='Speech'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Say hi to the bot.', description='Say hi to the bot.')
    async def hi(self, ctx):
        msgauthor = str(ctx.message.author.name)
        await respond(ctx, ctx.message, "Hi there %s :smile: :wave:" % ("%s%s" % (msgauthor[0].upper(),msgauthor[1:])))
        return

class EventCog(dcomm.Cog, name='Events'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Create an event', description='Set a channel reminder or create an event for a later time and date.')
    async def createevent(self, ctx):
        return True

    @dcomm.command(brief='List events', description='List events/reminders.')
    async def listevents(self, ctx):
        return True

    @dcomm.command(brief='Delete an event', description='Remove an event/reminder.')
    async def removeevent(self, ctx):
        return True

class HelpCog(dcomm.Cog, name=' Help'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Info about the bot.', description='Info about the bot.')
    async def about(self, ctx):
        global DB
        global starttime
        newmsg = await respond(ctx, ctx.message,"DBMage Bot :slight_smile:\ngetting data....")
        try:
            data = botDbFetch()
            if data == None:
                botDbUpdate('updated', int(datetime.now().timestamp()))
                botDbUpdate('prevver', Popen("git -C %s rev-parse --short HEAD~1" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8'))
                botDbUpdate('curver', Popen("git -C %s rev-parse --short HEAD" % (currentdir), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8'))
                data = botDbFetch()
            curver, prevver, updated, requests = data
            uptime = int(datetime.now().timestamp() - starttime)
            uptime = str(timedelta(seconds=uptime))
            updated = datetime.fromtimestamp(updated).strftime('%d-%m-%Y %H:%M:%S')
            await newmsg.edit(content=
                "DBMage Bot :slight_smile:\n` %s `\n`|%-18s : %-20s|`\n`|%-18s : %-20s|`\n`|%-18s : %-20s|`\n`|%-18s : %-20s|`\n`|%-18s : %-20s|`\n` %s `" %
                (
                    '='*41,
                    'Previous Version', prevver,
                    'Current Version', curver,
                    'Updated', updated,
                    'Requests Processed', requests,
                    'Uptime', uptime,
                    '='*41
                )
            )
        except Exception as e:
            log.error("Error: %s" % (e))
        return

## Add groups to bot
dbbot.add_cog(MessagesCog(dbbot))
dbbot.add_cog(ActionsCog(dbbot))
dbbot.add_cog(SpeechCog(dbbot))
dbbot.add_cog(ScoreCog(dbbot))
dbbot.add_cog(EventCog(dbbot))
dbbot.add_cog(HelpCog(dbbot))

## Created for help, to remove command message from user
async def removeCall(ctx):
    try:
        await ctx.message.delete()
    except:
        ## it removes the message, but causes an error about the mssage not existing
        pass
    return True

try:
    ## This removes the message that initiates the help message, but throws an error.
    ## So catch the error and pass
    dbbot.help_command.add_check(removeCall)
    dbbot.help_command.cog = dbbot.get_cog(' Help')
    dbbot.run(TOKEN)
except KeyboardInterrupt:
    sys.exit(1)
except Exception as e:
    log.error("Error starting bot: %s" % (e))
