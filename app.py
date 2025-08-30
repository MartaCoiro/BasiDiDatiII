from flask import Flask, render_template, request, session, redirect, url_for, flash
from pymongo import MongoClient
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string
from datetime import datetime, timedelta
from flask import jsonify
from bson.regex import Regex
import os 
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.static_folder = 'static'
app.secret_key = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(24))

# Connessione al database MongoDB
client = MongoClient('mongodb://localhost:27017/')
db = client['moviesDB']  
movies_collection = db['Movies_Series']
people_collection = db['People']
users_collection = db['Users']

# Funzione per rimuovere i messaggi flash alla fine della richiesta
@app.after_request
def remove_flash_messages(response):
    session['_flashes'] = []  # Rimuove i messaggi flash dalla sessione
    return response

#funzione per la top ten e caricamento della pagina iniziale
@app.route('/')
def index():
    # Recupera e ordina i primi 10 film/serie in base al punteggio IMDb direttamente con MongoDB
    top_10 = list(movies_collection.find().sort('IMDb Score', -1).limit(10))
    
    # Recupera tutti i film/serie (senza ordinamento)
    movies_and_series = list(movies_collection.find())
    
    return render_template('index.html', movies_and_series=movies_and_series, top_10=top_10)

#metodo per la registrazione
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        firstname = request.form['firstname']
        lastname = request.form['lastname']
        birthdate = request.form['birthdate']
        gender = request.form['gender']
        username = request.form['username']
        password = request.form['password']

        if users_collection.find_one({'username': username}):
            flash('Username already exists. Please choose a different one.', 'error')
        else:
            today = datetime.now()
            dob = datetime.strptime(birthdate, '%Y-%m-%d')
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18:
                flash('You must be at least 18 years old to register.', 'error')
            else:
                hashed_password = generate_password_hash(password)
                users_collection.insert_one({
                    'firstname': firstname,
                    'lastname': lastname,
                    'birthdate': birthdate,
                    'gender': gender,
                    'username': username,
                    'password': hashed_password,
                    'to_review': []  # Initialize the to_review list
                })

                flash('Registration successful. Please log in.', 'success')
                return redirect(url_for('login'))

    return render_template('register.html')

#metodo per la login utente e amministratore
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        """
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Admin login successful.', 'success')
            return redirect(url_for('admin_dashboard'))
        """
        user = users_collection.find_one({'username': username})

        if user and check_password_hash(user['password'], password):
            session['username'] = username
            flash('Login successful.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password. Please try again.', 'error')

        # Example authentication, adjust as per your actual implementation
        if username == 'user' and password == '0000':
            session['is_admin'] = True
            flash('Logged in successfully.', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

#metodo per la logout utente e amministratore
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('is_admin', None)  # Clear admin session
    return redirect(url_for('index'))

#metodo per mostrare i prodotti preferiti
@app.route('/favorites')
def favorites():
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user and 'favorites' in user:
            favorite_movie_ids = user['favorites']
            total_favorites = len(favorite_movie_ids)
            favorite_movies = []
            for movie_id in favorite_movie_ids:
                movie = movies_collection.find_one({'_id': ObjectId(movie_id)})
                if movie:
                    favorite_movies.append(movie)
            return render_template('favorites.html', favorite_movies=favorite_movies, total_favorites=total_favorites)
        else:
            return render_template('favorites.html', favorite_movies=[], total_favorites=0)
    else:
        return redirect(url_for('login'))

#metodo per aggiungere i preferiti (complex)
@app.route('/add_to_favorites/<movie_id>', methods=['POST'])
def add_to_favorites(movie_id):
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user:
            favorites = user.get('favorites', [])

            if movie_id in favorites:
                return jsonify({'status': 'already_in_favorites'})
            else:
                # Aggiungi il film ai preferiti
                #addToSet aggiunge l'elemento solo se non è già presente nell'array. 
                update_result = users_collection.update_one({'username': username},{'$addToSet': {'favorites': movie_id}})
            
            # Verifica se l'aggiunta è avvenuta con successo
            if update_result.modified_count > 0:

                # Aggiungi il film ai preferiti e contemporaneamente esegui un'aggregazione
                result = users_collection.aggregate([
                    {'$match': {'username': username}},
                    {'$project': {
                        'favorites': {'$ifNull': ['$favorites', []]},
                        'totalFavorites': {'$size': {'$ifNull': ['$favorites', []]}},
                    }},
                    {'$lookup': {
                        'from': 'Users',
                        'localField': 'favorites',
                        'foreignField': '_id',
                        'as': 'favoriteMovies'
                    }},
                    {'$addFields': {
                        'favoriteMoviesCount': {'$size': '$favoriteMovies'}
                    }}
                ])

                # Esempi di operazioni complesse che potrebbero essere incluse nell'aggregazione:
                # - Aggiunta di un film ai preferiti
                # - Calcolo del numero totale di preferiti
                # - Lookup per ottenere i dettagli dei film preferiti da una collezione separata

                total_favorites = 0
                for doc in result:
                    total_favorites = doc.get('totalFavorites', 0)

                # Restituisci la risposta JSON
                return jsonify({'status': 'added_to_favorites', 'totalFavorites': total_favorites})
    
            else:
                # Se l'aggiunta non è avvenuta, restituisci un messaggio di errore
                return jsonify({'status': 'failed_to_add'})
        else:
            return jsonify({'status': 'user_not_found'})
    else:
        return jsonify({'status': 'login_required'})


#metodo per rimuovere i favoriti (complex)
@app.route('/remove_from_favorites/<movie_id>', methods=['POST'])
def remove_from_favorites(movie_id):
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user:
            favorites = user.get('favorites', [])

            if movie_id in favorites:
                result = users_collection.update_one({'username': username}, {'$pull': {'favorites': movie_id}})
                
                if result.modified_count > 0: #aggiunto ora

                    result = users_collection.aggregate([
                        {'$match': {'username': username}},
                        {'$project': {
                            'favorites': {'$ifNull': ['$favorites', []]},
                            'totalFavorites': {'$size': {'$ifNull': ['$favorites', []]}},
                        }},
                        {'$lookup': {
                            'from': 'Users',
                            'localField': 'favorites',
                            'foreignField': '_id',
                            'as': 'favoriteMovies'
                        }},
                        {'$addFields': {
                            'favoriteMoviesCount': {'$size': '$favoriteMovies'}
                        }}
                    ])

                    # Esempi di operazioni complesse che potrebbero essere incluse nell'aggregazione:
                    # - Rimozione di un film dai preferiti
                    # - Calcolo del numero totale di preferiti dopo la rimozione
                    # - Lookup per ottenere i dettagli dei film preferiti da una collezione separata

                    total_favorites = 0
                    for doc in result:
                        total_favorites = doc.get('totalFavorites', 0)
                    
                    flash('Rimosso dai preferiti con successo!', 'success')
                else:
                    flash('Errore durante la rimozione dai preferiti.', 'error')
            else:
                flash('Non trovato nei preferiti.', 'warning')
        else:
            flash('Utente non trovato.', 'error')
    else:
        flash('Effettua il login per gestire i preferiti.', 'error')

    return redirect(url_for('favorites'))

#mostra solo i film
@app.route('/films')
def films():
    films = list(movies_collection.find({'Series or Movie': 'Movie'}))
    return render_template('films.html', films=films)

#mostra solo le serie
@app.route('/series')
def series():
    series = list(movies_collection.find({'Series or Movie': 'Series'}))
    return render_template('series.html', series=series)

#mostra i generi
@app.route('/generi')     
def generi():
    #Eseguire una query per ottenere tutti i generi
    generi = movies_collection.find({}, {"Genre": 1, "_id": 0})

    # Usare un set per ottenere generi distinti
    genres_set = set()
    for genere in generi:
        genres = genere.get('Genre', [])
        if isinstance(genres, str):
            genres = genres.split(', ')
        elif not isinstance(genres, list):
            continue  # Se genres non è né stringa né lista, passa al prossimo documento
        for Genre in genres:
            if isinstance(Genre, str):
                cleaned_genre = Genre.strip()
                genres_set.add(cleaned_genre)

    # Convertire il set in una lista
    generi = sorted(list(genres_set))
    return render_template('generi.html', generi=generi)

#filtra i film e serie per genere (complex)
@app.route('/genre/<genre_name>/<type>')
def show_genre(genre_name, type):
    # Query per trovare tutti i media con il genere specificato
    if type.lower() == "film":
        # Utilizza $regex per cercare il genere desiderato all'interno della lista separata da virgola
        regex_pattern = f"\\b{genre_name}\\b"  # \\b per fare il match esatto del termine
        lista = list(movies_collection.find({
            '$and': [
                {'Series or Movie': 'Movie'},
                {'Genre': {'$regex': Regex(regex_pattern, 'i')}}  # 'i' per ignorare la case-sensitivity
            ]
        }))
    else:
        # Utilizza $regex per cercare il genere desiderato all'interno della lista separata da virgola
        regex_pattern = f"\\b{genre_name}\\b"  # \\b per fare il match esatto del termine
        lista = list(movies_collection.find({
            '$and': [
                {'Series or Movie': 'Series'},
                {'Genre': {'$regex': Regex(regex_pattern, 'i')}}  # 'i' per ignorare la case-sensitivity
            ]
        }))
    return render_template('listaGenere.html', genre=genre_name, lista=lista, type=type)

#mostra i dettagli di uno specifico prodotto(complex)
@app.route('/movie/<movie_id>')
def movie_details(movie_id):

    # Converti movie_id in ObjectId
    try:
        movie_id = ObjectId(movie_id)
    except:
        return jsonify({'status': 'error', 'message': 'Invalid movie ID format'})

    movie = movies_collection.find_one({'_id': ObjectId(movie_id)})

    if movie is None:
        return jsonify({'status': 'error'})
        
    pipeline = [
        {
            "$match": {
                "_id": movie_id
            }
        },
        {
            "$lookup": {
                "from": "People",
                "let": { "title": "$Title" },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": { "$eq": ["$Title", "$$title"] }
                        }
                    },
                    {
                        "$group": {
                            "_id": "$Role",
                            "people": { "$push": "$Name" }
                        }
                    }
                ],
                "as": "people_involved"
            }
        },
        {
            "$project": {
                "_id": 1,
                "Title": 1,
                "Genre": 1,
                "Series or Movie":1,
                "IMDb Score": 1,
                "Release Date": 1,
                "IMDb Link":1,
                "Summary": 1,
                "Image": 1,
                "People Involved": "$people_involved"
            }
        }
    ]

    # Esegui l'aggregazione
    media_details = list(movies_collection.aggregate(pipeline))

    if not media_details:
        return jsonify({'status': 'error'})

    return render_template('movie_details.html', movie=media_details[0])


#richiesta eliminazione account
@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('profile.html')

#eliminazione account
@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if 'username' in session:
        username = session['username']
        users_collection.delete_one({'username': username})
        session.pop('username', None)
        flash('Your profile has been successfully deleted.', 'success')
    return redirect(url_for('index'))

#visualizzazione dei media iniziati a vedere
@app.route('/to-review')
def to_review():
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user and 'to_review' in user:
            to_review_movie_ids = user['to_review']
            to_review_movies = []
            for movie_id in to_review_movie_ids:
                movie = movies_collection.find_one({'_id': ObjectId(movie_id)})
                if movie:
                    to_review_movies.append(movie)
            return render_template('to_review.html', review_movies=to_review_movies)
        else:
            return render_template('to_review.html', review_movies=[])
    else:
        return redirect(url_for('login'))

#aggiunta di un media che abbiamo iniziato a vedere
@app.route('/add_to_review/<movie_id>', methods=['POST'])
def add_to_review(movie_id):
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user:
            to_review = user.get('to_review', [])

            if movie_id not in to_review:
                to_review.append(movie_id)
                users_collection.update_one({'username': username}, {'$set': {'to_review': to_review}})
                return jsonify({'status': 'added_to_review'})
            else:
                return jsonify({'status': 'already_in_to_review'})
        else:
            return jsonify({'status': 'user_not_found'})
    else:
        return jsonify({'status': 'login_required'})

#rimozione di un media che abbiamo iniziato a vedere
@app.route('/remove_from_review/<movie_id>', methods=['POST'])
def remove_from_review(movie_id):
    if 'username' in session:
        username = session['username']
        user = users_collection.find_one({'username': username})

        if user:
            to_review = user.get('to_review', [])

            if movie_id in to_review:
                to_review.remove(movie_id)
                users_collection.update_one({'username': username}, {'$set': {'to_review': to_review}})
                return jsonify({'status': 'removed_from_review'})
            else:
                return jsonify({'status': 'not_in_review_list'})
        else:
            return jsonify({'status': 'user_not_found'})
    else:
        return jsonify({'status': 'login_required'})
    

#metodo per la ricerca (complex)
@app.route('/search/<tipo>', methods=['GET'])
def search(tipo):
    query = request.args.get('query', '').strip()

    if query:
        # Costruzione dei criteri di ricerca con espressione regolare
        #i'rende la ricerca case-insensitive,non distingue tra lettere maiuscole e minuscole. 
        search_criteria = {
            '$or': [
                {'Title': {'$regex': query, '$options': 'i'}},
                {'Release Date': {'$regex': query, '$options': 'i'}}
            ]
        }
        
        # Esecuzione della query nel database
        movie_search_results = list(movies_collection.find(search_criteria))
        
        # Costruzione dei criteri di ricerca per attori e registi
        people_search_criteria = {
            'Name': {'$regex': query, '$options': 'i'}
        }
        
        # Esecuzione della query per attori e registi nel database
        people_search_results = list(people_collection.find(people_search_criteria))
        
        # Trovare film in cui è presente l'attore o regista
        movies_with_people = []
        for person in people_search_results:
            person_movies_criteria = {
                'Title': person['Title']
            }
        
            person_movies = list(movies_collection.find(person_movies_criteria))
            movies_with_people.extend(person_movies)

        # Rimuovere duplicati mantenendo l'ordine di ricerca
        final_movies_results = []
        seen_titles = set()
        for movie in movie_search_results:
            if movie['Title'] not in seen_titles:
                final_movies_results.append(movie)
                seen_titles.add(movie['Title'])
        for movie in movies_with_people:
            if movie['Title'] not in seen_titles:
                final_movies_results.append(movie)
                seen_titles.add(movie['Title'])

        return render_template('index.html', movies_and_series=final_movies_results, tipo=tipo)
    else:
        flash('Please enter a search term.', 'error')
        return redirect(url_for('index'))





#ADMIN 

# Admin credentials
ADMIN_USERNAME = "user"
ADMIN_PASSWORD = "0000"

#funzione che carica la pagina iniziale
@app.route('/admin')
def admin_dashboard():
    if 'is_admin' in session:
        products = list(movies_collection.find())
        return render_template('admin_dashboard.html', products=products)
    else:
        flash('Admin access only.', 'error')
        return redirect(url_for('login'))

#recupera tutti i generi dal db
def get_generi():
    # Eseguire una query per ottenere tutti i generi
    generi = movies_collection.find({}, {"Genre": 1, "_id": 0})

    # Usare un set per ottenere generi distinti
    genres_set = set()
    for genere in generi:
        genres = genere.get('Genre', [])
        if isinstance(genres, str):
            genres = genres.split(', ')
        elif not isinstance(genres, list):
            continue  # Se genres non è né stringa né lista, passa al prossimo documento
        for Genre in genres:
            if isinstance(Genre, str):
                cleaned_genre = Genre.strip()
                genres_set.add(cleaned_genre)

    # Convertire il set in una lista ordinata
    generi = sorted(list(genres_set))
    return generi

# funzione che permette di aggiungere un nuovo prodotto
@app.route('/admin/add', methods=['GET', 'POST'])
def add_product():
    
    generi = get_generi()  # Ottieni la lista dei generi

    if 'is_admin' in session:
        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            genres = request.form.getlist('genre[]')
            release_date = request.form.get('release_date', '').strip()
            series_or_movie = request.form.get('series_or_movie', '').strip()
            imdb_score = request.form.get('imdb_score', '').strip()
            imdb_link = request.form.get('imdb_link', '').strip()
            summary = request.form.get('summary', '').strip()
            image = request.form.get('image', '').strip()

            # Validate fields
            if not all([title, genres, release_date, series_or_movie, imdb_score, imdb_link, summary, image]):
                flash('All fields are required for Movies/Series.', 'error')
                return redirect(url_for('add_product'))

            try:
                imdb_score = float(imdb_score)
                if imdb_score < 0 or imdb_score > 10:
                    flash('IMDb Score must be between 0 and 10.', 'error')
                    return redirect(url_for('add_product'))
            except ValueError:
                flash('IMDb Score must be a valid number.', 'error')
                return redirect(url_for('add_product'))

            # Salva i dati del film/serie nella collezione appropriata
            product = {
                'Title': title,
                 'Genre': ', '.join(genres),
                'Release Date': release_date,
                'Series or Movie': series_or_movie,
                'IMDb Score': imdb_score,
                'IMDb Link': imdb_link,
                'Summary': summary,
                'Image': image,
            }
            
            movies_collection.insert_one(product)

            # Campi dei ruoli
            role_names = request.form.getlist('role_name[]')
            person_names = request.form.getlist('person_name[]')
            
            # Salva i dati del regista/attore nella collezione appropriata
            for role, name in zip(role_names, person_names):
                if role.strip() and name.strip():
                    person = {
                        'Name': name.strip(),
                        'Role': role.strip(),
                        'Title': title  # Usare il titolo del film/serie associato
                    }
                    people_collection.insert_one(person)

            flash('Film/Serie e Persona aggiunti con successo.', 'success')
            return redirect(url_for('admin_dashboard'))

        return render_template('add_product.html', generi = generi)

    else:
        flash('Admin access only.', 'error')
        return redirect(url_for('login'))

#funzione che permette di rimuovere un prodotto
@app.route('/admin/delete/<product_id>', methods=['POST'])
def delete_product(product_id):
    if 'is_admin' in session:

        # Converti product_id in ObjectId
        product_id = ObjectId(product_id)

        # Trova il prodotto nella collezione movies_series
        product = movies_collection.find_one({'_id': product_id})

        if product:
            # Rimuovi il prodotto dalla collezione movies_series
            movies_collection.delete_one({'_id': product_id})

            # Rimuovi i relativi attori e registi dalla collezione people
            people_collection.delete_many({'Title': product['Title']})

            flash('Product deleted successfully.', 'success')
        else:
            flash('Product not found.', 'error')

        return redirect(url_for('admin_dashboard'))
    else:
        flash('Admin access only.', 'error')
        return redirect(url_for('login'))
    
#funzione di ricerca
@app.route('/admin/search', methods=['GET'])
def admin_search():
    if 'is_admin' in session:
        query = request.args.get('query', '').strip()
 
        if query:
            # Costruzione dei criteri di ricerca con espressione regolare
            #i'rende la ricerca case-insensitive,non distingue tra lettere maiuscole e minuscole.
            search_criteria = {
                '$or': [
                    {'Title': {'$regex': query, '$options': 'i'}},
                    {'Release Date': {'$regex': query, '$options': 'i'}}
                ]
            }
        
            # Esecuzione della query nel database
            movie_search_results = list(movies_collection.find(search_criteria))
        
            # Costruzione dei criteri di ricerca per attori e registi
            people_search_criteria = {
                'Name': {'$regex': query, '$options': 'i'}
            }
        
            # Esecuzione della query per attori e registi nel database
            people_search_results = list(people_collection.find(people_search_criteria))
        
            # Trovare film in cui è presente l'attore o regista
            movies_with_people = []
            for person in people_search_results:
                person_movies_criteria = {
                    'Title': person['Title']
                }
        
                person_movies = list(movies_collection.find(person_movies_criteria))
                movies_with_people.extend(person_movies)
    
            # Rimuovere duplicati mantenendo l'ordine di ricerca
            final_movies_results = []
            seen_titles = set()
            for movie in movie_search_results:
                if movie['Title'] not in seen_titles:
                    final_movies_results.append(movie)
                    seen_titles.add(movie['Title'])
            for movie in movies_with_people:
                if movie['Title'] not in seen_titles:
                    final_movies_results.append(movie)
                    seen_titles.add(movie['Title'])
    
            return render_template('admin_dashboard.html', search_results=final_movies_results)
        else:
            flash('Please enter a search term.', 'error')
            return redirect(url_for('admin_dashboard'))
    else:
        flash('Admin access only.', 'error')
        return redirect(url_for('login'))
    
#funzione che permette di modificare i dati dei prodotti
@app.route('/edit_product/<product_id>', methods=['GET', 'POST'])
def edit_product(product_id):

    generi = get_generi()  # Ottieni la lista dei generi

    # Converti movie_id in ObjectId
    print(f'Request method: {request.method}')

    try:
        product_id = ObjectId(product_id)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})
    
    movie = movies_collection.find_one({'_id': product_id})

    if movie is None:
        return jsonify({'status': 'error'})

    # Pipeline per aggregazione
    pipeline = [
        {
            "$match": {
                "_id": product_id
            }
        },
        {
            "$lookup": {
                "from": "People",  # Assicurati che il nome della collezione sia corretto
                "let": { "title": "$Title" },
                "pipeline": [
                    {
                        "$match": {
                            "$expr": { "$eq": ["$Title", "$$title"] }
                        }
                    },
                    {
                      "$project": {
                            "Name": 1,
                            "Role": 1,
                            "_id": 1
                        }
                    }
                ],
                "as": "people_involved"
            }
        },
        {
            "$project": {
                "_id": 1,
                "Title": 1,
                "Genre": 1,
                "Series or Movie": 1,
                "IMDb Score": 1,
                "Release Date": 1,
                "IMDb Link": 1,
                "Summary": 1,
                "Image": 1,
                "People Involved": "$people_involved"
            }
        }
    ]

    # Esegui l'aggregazione
    media_details = list(movies_collection.aggregate(pipeline))

    if not media_details:
        return jsonify({'status': 'error', 'message': 'Details not found'})

    if request.method == 'POST':
        # Recupera e valida i dati dal form di modifica
        title = request.form.get('title', '').strip()
        genres = request.form.getlist('genre')  # getlist() is used to get multiple values
        genre = ', '.join(genres)  # Unisci i generi in una singola stringa separata da virgole
        release_date = request.form.get('release_date', '').strip()
        series_or_movie = request.form.get('series_or_movie', '').strip()
        imdb_score = request.form.get('imdb_score', '').strip()
        imdb_link = request.form.get('imdb_link', '').strip()
        summary = request.form.get('summary', '').strip()
        image = request.form.get('image', '').strip()
      
        roles = request.form.getlist('roles')  # List of roles
        names = request.form.getlist('names')  # List of names
        person_ids = request.form.getlist('person_ids')  # Nuovo campo per ID delle persone

        # Validazione dei campi
        if not all([title, genres, release_date, series_or_movie, imdb_score, imdb_link, summary, image]):
            flash('All fields are required.', 'error')
            return redirect(url_for('edit_product', product_id=product_id, generi=generi))

        try:
            imdb_score = float(imdb_score)
            if imdb_score < 0 or imdb_score > 10:
                flash('IMDb Score must be between 0 and 10.', 'error')
                return redirect(url_for('edit_product', product_id=product_id, generi=generi))
        except ValueError:
            flash('IMDb Score must be a valid number.', 'error')
            return redirect(url_for('edit_product', product_id=product_id, generi=generi))

        # Aggiornamento del prodotto
        updated_product = {
            'Title': title,
            'Genre': genre,
            'Release Date': release_date,
            'Series or Movie': series_or_movie,
            'IMDb Score': imdb_score,
            'IMDb Link': imdb_link,
            'Summary': summary,
            'Image': image,
        }
        
        movies_collection.update_one({'_id': product_id}, {'$set': updated_product})

        # Aggiorna il titolo delle persone
        old_title = movie['Title']
        if old_title != title:
            people_collection.update_many(
                {'Title': old_title},
                {'$set': {'Title': title}}
            )

        # Aggiorna le persone
        for person_id, role, name in zip(person_ids, roles, names):
            try:
                person_id = ObjectId(person_id) # Assicurati che person_id sia un ObjectId valido
                print(f'Updating person with Role: {role}, Name: {name}')
                result = people_collection.update_one(
                    {'_id': person_id },
                    {'$set': {'Role': role,'Name': name}}
                )
            except Exception as e:
                flash(f'Error updating person with ID: {person_id}. Error: {str(e)}', 'error')
                return redirect(url_for('edit_product', product_id=product_id, generi=generi))
            
        flash('Movie/Series updated successfully.', 'success')

        return redirect(url_for('edit_product', product_id=product_id, generi=generi))

    return render_template('edit_product.html', movie=media_details[0], generi=generi)

if __name__ == '__main__':
    app.run(debug=True)
