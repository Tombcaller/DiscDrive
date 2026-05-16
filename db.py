import sqlite3
import os
from config import DB_NAME

# getting dir of script for relative paths #
scriptDir = os.path.dirname(os.path.abspath(__file__))
dbPath = os.path.join(scriptDir, DB_NAME)

# creating connection and cursor for db interactions #
conn = sqlite3.connect(dbPath)
cursor = conn.cursor()

# setup a fresh db if it doesn't exist #
def setup_db():
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files (
            fileId TEXT PRIMARY KEY,
            fileHash TEXT,
            fileName TEXT,
            fileSize INTEGER,
            chunkCount INTEGER,
            channelId INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS fileChunks (
            fileId TEXT,
            messageId TEXT PRIMARY KEY,
            channelId INTEGER,
            chunkIndex INTEGER,
            FOREIGN KEY (fileId) REFERENCES files(fileId)
        )
    """)
    conn.commit()

# add new file to file info table after full upload #
def save_new_file(fileId, fileName, fileSize, chunkCount, fileHash, channelId):
    cursor.execute(
        "INSERT OR IGNORE INTO files (fileId, fileName, fileSize, chunkCount, fileHash, channelId) VALUES (?, ?, ?, ?, ?, ?)",
        [fileId, fileName, fileSize, chunkCount, fileHash, channelId]
    )
    conn.commit()

# save the data of an uploaded chunk after upload #
def save_chunk(fileId, messageId, channelId, chunkIndex):
    cursor.execute(
        "INSERT INTO fileChunks (fileId, messageId, channelId, chunkIndex) VALUES (?, ?, ?, ?)",
        (fileId, messageId, channelId, chunkIndex)
    )
    conn.commit()

# get message ids of chunks of a fileId for downloading #
def get_chunks(fileId):
    cursor.execute(
        "SELECT messageId FROM fileChunks WHERE fileId = ? ORDER BY chunkIndex",
        [fileId]
    )
    return [row[0] for row in cursor.fetchall()]

# get info of file for redownloading #
def get_file_info(fileId):
    cursor.execute(
        "SELECT fileName, fileSize, chunkCount FROM files WHERE fileId = ? ",
        [fileId]
    )
    row = cursor.fetchall()
    return row[0] if row else None

# delete chunk from db #
def delete_chunk(messageId):
    cursor.execute(
        "DELETE FROM fileChunks WHERE messageId = ?",
        [messageId]
    )
    conn.commit()

# delete chunk from db #
def delete_file_info(fileId):
    cursor.execute(
        "DELETE FROM files WHERE fileId = ?",
        [fileId]
    )
    conn.commit()

def get_file_channel_id(fileId):
    cursor.execute(
        "SELECT channelId FROM files WHERE fileId = ? ",
        [fileId]
    )
    row = cursor.fetchone()
    return row[0] if row else None

# list all files in db #
def list_files():
    cursor.execute("SELECT fileId, fileName, fileSize FROM files ORDER BY fileId")
    return cursor.fetchall()

# calling setup function to make db if it doesn't exist #
setup_db()