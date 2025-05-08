##################################################################################################
### 1) IMPORTING LIBRARIES
##################################################################################################

import requests
import re
import json
import pandas as pd
import numpy as np
from flask import Flask, jsonify
import logging
import os
from pandas import json_normalize
from datetime import datetime
import pandas as pd
import boto3
import botocore
import time
import s3fs

# Initialize Flask app
app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

##################################################################################################
### 2) VARIABLES DE ENTORNO
##################################################################################################

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY","eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjMyOTEwMjE3NiwiYWFpIjoxMSwidWlkIjoyNTgzODY5NCwiaWFkIjoiMjAyNC0wMy0wNVQyMDowNDo1Mi4zNzJaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6MTAwMjkxMDQsInJnbiI6InVzZTEifQ.4FXViuW0ZIOUBuCBt3DVBKwtaj3B9wrO3tgO7mrpjTk")
BOOKING_BOARD_ID = os.getenv("BOOKING_BOARD_NUMBER",8883743273)
SUB_BOOKING_BOARD_ID = os.getenv("SUB_BOOKING_BOARD_ID","group_title")
BUCKET_NAME = os.getenv("BUCKET_NAME","monday-booking-boards")
STORED_VARIABLES_SUB_FOLDER = os.getenv("STORED_VARIABLES_SUB_FOLDER","stored_variables")
OUTPUT_FILE_NAME = os.getenv("OUTPUT_FILE_NAME","bookings_ps_df_2025")
OUTPUT_FILE_NAME_LAST_UPDATE = os.getenv("OUTPUT_FILE_NAME","bookings_ps_items_last_update_stored_2025")

##################################################################################################
### 3) MONDAY & AWS-S3 CLIENTS
##################################################################################################

apiKey = MONDAY_API_KEY
apiUrl = "https://api.monday.com/v2"
headers = {"Authorization" : apiKey}
s3 = boto3.client('s3')

##################################################################################################
### 4) FUNCTIONS DEFINITIONS
##################################################################################################

def query_monday_graphql_paginated(board_number, sub_board_id, cursor=None):
    """Realiza una consulta GraphQL a monday.com con paginación."""
    query = f'''
    {{
      boards(ids: {board_number}) {{
        groups(ids: ["{sub_board_id}"]) {{
          items_page(limit: 500, cursor: {"null" if cursor is None else '"' + cursor + '"'}) {{
            cursor  
            items {{
              id
              updated_at
            }}
          }}
        }}
      }}
    }}
    '''
    # Configurar la solicitud
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": MONDAY_API_KEY
    }
    
    # Ejecutar la consulta
    response = requests.post(url, json={"query": query}, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_all_items(board_number, sub_board_id):
    """Itera sobre todas las páginas y devuelve un DataFrame con todos los datos."""
    all_items = []
    cursor = None  # Iniciar sin cursor para la primera página

    while True:
        data = query_monday_graphql_paginated(board_number, sub_board_id, cursor)
        groups = data.get("data", {}).get("boards", [])[0].get("groups", [])
        if not groups:
            break
        
        # Obtener los items de la página actual
        items = groups[0].get("items_page", {}).get("items", [])
        all_items.extend(items)
        
        # Obtener el cursor para la siguiente página
        cursor = groups[0].get("items_page", {}).get("cursor")
        if not cursor:
            break  # Salir del bucle si no hay más páginas

    # Convertir los datos a DataFrame
    return pd.DataFrame(all_items)

def query_monday_graphql_paginated_with_subitems(board_number, sub_board_id, cursor=None):
    """Realiza una consulta GraphQL a monday.com para obtener subitems con paginación."""
    query = f'''
    {{
      boards(ids: {board_number}) {{
        groups(ids: ["{sub_board_id}"]) {{
          items_page(limit: 500, cursor: {"null" if cursor is None else '"' + cursor + '"'}) {{
            cursor  
            items {{
              id
              subitems {{
                id
                updated_at
              }}
            }}
          }}
        }}
      }}
    }}
    '''
    # Configurar la solicitud
    url = "https://api.monday.com/v2"
    headers = {
        "Authorization": MONDAY_API_KEY
    }
    
    # Ejecutar la consulta
    response = requests.post(url, json={"query": query}, headers=headers)
    response.raise_for_status()
    return response.json()

def fetch_all_items_with_subitems(board_number, sub_board_id):
    """Itera sobre todas las páginas y devuelve un DataFrame con todos los datos."""
    all_items = []
    cursor = None  # Iniciar sin cursor para la primera página

    while True:
        data = query_monday_graphql_paginated_with_subitems(board_number, sub_board_id, cursor)
        groups = data.get("data", {}).get("boards", [])[0].get("groups", [])
        if not groups:
            break
        
        # Obtener los items de la página actual
        items = groups[0].get("items_page", {}).get("items", [])
        
        # Procesar cada ítem y sus subitems
        for item in items:
            item_id = item.get("id")
            subitems = item.get("subitems", [])
            for subitem in subitems:
                all_items.append({
                    "item_id": item_id,
                    "subitem_id": subitem.get("id"),
                    "subitem_updated_at": subitem.get("updated_at")
                })
        
        # Obtener el cursor para la siguiente página
        cursor = groups[0].get("items_page", {}).get("cursor")
        if not cursor:
            break  # Salir del bucle si no hay más páginas

    # Convertir los datos a DataFrame
    return pd.DataFrame(all_items)

def safe_read_latest_version(bucket, prefix, base_filename):
    s3 = boto3.client('s3')

    try:
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        files = response.get('Contents', [])

        # Filtrar archivos que matcheen el patrón base_filename_TIMESTAMP.parquet
        pattern = re.compile(f"{base_filename}_(\\d+)\\.parquet$")
        matched_files = [
            (obj['Key'], int(pattern.search(obj['Key']).group(1)))
            for obj in files if pattern.search(obj['Key'])
        ]

        if not matched_files:
            print(f"[INFO] No versioned files found for prefix: {prefix}")
            return pd.DataFrame()

        # Ordenar por timestamp descendente y elegir el último
        matched_files.sort(key=lambda x: x[1], reverse=True)
        latest_key = matched_files[0][0]
        s3_path = f"s3://{bucket}/{latest_key}"

        print(f"[INFO] Reading latest file: {s3_path}")
        return pd.read_parquet(s3_path).drop_duplicates()

    except botocore.exceptions.ClientError as e:
        print(f"[ERROR] Failed to list or read S3 files: {e}")
        return pd.DataFrame()

def storing_stored_variables_s3(df, file_name, bucket_name=BUCKET_NAME, folder=STORED_VARIABLES_SUB_FOLDER):
    import time
    timestamp = int(time.time())
    filename = f"{file_name}_{timestamp}.parquet"
    s3_path = f"s3://{bucket_name}/{folder}/{filename}"
    df.to_parquet(s3_path, index=False)
    print(f"[INFO] File saved to: {s3_path}")

##################################################################################################
### 5) MAIN FUNCTION
##################################################################################################
@app.route('/run', methods=['POST'])
def run_etl():
    try:
        ##################################################################################################
        ### 1) LAST UPDATE PER ROW, TO COMPARE WITH LAST LECTURE
        ##################################################################################################
        bookings_ps_items_last_update_stored = safe_read_latest_version(
        bucket="monday-booking-boards",
        prefix="stored_variables/",
        base_filename=OUTPUT_FILE_NAME_LAST_UPDATE
        )
        
        if bookings_ps_items_last_update_stored.empty:
            bookings_ps_items_last_update_stored = pd.DataFrame(columns = ['id','updated_at'])
        
        bookings_ps_items_last_update = fetch_all_items(BOOKING_BOARD_ID, SUB_BOOKING_BOARD_ID)
        
        bookings_ps_items_last_update['updated_at'] = pd.to_datetime(bookings_ps_items_last_update['updated_at'], format="%Y-%m-%dT%H:%M:%SZ")
        
        bookings_ps_items_last_update['updated_at_stored'] = bookings_ps_items_last_update['id'].map(bookings_ps_items_last_update_stored.set_index('id')['updated_at'])
        
        bookings_ps_items_last_update['filter'] = bookings_ps_items_last_update['updated_at'] == bookings_ps_items_last_update['updated_at_stored']
        
        filtered_bookings_ps_items_to_update_or_read =  bookings_ps_items_last_update[bookings_ps_items_last_update['filter']==False]['id'].to_list()
        
        filtered_bookings_ps_items_to_delete = bookings_ps_items_last_update_stored[~bookings_ps_items_last_update_stored['id'].isin(bookings_ps_items_last_update['id'].unique())]['id'].to_list()
        
        print('Bookings:')
        print(filtered_bookings_ps_items_to_update_or_read)
        print(filtered_bookings_ps_items_to_delete)
        
        ##################################################################################################
        ### 2) READING FROM THE BOARD
        ##################################################################################################
    
        bookings_ps_df = safe_read_latest_version(
            bucket="monday-booking-boards",
            prefix="stored_variables/",
            base_filename=OUTPUT_FILE_NAME
        )
        
        if bookings_ps_df.empty:
            bookings_ps_df = pd.DataFrame()
        
        new_bookings_ps_df = pd.DataFrame()
        
        for booking in filtered_bookings_ps_items_to_update_or_read:
        
            text_ids = str(booking)
        
            query_2 = f'''
            {{
              boards(ids: {BOOKING_BOARD_ID}) {{
                groups(ids: ["{SUB_BOOKING_BOARD_ID}"]) {{
                  items_page(limit:1 , query_params: {{ids: [{booking}]}}) {{
                    items {{
                      id
                      updated_at
                      name
                      group {{
                        title
                        id
                      }}
                      column_values {{
                        text
                        column {{
                          title
                        }}
                        ... on DependencyValue {{
                          display_value
                        }}
                        ... on MirrorValue {{
                          display_value
                        }}
                        ... on BoardRelationValue {{
                          display_value
                        }}
                      }}
                    }}
                  }}
                }}
              }}
            }}
            '''
        
            data = {'query':query_2}
        
            r = requests.post(url=apiUrl, json=data, headers=headers)
        
            response = r.json()['data']['boards'][0]['groups'][0]['items_page']['items'][0]
        
            df1 = pd.DataFrame.from_dict(response['column_values'])
        
            # Detecto celdas Null
            
            df1 = df1[df1!=''].copy()
        
            # Relleno los valores que son Null porque vienen de otro board conectado
        
            if 'display_value' not in df1.columns:
        
                df1['display_value'] = None
        
            df1['text'] = np.where(df1['text'].isnull(),df1['display_value'],df1['text'])
        
            # Nombres de las columnas
        
            df1['column'] = df1['column'].apply(lambda x : str(x))
            df1['column'] = df1['column'].str.extract(r"'title':\s*'([^']*)'")
        
            col_names = df1['column']
        
            # Hago el transpose
            
            df1 = df1.drop(['display_value','column'],axis=1).transpose().reset_index(drop=True).copy()
        
            df1.columns = col_names
        
            df1['booking_reason'] = response['name']
            df1['id'] = response['id']
            df1['updated_at'] = response['updated_at']
            df1['updated_at'] = pd.to_datetime(df1['updated_at'], format="%Y-%m-%dT%H:%M:%SZ")
        
            duplicated_columns = df1.columns.value_counts()[df1.columns.value_counts()>1].index.to_list()
            df1 = df1.drop(duplicated_columns,axis=1)
        
            new_bookings_ps_df = pd.concat([new_bookings_ps_df,df1])
        
        bookings_ps_df = pd.concat([bookings_ps_df,new_bookings_ps_df]).copy()
        
        bookings_ps_df = bookings_ps_df[~bookings_ps_df['id'].isin(filtered_bookings_ps_items_to_delete)].copy()
        
        ################################################################################################
        
        bookings_ps_df['last_monday_updated_at'] = bookings_ps_df['id'].map(bookings_ps_items_last_update.set_index('id')['updated_at'])
        bookings_ps_df['drop_it'] = (bookings_ps_df['id'].isin(filtered_bookings_ps_items_to_update_or_read)) & (bookings_ps_df['last_monday_updated_at']!=bookings_ps_df['updated_at'])
        bookings_ps_df = bookings_ps_df[bookings_ps_df['drop_it']==False].copy().reset_index(drop=True).drop(['last_monday_updated_at','drop_it'],axis=1)
        
        ################################################################################################
        
        bookings_ps_items_last_update_stored = bookings_ps_df[['id','updated_at']].copy()
        
        storing_stored_variables_s3(bookings_ps_items_last_update_stored, OUTPUT_FILE_NAME_LAST_UPDATE )
        
        duplicated_columns_2 = bookings_ps_df.columns.value_counts()[bookings_ps_df.columns.value_counts()>1].index.to_list()
        bookings_ps_df = bookings_ps_df.drop(duplicated_columns_2,axis=1)
        
        storing_stored_variables_s3(bookings_ps_df, OUTPUT_FILE_NAME)
    
        return jsonify({
            'status': 'Monday Booking Board - ETL Completed',
            'new_records': len(new_bookings_ps_df),
            'total_records': len(bookings_ps_df)
        })
        
    except Exception as e:
        logging.exception("ETL failed")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
