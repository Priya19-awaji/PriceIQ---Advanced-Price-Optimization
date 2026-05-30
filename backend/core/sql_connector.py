import os
import urllib.parse
from sqlalchemy import create_engine
import pandas as pd

def get_sql_engine():
    """
    Creates and returns a SQLAlchemy engine for SQL Server based on environment variables.
    """
    db_server = os.getenv("DB_SERVER", "localhost")
    db_name = os.getenv("DB_NAME", "PriceIQ")
    db_user = os.getenv("DB_USER", "sa")
    db_password = os.getenv("DB_PASSWORD", "")

    # For SQL Server using standard authentication
    # Using ODBC Driver 17 for SQL Server. Adjust driver name if needed.
    driver = "ODBC Driver 17 for SQL Server"
    
    # URL encode password in case it contains special characters
    quoted_password = urllib.parse.quote_plus(db_password)

    conn_str = f"mssql+pyodbc://{db_user}:{quoted_password}@{db_server}/{db_name}?driver={driver}"
    
    engine = create_engine(conn_str)
    return engine

def load_data_from_sql() -> pd.DataFrame:
    """
    Connects to the SQL Server and loads the live data into a pandas DataFrame.
    This acts as a drop-in replacement for the CSV file.
    """
    engine = get_sql_engine()
    
    # Replace 'SalesData' with your actual table or view name
    table_name = os.getenv("DB_TABLE", "SalesData")
    
    print(f"[SQL] Fetching live data from {table_name}...")
    
    query = f"SELECT * FROM {table_name}"
    
    df = pd.read_sql(query, engine)
    print(f"[SQL] Successfully loaded {len(df)} rows.")
    
    return df
