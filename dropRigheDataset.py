import pandas as pd

# # Percorso del file CSV di input e output
input_file_path = 'C:/Users/marta/Desktop/ProgettoBasiDiDatiII/movies.csv'
output_file_path = 'C:/Users/marta/Desktop/ProgettoBasiDiDatiII/movies_db.csv'

# Leggi solo le prime 2000 righe del file CSV
df = pd.read_csv(input_file_path, nrows=2000)

# Salva il DataFrame ridotto in un nuovo file CSV
df.to_csv(output_file_path, index=False)

print("Il dataset ridotto è stato salvato con successo.")


# Carica il dataset
df = pd.read_csv('C:/Users/marta/Desktop/ProgettoBasiDiDatiII/movies_db.csv')


# Rimuovi le colonne 'col1' e 'col2'
df = df.drop(['Tags', 'Languages','Hidden Gem Score','Runtime','Country Availability','View Rating','Metacritic Score','Awards Received','Rotten Tomatoes Score','Awards Nominated For','Boxoffice','Netflix Release Date','Production House','Netflix Link','IMDb Votes','Poster','TMDb Trailer','Trailer Site'], axis=1)

# Salva il dataset modificato
df.to_csv('C:/Users/marta/Desktop/ProgettoBasiDiDatiII/moviesDB.csv', index=False)

print("Colonne rimosse correttamente")



