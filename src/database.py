"""
File: database.py

Purpose: Creates a database based on portfolio
list with tickers inputted by user. 

"""
import sqlite3

connection = sqlite3.connect("stocks.db")
cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS portfolio (
        ticker TEXT NOT NULL,
        date TEXT NOT NULL,
        open INT NOT NULL,
        high INT NOT NULL,
        low INT NOT NULL,
        close INT NOT NULL,
        volume INT NOT NULL
        )
    """)

# 4. Save (commit) your changes
connection.commit()

# 5. Always close the connection when finished
connection.close()
