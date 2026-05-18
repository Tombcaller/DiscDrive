import os

DB_NAME = "data.db"
REGULAR_CHUNK_SIZE = 10485760
BASIC_CHUNK_SIZE = 52428800
NITRO_CHUNK_SIZE = 524288000

# getting dir of script for relative paths #
scriptDir = os.path.dirname(os.path.abspath(__file__))

# loading bot config from txt file #
configPath = os.path.join(scriptDir, "botconfig.txt")

# grabbing bot config from botconfig.txt if it exists #
try:
    with open(configPath, "r") as f:
        lines = f.readlines()

    if len(lines) < 2:
        raise Exception

    BOT_TOKEN = lines[0].strip()
    GUILD_ID = int(lines[1].strip())

# making new botconfig.txt file if it does not exist #
except:
    print("Bot config not found or incomplete, building new config file")

    BOT_TOKEN = input("Enter bot token:\n").strip()
    GUILD_ID = int(input("Enter server ID:\n").strip())

    with open(configPath, "w") as f:
        f.write(f"{BOT_TOKEN}\n{GUILD_ID}\n")

    print("New config saved to botconfig.txt")