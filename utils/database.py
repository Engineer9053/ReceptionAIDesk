import sqlite3
from configs import DATABASE_PATH
from typing import List, Dict, Tuple, Any



def initialize_database() -> None:

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            first_name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            username TEXT NOT NULL,
            created TIMESTAMP DEFAULT (DATETIME('now')))
        """)

    connection.commit()

    connection.close()


def insert_into_users(user: Dict[str, Any]) -> None:

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO users ( telegram_id, first_name, last_name, username)
        VALUES ( ?, ?, ?, ?)
        """,
        (
            user["telegram_id"], user["first_name"], user["last_name"], user["username"]
        )
    )

    connection.commit()

    connection.close()


def select_from_users(filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:

    connection = sqlite3.connect(DATABASE_PATH)
    cursor = connection.cursor()

    query = """ SELECT id, telegram_id, first_name, last_name, username, created FROM users """
    
    parameters = []

    if filters:

        conditions = []

        for field, value in filters.items():

            if isinstance(value, Tuple) and len(value) == 2:

                parameters.extend(value)
                conditions.append(f"{field} BETWEEN ? AND ?")
            
            else:

                parameters.append(value)
                conditions.append(f"{field} = ?")
        
        query += " WHERE " + " AND ".join(conditions)
    
    query += " ORDER BY created"

    cursor.execute(query, parameters)

    rows = cursor.fetchall()
    columns = [description[0] for description in cursor.description]

    connection.close()

    users = [dict(zip(columns, row)) for row in rows]

    return users


initialize_database()
