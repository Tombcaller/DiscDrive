import json
import os

# getting dir of script for relative paths #
scriptDir = os.path.dirname(os.path.abspath(__file__))

# loading config from json file #
with open(os.path.join(scriptDir, "config.json"), "r") as f:
    config = json.load(f)

# loading items from config file #
BOT_TOKEN = config["bot_token"]
CHANNEL_ID = config["channel_id"]
CHUNK_SIZE = config["chunk_size"]
DB_NAME = config["database_name"]