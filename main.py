import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import random
import sqlite3
import requests
import math

# ================= LOAD TOKEN =================
load_dotenv()
TOKEN = os.getenv("TOKEN")

# ================= DISCORD SETUP =================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATABASE =================
conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    gold INTEGER DEFAULT 100,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS inventory (
    user_id INTEGER,
    item TEXT
)
""")

conn.commit()

# ================= BASIC SYSTEM =================
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if user is None:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return get_user(user_id)
    return user

def update_gold(user_id, amount):
    cursor.execute("UPDATE users SET gold = gold + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()

def add_win(user_id):
    cursor.execute("UPDATE users SET wins = wins + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

def add_loss(user_id):
    cursor.execute("UPDATE users SET losses = losses + 1 WHERE user_id = ?", (user_id,))
    conn.commit()

# ================= XP SYSTEM =================
def add_xp(user_id, amount):
    user = get_user(user_id)
    xp = user[4] + amount
    level = user[5]

    needed = level * 100

    if xp >= needed:
        level += 1
        xp -= needed

    cursor.execute("UPDATE users SET xp = ?, level = ? WHERE user_id = ?", (xp, level, user_id))
    conn.commit()

# ================= RANK =================
def get_rank(wins):
    if wins <= 2: return "Herald"
    if wins <= 5: return "Guardian"
    if wins <= 9: return "Crusader"
    if wins <= 14: return "Archon"
    if wins <= 20: return "Legend"
    return "Immortal"

# ================= ITEMS =================
shop_items = {"blink":200,"aghanim":350,"rapier":500}
item_power = {"blink":10,"aghanim":15,"rapier":40}

def add_item(user_id,item):
    cursor.execute("INSERT INTO inventory VALUES (?,?)",(user_id,item))
    conn.commit()

def get_items(user_id):
    cursor.execute("SELECT item FROM inventory WHERE user_id=?",(user_id,))
    return [i[0] for i in cursor.fetchall()]

def remove_item(user_id,item):
    cursor.execute("DELETE FROM inventory WHERE user_id=? AND item=? LIMIT 1",(user_id,item))
    conn.commit()

# ================= GLOBAL =================
heroes=["Invoker","Pudge","Storm","Sniper","SF","PA","Jugger"]
roshan_hp=500
quiz_active=False
quiz_answer=""

# ================= EVENTS =================
@bot.event
async def on_ready():
    print(f"Bot online: {bot.user}")

# ================= PROFILE =================
@bot.command()
async def profile(ctx):
    user=get_user(ctx.author.id)
    rank=get_rank(user[2])
    embed=discord.Embed(title=f"{ctx.author.name} PROFILE",color=discord.Color.gold())
    embed.add_field(name="Gold",value=user[1])
    embed.add_field(name="Wins",value=user[2])
    embed.add_field(name="Losses",value=user[3])
    embed.add_field(name="Level",value=user[5])
    embed.add_field(name="XP",value=user[4])
    embed.add_field(name="Rank",value=rank)
    await ctx.send(embed=embed)

# ================= MID =================
@bot.command()
@commands.cooldown(1,30,commands.BucketType.user)
async def mid(ctx,opponent:discord.Member):
    if opponent.bot: return

    hero1=random.choice(heroes)
    hero2=random.choice(heroes)

    base1=random.randint(50,100)
    base2=random.randint(50,100)

    bonus1=sum(item_power.get(i,0) for i in get_items(ctx.author.id))
    bonus2=sum(item_power.get(i,0) for i in get_items(opponent.id))

    total1=base1+bonus1
    total2=base2+bonus2

    if total1>total2:
        winner,loser=ctx.author,opponent
    else:
        winner,loser=opponent,ctx.author

    update_gold(winner.id,70)
    update_gold(loser.id,-30)
    add_win(winner.id)
    add_loss(loser.id)
    add_xp(winner.id,50)

    if "rapier" in get_items(loser.id):
        remove_item(loser.id,"rapier")
        await ctx.send("💀 Rapier потеряна!")

    embed=discord.Embed(title="MID 1V1",color=discord.Color.red())
    embed.add_field(name=ctx.author.name,value=f"{hero1} {total1}")
    embed.add_field(name=opponent.name,value=f"{hero2} {total2}")
    embed.add_field(name="Winner",value=winner.name)
    await ctx.send(embed=embed)

# ================= GANK =================
@bot.command()
async def gank(ctx,opponent:discord.Member):
    roll=random.randint(1,100)
    if roll<=60:
        update_gold(ctx.author.id,40)
        add_xp(ctx.author.id,20)
        result="SUCCESS"
    else:
        update_gold(ctx.author.id,-25)
        result="FAIL"

    embed=discord.Embed(title="GANK",color=discord.Color.dark_red())
    embed.add_field(name="Roll",value=roll)
    embed.add_field(name="Result",value=result)
    await ctx.send(embed=embed)

# ================= ROSHAN =================
@bot.command()
async def roshan(ctx):
    global roshan_hp
    if roshan_hp<=0:
        await ctx.send("Roshan мертв. Respawn.")
        return
    dmg=random.randint(20,80)
    roshan_hp-=dmg
    if roshan_hp<=0:
        update_gold(ctx.author.id,200)
        add_xp(ctx.author.id,100)
        roshan_hp=500
        await ctx.send(f"{ctx.author.name} убил Roshan +200 gold")
    else:
        await ctx.send(f"Урон {dmg}. Осталось {roshan_hp}")

# ================= QUIZ =================
@bot.command()
async def quiz(ctx):
    global quiz_active,quiz_answer
    if quiz_active: return
    questions={"Кто кидает Hook?":"pudge",
               "Кто крадет спеллы?":"rubick",
               "Black Hole кто?":"enigma"}
    q,a=random.choice(list(questions.items()))
    quiz_answer=a
    quiz_active=True
    await ctx.send(q)

    def check(m): return m.channel==ctx.channel and m.content.lower()==quiz_answer
    try:
        msg=await bot.wait_for("message",timeout=20,check=check)
        update_gold(msg.author.id,50)
        add_xp(msg.author.id,40)
        await ctx.send(f"{msg.author.name} правильно!")
    except:
        await ctx.send("Время вышло")
    finally:
        quiz_active=False

# ================= SHOP =================
@bot.command()
async def shop(ctx):
    text="Shop:\n"
    for i,p in shop_items.items():
        text+=f"{i} - {p}\n"
    await ctx.send(text)

@bot.command()
async def buy(ctx,item:str):
    user=get_user(ctx.author.id)
    if item not in shop_items: return
    if user[1]<shop_items[item]:
        await ctx.send("Недостаточно золота")
        return
    update_gold(ctx.author.id,-shop_items[item])
    add_item(ctx.author.id,item)
    await ctx.send(f"Куплен {item}")

# ================= OPENDOTA =================
@bot.command()
async def dota(ctx,steam_id:str):
    url=f"https://api.opendota.com/api/players/{steam_id}"
    r=requests.get(url)
    if r.status_code!=200:
        await ctx.send("Игрок не найден")
        return
    data=r.json()
    profile=data.get("profile",{})
    mmr=data.get("mmr_estimate",{}).get("estimate","Unknown")

    embed=discord.Embed(title="OpenDota Stats",color=discord.Color.blue())
    embed.add_field(name="Name",value=profile.get("personaname","N/A"))
    embed.add_field(name="MMR (estimate)",value=mmr)
    embed.add_field(name="Profile URL",value=profile.get("profileurl","N/A"))
    await ctx.send(embed=embed)

# ================= RUN =================
bot.run(TOKEN)