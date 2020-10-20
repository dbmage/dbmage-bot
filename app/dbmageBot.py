#!/usr/bin/python3
import sys
import docker
import discord
import sqlite3
from os import path,getenv
from time import sleep
from discord.ext import commands as dcomm
from json import loads as jloads

currentdir = path.dirname(path.abspath(__file__))
config = jloads(open("%s/config.json" % (currentdir)).read())
## Check if vars are in config or env
if len(config['token']) == 0:
    if os.getenv('TOKEN') == None:
        print("ERROR: No token supplied")
        sys.exit(1)
    config['token'] = os.getenv('TOKEN')
for thing in ['token', 'amongusbot']:
    if len(config[thing]) == 0:
        if os.getenv(thing.upper()) == None:
            print("WARNING: No %s supplied" % (thing))
        else:
            config[thing] = os.getenv(thing.upper())

description = 'DBMages helper bot'
##Normal functions
def dbConn():
    done = False
    while not done:
        try:
            conn = sqlite3.connect('bot.db')
            cursor = conn.cursor()
            cursor.execute('create table if not exists dbbot (dbkey TEXT, dbvalue TEXT)')
            conn.commit()
            done = True
            return conn
        except sqlite3.OperationalError:
            sleep(1)
            pass
    return False

def dbAdd(dbkey, dbvalue):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO dbbot VALUES (?,?)', (dbkey, dbvalue))
        conn.commit()
    except Exception as e:
        print("Unable add %s-%s: %s" (dbkey, dbvalue, e))
        return False
    return

def dbRem(dbkey):
    conn = dbConn()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM dbbot WHERE dbkey=?', (dbkey,))
        conn.commit()
    except Exception as e:
        print("Unable remove data with key %s: %s" (dbkey, e))
        return False
    return True

def dbFetch(dbkey):
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM dbbot WHERE dbkey=?', (dbkey,))
    o = cursor.fetchone()
    if o == None:
        return []
    return tuple(o)

def dbFetchAll():
    conn = dbConn()
    cursor = conn.cursor()
    cursor.execute('SELECT dbkey FROM dbbot')
    o = cursor.fetchall()
    if o == None:
        return []
    return tuple(o)

def getContainers(dclient):
    containers = {}
    for x in dclient.containers.list():
        continers[x.attrs['Name']] = x
    return containers

## Bot definitions
dbbot = dcomm.Bot(command_prefix='.db ', description=description)

@dbbot.event
async def on_ready():
    print("%s has connected to Discord!" % (dbbot.user))

@dbbot.event
async def on_member_join(member):
    await ctx.send("Hi %s, welcome to the server!\nYou can use .db help to find out more info" % (member.name))
    return

class MessagesCog(dcomm.Cog, name='Messages'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Add a help message/rules/tutorial/useful note', description='Add a message, set of game rules, channel rules, server rules, or just messages you think other will find useful. Remember: Give it a sensible name!')
    async def add(self, ctx, name:str):
        toremove = len("%s %s %s " % (ctx.prefix, ctx.command, name))-1
        message = ctx.message.content[toremove:]
        await ctx.message.delete()
        if dbAdd(name, message) == False:
            await ctx.send("Sorry that didn't work :cry:")
            return
        await ctx.send('OK Done :slight_smile:')
        return

    @dcomm.command(brief='Delete a help message/rules/tutorial/useful note', description='Delete one of the messages that have been stored. You will need "admin" privs for that.')
    async def delete(self, ctx, name:str):
        await ctx.message.delete()
        results = dbFetch(name)
        if len(results) < 1:
            await ctx.send("Sorry I couldn't find %s" % (name))
            return
        if dbRem(name) == False:
            await ctx.send("Sorry that didn't work :cry:")
            return
        await ctx.send('OK Done :slight_smile:')
        return

    @dcomm.command(brief='List stored messages', description='List stored messages')
    async def list(self, ctx):
        await ctx.message.delete()
        data = dbFetchAll()
        if len(data) < 1:
            await ctx.send('Nothing stored :frowning:')
            return
        output = 'Stored messages:\n'
        for row in data:
            output += "%s\n" % (row[0])
        await ctx.send(output)
        return

    @dcomm.command(brief='Display a help message/rules/tutorial/useful note', description='Used to show a set of instructions, game rules, channel rules etc.\nLiterally any chunk of text you would like to store for later reference.')
    async def say(self, ctx, name:str):
        await ctx.message.delete()
        results = dbFetch(name)
        if len(results) < 1:
            await ctx.send("Sorry I couldn't find %s" % (name))
            return
        await ctx.send("%s\n\n%s" % (results[0].upper(),results[1]))

class ActionsCog(dcomm.Cog, name='Actions'):

    def __init__(self, bot):
        self.bot = bot

    @dcomm.command(brief='Restart the Among Us bot.', description='Restart the Among Us bot.')
    async def restart(self, ctx):
        await ctx.message.delete()
        if config['amongusbot'].replace(' ','') == '':
            await ctx.send("Could not find an Among Us bot configured")
        dclient = docker.from_env()
        containers = getContainers(dclient)
        if config['amongusbot'] not in containers:
            dclient.close()
            await ctx.send("Could not find an Among Us bot connected to your server")
            return
        cont = containers[config['amongusbot']]
        cont.restart()
        dclient.close()
        return True

class HelpCog(dcomm.Cog, name=' Help'):

    def __init__(self, bot):
        self.bot = bot

dbbot.add_cog(MessagesCog(dbbot))
dbbot.add_cog(ActionsCog(dbbot))
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
