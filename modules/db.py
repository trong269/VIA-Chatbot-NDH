import psycopg2
from psycopg2 import sql, DatabaseError
from typing import Optional
from configs.config import load_config
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
import logging

logger = logging.getLogger("ChatbotNDH")

config = load_config()



class Database_data: # Database_data
    def __init__(self):
        self.host = config['database_data']["host"]
        self.dbname = config['database_data']["database"]
        self.user = config['database_data']["user"]
        self.password = config['database_data']["password"]
        self.port = config['database_data']["port"]
        self.conn, self.cursor = self.connect()
    
    def connect(self):
        try:
            conn = psycopg2.connect(
                host=self.host,
                database=self.dbname,
                user=self.user,
                password=self.password,
                port=self.port
            )
            cursor = conn.cursor()
            logger.info(f"✅ DB {self.dbname} connected.")
            return conn, cursor
        except Exception as e:
            logger.info(f"❌ DB {self.dbname} connect failed", e)
            return None, None

    def close(self):
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
        logger.info(f"🔒 DB {self.dbname} close!")

