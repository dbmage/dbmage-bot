#!/usr/bin/python3
import sys
import docker
import discord
import sqlite3
from time import sleep
from os import path,getenv,system
from shutil import copyfile
from json import loads as jloads
from subprocess import Popen, PIPE
from discord.ext import commands as dcomm

currentdir = path.dirname(path.abspath(__file__))
config = jloads(open("%s/config.json" % (currentdir)).read())
## Check if vars are in config or env
if len(config['token']) == 0:
    if getenv('TOKEN') == None:
        print("ERROR: No token supplied")
        sys.exit(1)
    config['token'] = getenv('TOKEN')
for thing in ['token', 'amongusbot']:
    if len(config[thing]) == 0:
        if getenv(thing.upper()) == None:
            print("WARNING: No %s supplied" % (thing))
        else:
            config[thing] = getenv(thing.upper())

DB = '/app/db/bot.db'
if getenv('DB') != None:
    DB = getenv('DB')
else:
    if not path.exists('/'.join(DB.split('/')[:-1])):
        print("Unable to create DB: %s does not exist" % ('/'.join(DB.split('/')[:-1])))
        sys.exit(1)

description = 'DBMages helper bot'
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
            done = True
            return conn
        except sqlite3.OperationalError as e:
            print("Unable to access DB: %s" % (e))
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
        print("Unable add %s-%s: %s" % (dbkey, dbvalue, e))
        return False
    return

def dbRem(guild, dbkey):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM dbbot WHERE dbkey=? AND guild=?', (dbkey,guild))
        conn.commit()
    except Exception as e:
        print("Unable remove data with key %s: %s" % (dbkey, e))
        return False
    return True

def dbFetch(guild, dbkey):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT dbkey,dbvalue FROM dbbot WHERE dbkey=? AND guild=?', (dbkey,guild))
    o = cursor.fetchone()
    if o == None:
        return []
    return tuple(o)

def dbFetchAll(guild):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT dbkey FROM dbbot WHERE guild=?', (guild,))
    o = cursor.fetchall()
    if o == None:
        return []
    return tuple(o)

def scorePlayerAdd(guild, player):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO auscores VALUES (?,?,0,0,0,0)', (guild,player))
        conn.commit()
    except Exception as e:
        print("Unable add %s: %s" % (player, e))
        return False
    return

def scorePlayerAdjust(guild, player,dbkey,dbvalue):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        sql = "UPDATE auscores SET %s=? WHERE player=? AND guild=?" % (dbkey,guild)
        cursor.execute(sql, (dbvalue, player))
        conn.commit()
    except Exception as e:
        print("Unable update %s %s: %s" % (player, dbkey, e))
        return False
    return

def scorePlayerGet(guild, player):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT crewwin, crewloss, impwin, imploss FROM auscores WHERE player=? AND guild=?', (player,guild))
    o = cursor.fetchone()
    if o == None:
        return []
    return tuple(o)

def scoreBoardGet(guild):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT player FROM auscores WHERE guild=?', (guild,))
    o = cursor.fetchall()
    if o == None:
        return []
    scoreboard = {}
    for i in o:
        scoreboard[i[0]] = scorePlayerGet(guild, i[0])
    return scoreboard

def getContainers(dclient):
    containers = {}
    for x in dclient.containers.list():
        continers[x.attrs['Name']] = x
    return containers

## Bot definitions
dbbot = dcomm.Bot(command_prefix='.db ', description=description)

@dbbot.event
async def on_command_error(ctx, error):
    msgauth = ctx.message.author.name
    if isinstance(error, dcomm.CommandNotFound):
        await ctx.send("Sorry %s, I do not recognise that command :confused: Use `.db help` to find out more about my available commands :slight_smile:" % (msgauth))
        await ctx.message.delete()
        return
    if isinstance(error, dcomm.BotMissingPermissions):
        await ctx.send("Sorry %s, I do not have permissions to do that :frowning:" % (msgauth))
        await ctx.message.delete()
        return
    if isinstance(error, dcomm.MissingPermissions):
        await ctx.send("Sorry %s, you do not have permissions to do that :frowning:" % (msgauth))
        await ctx.message.delete()
        return
    if isinstance(error, dcomm.UserInputError):
        await ctx.send("Sorry %s, that command isn't quite right :slight_smile:, but no worries, use `.db help` to find out more about my available commands" % (msgauth))
        await ctx.message.delete()
        return
    print("Error occured: %s" % (error))
    return

@dbbot.event
async def on_ready():
    print("%s has connected to Discord!" % (dbbot.user))

@dbbot.event
async def on_member_join(member):
    if 'eggsy' not in ctx.message.guild.name.lower():
        return
    await ctx.send("Hi %s, welcome to the server!\nYou can use .db help to find out more info" % (member.name))
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
            await ctx.send("Sorry that didn't work :cry:")
            await ctx.message.delete()
            return
        await ctx.send('OK Done :slight_smile:')
        await ctx.message.delete()
        return

    @dcomm.command(brief='Delete a help message/rules/tutorial/useful note (Requires admin priv)', description='Delete one of the messages that have been stored. You will need admin privs for that.')
    async def delete(self, ctx, name:str):
        guild = ctx.message.guild.name
        admin = False
        if "admin" in [y.name.lower() for y in ctx.message.author.roles]:
            admin = True
        if admin == False:
            await ctx.send("Sorry %s, you do not have permission to do that :frowning:" % (ctx.message.author.name))
            await ctx.message.delete()
            return
        results = dbFetch(guild,name)
        if len(results) < 1:
            await ctx.send("Sorry I couldn't find %s" % (name))
            await ctx.message.delete()
            return
        if dbRem(guild, name) == False:
            await ctx.send("Sorry that didn't work :cry:")
            await ctx.message.delete()
            return
        await ctx.send('OK Done :slight_smile:')
        await ctx.message.delete()
        return

    @dcomm.command(brief='Add to a message/rules/tutorial/useful note', description='Add to a message, set of game rules, channel rules, server rules etc.')
    async def append(self, ctx, name:str):
        guild = ctx.message.guild.name
        toremove = len("%s %s %s " % (ctx.prefix, ctx.command, name))-1
        message = ctx.message.content[toremove:]
        results = dbFetch(guild, name)
        if len(results) < 1:
            await ctx.send("Sorry I couldn't find %s" % (name))
            await ctx.message.delete()
            return
        curmsg = results[1]
        if dbRem(guild,name) == False:
            await ctx.send("Sorry that didn't work :cry:")
            await ctx.message.delete()
            return
        newmessage = "%s\n%s" % (curmsg, message)
        if dbAdd(guild, name, newmessage) == False:
            await ctx.send("Sorry that didn't work :cry:")
            await ctx.message.delete()
            return
        await ctx.send('OK Done :slight_smile:')
        await ctx.message.delete()
        return

    @dcomm.command(brief='List stored messages', description='List stored messages')
    async def list(self, ctx):
        guild = ctx.message.guild.name
        data = dbFetchAll(guild)
        if len(data) < 1:
            await ctx.send('Nothing stored :frowning:')
            await ctx.message.delete()
            return
        output = '**Stored messages**:\n'
        for row in data:
            output += "- *%s*\n" % (row[0])
        await ctx.send(output)
        await ctx.message.delete()
        return

    @dcomm.command(brief='Display a help message/rules/tutorial/useful note', description='Used to show a set of instructions, game rules, channel rules etc.\nLiterally any chunk of text you would like to store for later reference.')
    async def say(self, ctx, name:str):
        guild = ctx.message.guild.name
        results = dbFetch(guild, name)
        if len(results) < 1:
            await ctx.send("Sorry I couldn't find %s" % (name))
            await ctx.message.delete()
            return
        await ctx.send("%s\n\n%s" % (results[0].upper(),results[1]))
        await ctx.message.delete()
        return

class ActionsCog(dcomm.Cog, name='Actions'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Restart the Among Us bot.', description='Restart the Among Us bot.')
    async def restart(self, ctx):
        guild = ctx.message.guild.name
        aubot = None
        for i in config['amongusbot'].split(','):
            if i.split('-')[-1] not in guild:
                continue
            aubot = i.split('-')[-1]
        if aubot == None:
            await ctx.send("Could not find an Among Us bot connected to your server")
            await ctx.message.delete()
            return
        if config['amongusbot'].replace(' ','') == '':
            await ctx.send("Could not find an Among Us bot configured")
            await ctx.message.delete()
            return
        dclient = docker.from_env()
        containers = getContainers(dclient)
        if config['amongusbot'] not in containers:
            dclient.close()
            await ctx.send("Could not find an Among Us bot connected to your server")
            await ctx.message.delete()
            return
        cont = containers[config['amongusbot']]
        cont.restart()
        dclient.close()
        await ctx.message.delete()
        return True

    @dcomm.command(brief='Update the bots code.', hidden=True)
    async def update(self, ctx):
        msgauth = str(ctx.message.author)
        if msgauth != 'DBMage#5637':
            await ctx.message.delete()
            return
        system('git -C /app/ pull')
        await ctx.message.delete()
        return

class ScoreCog(dcomm.Cog, name='Score'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Track players scores in Among Us.', description='Track players scores in Among Us.')
    async def scoreboard(self, ctx):
        guild = ctx.message.guild.name
        scores = scoreBoardGet(guild)
        if len(scores) < 1:
            await ctx.send("No scores yet!")
            await ctx.message.delete()
            return
        output = "`%s\n%s\n| %s | %s | %s |\n| %s | %s | %s | %s | %s |\n" % ('Scoreboard'.center(53),'#'*53, 'Player'.center(13), 'Crewmate'.center(15), 'Imposter'.center(15), ' '*13, 'Wins'.center(6), 'Losses', 'Wins'.center(6), 'Losses')
        for player in scores:
            cwin,closs,iwin,iloss = scores[player]
            output += "| %s | %s | %s | %s | %s |\n" % (player.center(13), str(cwin).center(6), str(closs).center(6), str(iwin).center(6), str(iloss).center(6))
        output += "%s`" % ('#'*53)
        await ctx.send(output)
        await ctx.message.delete()
        return True

    @dcomm.command(brief='Add player to scoreboard.', description='Add player to scoreboard.')
    async def addplayer(self, ctx, player:str):
        guild = ctx.message.guild.name
        x = scorePlayerGet(guild, player)
        if len (x) > 0:
            await ctx.send("Player %s that already esists" % (player))
            await ctx.message.delete()
            return
        if scorePlayerAdd(guild, player) == False:
            await ctx.send("Couldn't add player %s, sorry :cry:" % (player))
            await ctx.message.delete()
        await ctx.send("OK player %s added! :upside_down:" % (player))
        await ctx.message.delete()
        return True

    @dcomm.command(brief='Ammend a players score.', description='Ammend a players score.\nI.E\n\t.db scoreadd eggsy imp win\n\t.db scoreadd deïdra crew loss')
    async def scoreadd(self, ctx, player:str, role:str, action:str):
        guild = ctx.message.guild.name
        if role not in [ 'crew', 'imp']:
            await ctx.send("Sorry only Crew (crew) and Imposter (imp) roles can be tracked")
            await ctx.message.delete()
            return
        if action not in [ 'win', 'loss']:
            await ctx.send("Please specify either a win or loss")
            await ctx.message.delete()
            return
        curscore = scorePlayerGet(guild, player)
        if len(curscore) < 1:
            await ctx.send("%s has not yet been added" % (player))
            await ctx.message.delete()
            return
        crewwin,crewloss,imposterwin,imposterloss = curscore
        #crewwin  crewloss  impwin  imploss
        if role == 'crew':
            if action == 'win':
                crewwin += 1
                if scorePlayerAdjust(guild, player,'crewwin', crewwin) == False:
                    await ctx.send("Sorry, that didn't work :cry:")
                    await ctx.message.delete()
                    return
                await ctx.send("%s updated! :angel:" % (player))
                await ctx.message.delete()
                return
            if action == 'loss':
                crewloss += 1
                if scorePlayerAdjust(guild, player,'crewloss', crewloss) == False:
                    await ctx.send("Sorry, that didn't work :cry:")
                    await ctx.message.delete()
                    return
                await ctx.send("%s updated! :dizzy_face:" % (player))
                await ctx.message.delete()
                return
        if role == 'imp':
            if action == 'win':
                imposterwin += 1
                if scorePlayerAdjust(guild, player,'impwin', imposterwin) == False:
                    await ctx.send("Sorry, that didn't work :cry:")
                    await ctx.message.delete()
                    return
                await ctx.send("%s updated! :smiling_imp:" % (player))
                await ctx.message.delete()
                return
            if action == 'loss':
                imposterloss += 1
                if scorePlayerAdjust(guild, player,'imploss', imposterloss) == False:
                    await ctx.send("Sorry, that didn't work :cry:")
                    await ctx.message.delete()
                    return
                await ctx.send("%s updated! :imp:" % (player))
                await ctx.message.delete()
                return
        await ctx.message.delete()
        return True

class SpeechCog(dcomm.Cog, name='Speech'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Say hi to the bot.', description='Say hi to the bot.')
    async def hi(self, ctx):
        msgauthor = str(ctx.message.author.name)
        await ctx.send("Hi there %s :smile: :wave:" % ("%s%s" % (msgauthor[0].upper(),msgauthor[1:])))
        await ctx.message.delete()
        return

class HelpCog(dcomm.Cog, name=' Help'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Info about the bot.', description='Info about the bot.')
    async def about(self, ctx):
        version = Popen("git -C /app/ rev-parse --short HEAD"), shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8')
        uptime = Popen('uptime -p', shell=True, stdout=PIPE).communicate()[0].strip().decode('utf-8').replace('up ','')
        await ctx.send("DBMage Bot :slight_smile:\n`Version: %-40s\nUptime: %-40s`" % (version, uptime))
        await ctx.message.delete()
        return

dbbot.add_cog(MessagesCog(dbbot))
dbbot.add_cog(ActionsCog(dbbot))
dbbot.add_cog(SpeechCog(dbbot))
dbbot.add_cog(ScoreCog(dbbot))
dbbot.add_cog(HelpCog(dbbot))

async def removeCall(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    return True

try:
    ## This removes the message that initiates the help message, but throws an error.
    ## So catch the error and pass
    dbbot.help_command.add_check(removeCall)
    dbbot.help_command.cog = dbbot.get_cog(' Help')
    dbbot.run(config['token'])
except KeyboardInterrupt:
    sys.exit(1)
