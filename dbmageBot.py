#!/usr/bin/python3
import sys
import docker
import discord
import sqlite3
from os import path
from time import sleep
from discord.ext import commands as dcomm
from json import loads as jloads

currentdir = path.dirname(path.abspath(__file__))
config = jloads(open("%s/config.json" % (currentdir)).read())
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

@dbbot.command(brief='Add a help message/rules/tutorial/useful note', description='Add a message, set of game rules, channel rules, server rules, or just messages you think other will find useful. Remember: Give it a sensible name!')
async def add(ctx, name:str):
    toremove = len("%s %s %s " % (ctx.prefix, ctx.command, name))-1
    message = ctx.message.content[toremove:]
    await ctx.message.delete()
    if dbAdd(name, message) == False:
        await ctx.send("Sorry that didn't work :(")
        return
    await ctx.send('OK Done :)')
    return

@dbbot.command(brief='Delete a help message/rules/tutorial/useful note', description='Delete one of the messages that have been stored. You will need "admin" privs for that.')
async def delete(ctx, name:str):
    await ctx.message.delete()
    results = dbFetch(name)
    if len(results) < 1:
        await ctx.send("Sorry I couldn't find %s" % (name))
        return
    if dbRem(name) == False:
        await ctx.send("Sorry that didn't work :(")
        return
    await ctx.send('OK Done :)')
    return

@dbbot.command(brief='List stored messages', description='List stored messages')
async def list(ctx):
    return ("Stored messages:\n%s" % ('\n'.join(dbFetchAll())))

@dbbot.command(brief='Display a help message/rules/tutorial/useful note', description='Used to show a set of instructions, game rules, channel rules etc.\nLiterally any chunk of text you would like to store for later reference.')
async def tell(ctx, name:str):
    await ctx.message.delete()
    results = dbFetch(name)
    if len(results) < 1:
        await ctx.send("Sorry I couldn't find %s" % (name))
        return
    await ctx.send("%s\n\n%s" % (results[0].upper(),results[1]))

@dbbot.command(brief='Restart the Among Us bot.', description='Restart the Among Us bot.')
async def restart(ctx):
    await ctx.message.delete()
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

@dbbot.event
async def on_member_join(member):
    await ctx.send("Hi %s, welcome to the server!\nYou can use .db help to find out more info" % (member.name))
    return

try:
    dbbot.run(config['token'])
except KeyboardInterrupt:
    sys.exit(1)
