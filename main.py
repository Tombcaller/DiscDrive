# ---------------------------------------------------- #

import sys
import discord

from config import BOT_TOKEN, GUILD_ID
from db import list_files
from storage import upload_file, download_file, remove_file

# ---------------------------------------------------- #

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# ---------------------------------------------------- #

@client.event
async def on_ready():
    print(f"Sucessfully logged in as bot: {client.user}\n")
    guild = client.get_guild(GUILD_ID)

    # checking args to allocate task #
    match sys.argv[1]:

        # -u | uploading file #
        case "-u":
            await upload_file(sys.argv[2], sys.argv[3], sys.argv[4], guild)

        # -c | chunking file into regular/basic/nitro chunks for manual sending #
        case "-c":
            await chunk_file(sys.argv[2], sys.argv[3])

        # -d | downloading file #
        case "-d":
            await download_file(sys.argv[2], sys.argv[3], guild)

        case "-r":
            await remove_file(sys.argv[2], guild)

        # -ls | listing files in database #
        case "-ls":
            rows = list_files()
            if not rows: print("No files in database.")
            else:
                print("Files in database:")
                for fileId, fileName, fileSize in rows:
                    print(f"FileID: {fileId} | Name: {fileName} | Size: {fileSize} B ({round(fileSize/1024**2, 2)} MiB)")
        
        # invalid arg 1 error #
        case _:
            print("Invalid args. Usage is -u <id> <channel> <path> | -d <id> <path> | -r <id> | -ls")

    # closing client after task completed #
    await client.close()

# ---------------------------------------------------- #

client.run(BOT_TOKEN)

# ---------------------------------------------------- #