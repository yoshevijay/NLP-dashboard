from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import pandas as pd
import pymysql
import os
from dotenv import load_dotenv
from typing import List
import requests
import json

app = FastAPI()
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

DB_configure={
    "host": "localhost",
    "user": "root",
    "password": "Ge00@mini070803",
    "database": "amazon_prime_db",
}

class QueryRequest(BaseModel):
    query: str
    table_name: str
    columns: List[str]

def text_to_sql(user_query, table_name, columns):#nlp to sql conversion
    try:
        if not user_query.strip():
            return "ERROR: Empty user query"

        if not columns:
            return "ERROR: No columns provided for SQL generation"

        column_list = ','.join(columns)
        prompt = f"""
        Convert the following natural language query to a valid MySQL SQL query.
        Table name: `{table_name}` which has the following columns: {column_list}.
        
        Return ONLY the SQL query without explaination, markdown, or formatting.

        Query: "{user_query}"
        """

        url = "https://generativelanguage.googleapis.com/v1beta1/models/gemini-pro:generateContent"
        headers = {"Content-Type": "application/json"}
        params = {"key": os.getenv("GEMINI_API_KEY")}
        body = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }
        print(f"=== PROMPT SENT TO GEMINI ===\n{prompt}\n")

        response = requests.post(url, headers=headers, params=params, json=body)
        data = response.json()

        print(f"=== GEMINI RESPONSE ===\n{json.dumps(data, indent=2)}\n")

        sql_query = ""
        try:
            candidates = data.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}.get("parts",[]))
                if parts:
                    sql_query = parts[0].get("text", "").strip()
        except Exception as e:
            print(f"Error parsing Gemini response: {e}")

        print(f"=== GEMINI RESPONSE ===\n{sql_query}")

        return sql_query if sql_query else "ERROR: Empty SQL generated"

    except Exception as e:
        print(f"Gemini API Error: {e}")
        return f"Error:{e}"

def execute_query(sql_query):
    try:
        print(f"Executing SQL: {sql_query}")
        conn = pymysql.connect(**DB_configure)#connects to mysql
        cursor = conn.cursor()

        cursor.execute(sql_query)
        result = cursor.fetchall()#fetches all results

        conn.close()
        return result
    except Exception as e:
        print(f"Database Error: {e}")
        return str(e) #returns an error if the query fails

@app.get("/")
async def root():
    return {"message": "Hello, FastAPI!"}

@app.post("/search")  # API endpoint
def search(request: QueryRequest):
    user_query = request.query
    table_name = request.table_name
    columns = request.columns
    sql_query = text_to_sql(user_query, table_name, columns)  #Convert NLP query to SQL

    if sql_query.startswith("ERROR"):
        return {"query": "", "result": f"{sql_query}"}

    try:
        connection = pymysql.connect(**DB_configure)
        cursor = connection.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchall()
        cols = [desc[0] for desc in cursor.description]
        result = [dict(zip(cols, row)) for row in rows]
        return {"query": sql_query, "result": result}
    except Exception as e:
        return {"query": sql_query, "result": f"(1065, '{e}')"}

@app.post("/upload")
async def upload_dataset(file: UploadFile = File(...)): #accepts dataset into backend
    try:
        file_location = f"temp_{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())

        if file.filename.endswith('.csv'):
            df = pd.read_csv(file_location)
        elif file.filename.endswith(('.xls', '.xlsx')):
            df = pd.read_excel(file_location)
        else:
            return{"error": "Unsupported file type! Please upload CSV or Excel files."}

        df = df.fillna('NULL')

        connection = pymysql.connect(**DB_configure) #connects to mysql
        cursor = connection.cursor()

        table_name = file.filename.rsplit('.', 1)[0].replace(' ', '_').lower()

        cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")

        create_table_query = f"""
        CREATE TABLE `{table_name}` (
            {', '.join([f'`{col}` TEXT' for col in df.columns])}
        )
        """

        cursor.execute(create_table_query)

        for _, row in df.iterrows():
            placeholders = ', '.join(['%s'] * len(row))
            sql = f"INSERT INTO `{table_name}` ({', '.join([f'`{col}`' for col in df.columns])}) VALUES ({placeholders})"
            cursor.execute(sql, tuple(row))

        connection.commit()
        cursor.close()
        connection.close()

        os.remove(file_location)

        latest_table_uploaded = table_name

        return{"message": f"uploaded {len(df)} rows into `{table_name}` successfully!"}

    except Exception as e:
        return {"error": str(e)}
