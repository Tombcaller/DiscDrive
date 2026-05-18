import discord
import io
import os
import sys
import time
import math
import hashlib
import requests

from config import REGULAR_CHUNK_SIZE, BASIC_CHUNK_SIZE, NITRO_CHUNK_SIZE
from db import save_new_file, save_chunk, get_chunks, get_file_info, delete_chunk, delete_file_info, get_file_channel_id

# ---------------------------------------------------- #

async def get_channel_from_name(name, guild):
    channel = discord.utils.get(guild.text_channels, name=name)
    if channel is None:
        channel = await guild.create_text_channel(name)
    return channel

async def get_channel_from_id(channelId, guild):
    channel = discord.utils.get(guild.text_channels, id=channelId)
    if channel is None:
        print("Somehow, the channel has gone missing...")
    return channel

# ---------------------------------------------------- #

# getting file hash for integrity checking #
def hash_file(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def status(msg):
    print(f"\r{msg:<69}", end="", flush=True)

# ---------------------------------------------------- #

# function to chunk and upload files from a path (-u) #
async def upload_file(fileId, channelName, filePath, guild):

    # checking if fileId already exists #
    if get_file_info(fileId):
        info = get_file_info(fileId)
        print(f'FileID already in database: "{info[0]}", {info[2]} chunk(s)')
        return

    # getting stats of file to add to db and for speed calc #
    fileSize = os.path.getsize(filePath)
    fileName = os.path.basename(filePath)
    chunkCount = math.ceil(fileSize / REGULAR_CHUNK_SIZE)

    print("Hashing file...")
    fileHash = hash_file(filePath)

    channel = await get_channel_from_name(channelName, guild)

    print(f'Uploading {fileName} as "{fileId}"...\nTotal chunks needed: {chunkCount}\n(File Size - {fileSize}B/{round(fileSize/1024**2, 2)}MiB)\n')

    # getting current time for speed calc #
    startTime = time.time()

    # chunking and sending file #
    with open(filePath, "rb") as infile:
        for i in range(chunkCount):
            chunk = infile.read(REGULAR_CHUNK_SIZE)
            file = discord.File(io.BytesIO(chunk), filename=f"{fileId}.{i+1}")

            status(f"Uploading chunk {i+1}/{chunkCount} ({(i+1)/chunkCount:.2%})")

            msg = await channel.send(file=file)
            save_chunk(fileId, msg.id, channel.id, i + 1)

    status(f"Finished uploading {chunkCount} chunks.")
    print("\n")

    # getting final time to find time elapsed #
    elapsed = time.time() - startTime
    print(f"Avg upload speed: {fileSize/10e6*8/elapsed:.2f} Mbps, took {elapsed:.2f}s")

    print("Saving file data to database.")
    save_new_file(fileId, fileName, fileSize, chunkCount, fileHash, channel.id)
    print("Upload complete.")

# ---------------------------------------------------- #

# function to download a file from a fileId to a specified path #
async def download_file(fileId, filePath, guild):

    # grabbing info from db about file and checking if it exists #
    fileInfo = get_file_info(fileId)

    if not fileInfo:
        print("fileID not found in database.")
        return
    
    fileName, fileSize, chunkCount = fileInfo

    channel = await get_channel_from_id(get_file_channel_id(fileId), guild)

    print(f"Downloading {fileName} ({fileSize} B, {chunkCount} chunks)")

    # getting start time for speed calc #
    startTime = time.time()
 
    # getting message ids of file chunks from db #
    chunkMessageIds = get_chunks(fileId)

    # writing chunks to file path
    with open(os.path.join(filePath, fileName), "wb") as outfile:
        for i in range(chunkCount):
            messageId = chunkMessageIds[i]

            # default to no message for error handling #
            msg = None

            # retrying 5 times per chunk in case of 503 etc #
            for attempt in range(5):
                try:
                    msg = await channel.fetch_message(messageId)
                    break
                except:
                    status(f"Error on chunk {i+1}, retrying (attempt {attempt+1})...\n")
                    time.sleep(1)

            # checking if message has expected format and downloading chunk then writing it to file #
            if msg and msg.attachments:
                status(f"Downloading chunk {i+1}/{chunkCount} ({(i+1)/chunkCount:.2%})")
                resp = requests.get(msg.attachments[0].url)
                outfile.write(resp.content)
            else:
                sys.stdout.write(f"Fatal errors during download of chunk {i+1}.")

    status(f"Finished downloading {chunkCount} chunks.")
    print("\n")

    # getting final time to find time elapsed #
    elapsed = time.time() - startTime
    print(f"Avg download speed: {fileSize/10e6*8/elapsed:.2f} Mbps, took {elapsed:.2f}s")

# ---------------------------------------------------- #


# very broken right now #
async def manual_upload_file(nitroTier, fileId, channelId, filePath):

    nitroTier = int(nitroTier)
    if nitroTier == 0:   chunkSize = REGULAR_CHUNK_SIZE
    elif nitroTier == 1: chunkSize = BASIC_CHUNK_SIZE
    elif nitroTier == 2: chunkSize = NITRO_CHUNK_SIZE
    else: print("Invalid Nitro tier (0-2)"); return

    fileSize = os.path.getsize(filePath)
    chunkCount = math.ceil(fileSize / chunkSize)
    fileName = os.path.basename(filePath)

    os.makedirs(os.path.join("output", f"{fileId}"), exist_ok = True)

    with open(filePath, "rb") as infile:

        for chunkIndex in range(chunkCount):
            chunk = infile.read(chunkSize)

            status(f"Saving {chunkIndex+1}/{chunkCount} ({(chunkIndex+1)/chunkCount:.2%})")

            with open(os.path.join("output", f"{fileId}", f"{fileId}.c{chunkIndex+1}"), "wb") as outfile:
                outfile.write(chunk)

            messageId = 0
            save_chunk(fileId, messageId, channelId, chunkIndex + 1)
    
    fileHash = "test"
    save_new_file(fileId, fileName, fileSize, chunkCount, fileHash, channelId)

# ---------------------------------------------------- #

async def remove_file(fileId, guild):
    startTime = time.time()

    channel = await get_channel_from_id(get_file_channel_id(fileId), guild)

    status(f"Grabbing message IDs for {fileId} from DB")
    chunkMessageIds = get_chunks(fileId)

    status(f"Deleting DB chunks")
    messages = []
    
    # deleting chunks and adding message objects to list for mass deletion #
    for msgId in chunkMessageIds:
        msg = await channel.fetch_message(msgId)
        messages.append(msg)
        delete_chunk(msgId)

    status(f"Deleting Discord message IDs")
    await channel.delete_messages(messages)

    status(f"Deleting file info from DB")
    delete_file_info(fileId)

    elapsed = time.time() - startTime
    print(f"\nFile deleted in {elapsed:.2f}s")
    

# ---------------------------------------------------- #