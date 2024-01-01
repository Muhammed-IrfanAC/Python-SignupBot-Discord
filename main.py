import sqlite3
import requests
import interactions
from interactions import Embed, SlashCommandChoice, slash_option
import os
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

TOKEN = os.getenv('TOKEN')
api_auth = os.getenv('AUTH')

client= interactions.Client(token=TOKEN)

# Database creation
def database_create():
    global dbCursor
    global sqlConnect
    sqlConnect = sqlite3.connect('sqldatabase.db')
    dbCursor = sqlConnect.cursor()

async def playerGet(player_tag):
    url = 'https://api.clashofclans.com/v1/players/%23' + player_tag
    response = requests.get(url, headers=header)
    player_data = response.json()
    return player_data

events=[]
event_embed_id={}
event_channel_id={}

# API header
header ={'Authorization': f'{api_auth}'}

class signupEmbed():
    def __init__(self, event_name):
        self.embed = interactions.Embed(title=f'{event_name} Roster', color=0xfa0000)
        self.coloms=["ID","PLAYER NAME","PLAYER TAG","TH","DISCORD"]
        self.user_data=[]
        self.th_data=[]

    def add_user(self, id, player_name, player_tag, player_th, player_discord, th_count):
        self.user_data=[]
        self.th_data=[]
        self.th_data=th_count
        self.user_data.append({"id":id,"name":player_name,"tag":player_tag,"th":player_th,"discord":player_discord})

    def update_embed(self):
        self.embed.description=' | '.join(self.coloms)

        for user_data in self.user_data:
            id=user_data["id"]
            name=user_data["name"]
            tag=user_data["tag"]
            th=user_data["th"]
            discord=user_data["discord"]

            self.embed.add_field(name=f'{id}   {name}   {tag}   {th}   {discord}', value=" ", inline=False)

        footer_text = "   ".join([f'{row[0]}-{row[1]}' for row in self.th_data])
        self.embed.set_footer(text=footer_text)
        return self.embed

    def create_embed(self):
        return self.embed
    
class PlayerEmbed():
    def __init__(self, player_name, player_tag, player_th):
        self.player_name=player_name
        self.player_tag=player_tag
        self.player_th=player_th
    def embed_create(self):
        embed=Embed(title='Successfully Signed Up!', color=0xfa0000)
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/148/148767.png")
        embed.add_field(name="Name", value=f"{self.player_name}")
        embed.add_field(name="Tag", value=f"{self.player_tag}")
        embed.add_field(name="Townhall", value=f"{self.player_th}")
        return embed
       
@client.listen()
async def on_ready():
    print('Logged in as {0.user}'.format(client))

database_create()

@interactions.slash_command(name="ping")
async def _ping(ctx:interactions.SlashContext):
    await ctx.send('Beep Boop!')

@interactions.slash_command(name='create', description='Create signup embed')
@slash_option(name='event_name', description='Name of the event', required=True, opt_type=interactions.OptionType.STRING)
@slash_option(name="channel_name", description="Enter target channel name", required=True, opt_type=interactions.OptionType.CHANNEL)
async def _signupPost(ctx:interactions.SlashContext, event_name, channel_name: interactions.Guild):

    # Table creation
    createTableQuery = f"""CREATE TABLE IF NOT EXISTS {event_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,player_name,player_tag,th_level, discord_id)"""
    dbCursor.execute(createTableQuery)
    await ctx.send(f'{event_name} created in the cahnnel {channel_name.name}', ephemeral=True)
    sqlConnect.commit()

    global signup_embed
    signup_embed = signupEmbed(event_name=event_name)
    embed=signup_embed.create_embed()
    initial_embed=await channel_name.send(embed=embed)

    event_embed_id[event_name]=initial_embed.id
    event_channel_id[event_name]=channel_name.id
    events.append(event_name)

@interactions.slash_command(name='signup')
@slash_option(name="player_tag", required=True, opt_type=interactions.OptionType.STRING, description="Please enter the Player Tag")
@slash_option(name="event_name", required=True, opt_type=interactions.OptionType.STRING, description="Please select an Event", autocomplete=True)
async def _sign_up(ctx:interactions.SlashContext, player_tag: str, event_name: str):
    player_data = await playerGet(player_tag[1:])
    player_name = player_data['name']
    if dbCursor.execute(f'SELECT 1 FROM {event_name} WHERE player_tag = ?',(player_tag,)).fetchone():
        await ctx.send('```'+player_name+' already signed up!```', ephemeral=True)
    else:
        discord_name=ctx.author.username
        player_th = player_data['townHallLevel']
        
        dbCursor.execute(f"""INSERT INTO {event_name} 
                        (player_name,player_tag,th_level,discord_id) VALUES (?,?,?,?)""",
                        (player_name,player_tag,player_th,discord_name,))
        
        dbCursor.execute(f'SELECT * FROM {event_name} ORDER BY id DESC')
        rows = dbCursor.fetchone()

        #TH count
        dbCursor.execute(f"""SELECT th_level, COUNT(*) AS count 
                         FROM {event_name} GROUP BY th_level""")
        th_count=dbCursor.fetchall()

        player_embed = PlayerEmbed(player_name=rows[1], player_tag=rows[2], player_th=rows[3])
        embed=player_embed.embed_create()
        await ctx.send(embed=embed)

        original_embed_id=event_embed_id.get(event_name)
        original_channel_id=event_channel_id.get(event_name)
        original_channel_object=client.get_channel(original_channel_id)
    
        signup_embed.add_user(id=rows[0],player_name=rows[1],player_tag=rows[2],player_th=rows[3],player_discord=rows[4], th_count=th_count)
        updated_embed=signup_embed.update_embed()
        message=await original_channel_object.fetch_message(original_embed_id)
        await message.edit(embed=updated_embed)

@_sign_up.autocomplete('event_name')
async def autocompleteOptions(ctx: interactions.AutocompleteContext):
    await ctx.send(choices=[
        {
            "name":event_name,
            "value":event_name
        } for event_name in events
    ])

@interactions.slash_command(name='export')
@slash_option(name="event_name", required=True, opt_type=interactions.OptionType.STRING, description="Provide the Event name", autocomplete=True)
async def _export(ctx: interactions.SlashContext, event_name):
    # Fetch all entries from the database
    dbCursor.execute(f'SELECT * FROM {event_name}')
    rows = dbCursor.fetchall()

    # Create a DataFrame from the database entries
    df = pd.DataFrame(rows, columns=['ID', 'Player Name', 'Player Tag', 'TH Level', 'Discord ID'])

    # Export DataFrame to Excel file
    excel_file_path = f'{event_name}_entries.xlsx'
    df.to_excel(excel_file_path, index=False)

    # Send the Excel file
    await ctx.send(file=interactions.File(excel_file_path))

@_export.autocomplete('event_name')
async def autocompleteOptions(ctx: interactions.AutocompleteContext):
    await ctx.send(choices=[
        {
            "name":event_name,
            "value":event_name
        } for event_name in events
    ])

client.start()