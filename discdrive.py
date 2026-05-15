import discord
import io
import os
import sqlite3
import requests
import math
import time
import sys
import json
import hashlib

# --------------------------------------------------------- #
def setup_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        fileId TEXT PRIMARY KEY,
        fileHash TEXT,
        fileName TEXT,
        fileSize INTEGER,
        chunkCount INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fileChunks (
        fileId TEXT,
        messageId TEXT PRIMARY KEY,
        chunkIndex INTEGER,
        FOREIGN KEY (fileId) REFERENCES files(fileId)
    )
    """)

    conn.commit()

# --------------------------------------------------------- #

# func to hash files for integrity checking #
def hash_file(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()

# saving new file data to db after upload #
def saveNewFile(fileId, fileName, fileSize, chunkCount, fileHash):
    cursor.execute("INSERT OR IGNORE INTO files (fileId, fileName, fileSize, chunkCount, fileHash) VALUES (?, ?, ?, ?, ?)", [fileId, fileName, fileSize, chunkCount, fileHash])
    conn.commit()

# saving chunk messageId and chunk index to db for redownloading #
def saveChunk(fileId, messageId, chunkIndex):
    cursor.execute("""
        INSERT INTO fileChunks (fileId, messageId, chunkIndex)
        VALUES (?, ?, ?)
    """, (fileId, messageId, chunkIndex))
    conn.commit()

# getting list of chunks (messageIds) for redownloading a fileId #
def getChunks(fileId):
    cursor.execute("""
        SELECT messageId FROM fileChunks
        WHERE fileId = ?
        ORDER BY chunkIndex
    """, [fileId])

    return [row[0] for row in cursor.fetchall()]

# --------------------------------------------------------- #

# grabbing script dir for relative file paths #
scriptDir = os.path.dirname(os.path.abspath(__file__))

# opening config file and loading variables #
configPath = os.path.join(scriptDir, "config.json")

with open(configPath, "r") as f:
    config = json.load(f)
    BOT_TOKEN = config["bot_token"]
    CHANNEL_ID = config["channel_id"]
    CHUNK_SIZE = config["chunk_size"]

# --------------------------------------------------------- #

intents = discord.Intents.all()
client = discord.Client(intents=intents)

# --------------------------------------------------------- #

# database setup #
dbPath = os.path.join(scriptDir, "files.db")

# grabbing connection and cursor then setting up db if it doesnt exist #
conn = sqlite3.connect(dbPath)
cursor = conn.cursor()
setup_db()

# --------------------------------------------------------- #

async def uploadFile(filePath, fileId, channel):

    # checking if fileId already exists in db to prevent dupes #
    cursor.execute("""
        SELECT fileName, fileSize, chunkCount FROM files
        WHERE fileId = ?
    """, [fileId])

    row = cursor.fetchall()

    if row:
        fileName, fileSize, chunkCount = row[0]
        print(f"FileID already in database: \"{fileName}\", {chunkCount} chunk(s)")
        return
       
   # getting file info for db and stats display #
    fileSize = os.path.getsize(filePath)
    fileName = os.path.basename(filePath)
    chunkCount = math.ceil(fileSize/CHUNK_SIZE)

    # hashing file for integrity checking #
    print("Hashing file...")
    fileHash = hash_file(filePath)

    print(f"Uploading {fileName} as \"{fileId}\"...\nTotal chunks needed: {chunkCount}\n(File Size - {fileSize}B/{round(fileSize/1024**2,2)}MiB)\n")
    
    # for speed display #
    startTime = time.time()
    
    # chunking and uploading file, saving chunk messageIds to db for redownloading #
    with open(filePath, 'rb') as infile:
        for currentChunkNum in range(chunkCount):

            # reading chunk from file and uploading #
            chunk = infile.read(CHUNK_SIZE)
            file=discord.File(io.BytesIO(chunk),filename=f"[{currentChunkNum+1} - {chunkCount}]")

            sys.stdout.write(f"\rUploading file chunk {currentChunkNum+1}/{chunkCount} ({(currentChunkNum+1)/chunkCount:.2%})")
            sys.stdout.flush()

            msg = await channel.send(file=file)
            saveChunk(fileId, msg.id, currentChunkNum+1)

        sys.stdout.write(f"\rFinished uploading {chunkCount} file chunks.")
        print("\n")

    # calculating total time elapsed and avg upload speed in Mbps #
    timeElapsed = time.time() - startTime
    print(f"Avg upload speed: {fileSize/1000**2/timeElapsed}Mbps, took {timeElapsed:.2f} seconds.") 

    print("Saving new file data to database.")
    saveNewFile(fileId, fileName, fileSize, chunkCount, fileHash)
    print("File upload complete.")

# --------------------------------------------------------- #

async def downloadFile(filePath, fileId, channel):
    
    # grabbing file info from db #
    cursor.execute("""
        SELECT fileName, fileSize, chunkCount FROM files
        WHERE fileId = ?
    """, [fileId])

    row = cursor.fetchall()

    # checking if fileId exists and grabbing info from db #
    try:
        fileName, fileSize, chunkCount = row[0]
    except: 
        print("fileID not found in database.")
        return

    print(f"Downloading {fileName} ({fileSize} B, {chunkCount} chunks)")

    startTime = time.time()

    with open(os.path.join(filePath, fileName), "wb") as file:
        
        chunkMessageIds = getChunks(fileId)

        print("Refreshing CDN links")
        for i in range(chunkCount):

            messageId = chunkMessageIds[i]
            msg = await channel.fetch_message(messageId)

            if msg.attachments:
                chunkURL = msg.attachments[0].url

                sys.stdout.write(f"\rDownloading file chunk {i+1}/{chunkCount}")
                sys.stdout.flush()

                resp = requests.get(chunkURL)
                file.write(resp.content)

        sys.stdout.write(f"\rFinished downloading {chunkCount} file chunks.")
        print("\n")

    print(f"downloaded {fileName}")

    timeElapsed = time.time() - startTime

    print(f"Avg download speed: {fileSize/1000**2/timeElapsed}Mbps, took {timeElapsed:.2f} seconds.")

# --------------------------------------------------------- #

@client.event
async def on_ready():
    print(f'Logged in as {client.user}\n')
    channel = client.get_channel(CHANNEL_ID)
    
    if sys.argv[1] == "-u":
        filePath = sys.argv[2]
        fileId = sys.argv[3]
        await uploadFile(filePath, fileId, channel)
        
    elif sys.argv[1] == "-d":
        filePath = sys.argv[2]
        fileId = sys.argv[3]
        await downloadFile(filePath, fileId, channel)

    elif sys.argv[1] == "-l":

        cursor.execute("SELECT fileId, fileName, fileSize FROM files")
        rows = cursor.fetchall()

        if not rows:
            print("No files in database.")
        else:
            print("Files in database:")
            for fileId, fileName, fileSize in rows:
                print(f"FileID: {fileId} | Name: {fileName} | Size: {fileSize} B ({round(fileSize/1024**2,2)} MiB)")

    else:
        print("invalid args ")

    await client.close()

# --------------------------------------------------------- #

client.run(BOT_TOKEN)

