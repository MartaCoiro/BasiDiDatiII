import pandas as pd
import pymongo
import json
 
import pandas as pd
from pymongo import MongoClient

# Caricare il dataset
file_path = 'C:/Users/marta/Desktop/ProgettoBasiDiDatiII/moviesDB.csv'
movies_df = pd.read_csv(file_path)

# Preparare i dati per la collezione Movies/Series
movies_data = movies_df[['Title', 'Genre', 'Series or Movie', 'IMDb Score', 'Release Date', 'IMDb Link', 'Summary', 'Image']].copy()
movies_data = movies_data.to_dict('records')

# Funzione per estrarre persone
def extract_people(row, column, role):
    people = row[column]
    if pd.isna(people):
        return []
    return [{'Name': person.strip(), 'Role': role, 'Title': row['Title']} for person in people.split(', ') if person.strip()]

# Preparare i dati per la collezione People (Directors, Writers, Actors)
people_data = []
for _, row in movies_df.iterrows():
    people_data.extend(extract_people(row, 'Director', 'Director'))
    people_data.extend(extract_people(row, 'Writer', 'Writer'))
    people_data.extend(extract_people(row, 'Actors', 'Actor'))

# Connessione a MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["moviesDB"]

# Creare collezioni
movies_collection = db["Movies_Series"]
people_collection = db["People"]

# Pulire le collezioni esistenti prima di inserire nuovi documenti
movies_collection.delete_many({})
people_collection.delete_many({})

# Inserire i documenti nelle collezioni
movies_collection.insert_many(movies_data)
people_collection.insert_many(people_data)

print("Caricamento completato!")
