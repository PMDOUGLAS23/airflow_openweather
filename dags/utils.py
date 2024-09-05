import pandas as pd
from sklearn.model_selection import cross_val_score
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor
from joblib import dump
import requests
import json
import os

# Collecte des données via l'API OpenWeatherData
def collect_data(cities: list, api_key: str, filename: str):
    """ 
    Fetches weather data from OpenWeatherData API of the given cities
    and saves it into a JSON file.
    
    input : 
        - list of cities for which data will be collected
        - api key to access to OpenWeatherData API
        - filename of the .json file where the data are stored
    """
    
    data =[]
    with open('/app/raw_files/'+filename, 'a') as f:
        print("****** check") # check
        print("****** check:", cities) # check
        print("check api_key1 ******:", api_key)
        for city in cities : 
            url=f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}"                     
            try:
                response = requests.get(url)
                response.raise_for_status()
                data.append(response.json())
                print(f"Données météo de {city} collectées.")                
            except requests.exceptions.RequestException as e:
                print(f"Erreur lors de la collecte des données de {city}: {e}")            
        if len(data) == 0 :
            raise ValueError ("Aucune donnée collectée")
        else:
            json.dump(data, f, indent=4)

# Compte le nombre de fichier dans /app/raw_files
def check_file_count():
    """Checks if the specified directory contains at least 15 files.

    Returns:
        bool: True if the condition is met, False otherwise.
    """
    directory = '/app/raw_files/'
    count = len([f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))])
    return count >= 15

# transform and concat collected .json files into csv file
def transform_data_into_csv(n_files=None, filename='data.csv'):
    parent_folder = '/app/raw_files'
    files = sorted(os.listdir(parent_folder), reverse=True)
    
    if n_files:
        files = files[:n_files]

    dfs = []

    for f in files:
        file_path = os.path.join(parent_folder, f)
        try: 
            with open(os.path.join(parent_folder, f), 'r') as file:
                data_temp = json.load(file)
            for data_city in data_temp:
                dfs.append(
                    {
                        'temperature': data_city['main']['temp'],
                        'city': data_city['name'],
                        'pression': data_city['main']['pressure'],
                        'date': f.split('.')[0]
                    }
                )
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Erreur lors du traitement de {file_path}: {e}")
            continue  # continue with the next file if an error occurs

    df = pd.DataFrame(dfs)

    print('\n', df.head(10))
    
    df.to_csv(os.path.join('/app/clean_data', filename), index=False)

# Vérifier que le fichier csv dans filepath existe et a au moin 15 lignes
# pour s'assurer que les modele qui suivront puissent tourner avec succès
def check_file_15_lines(filepath='/app/clean_data/fulldata.csv', min_lines=15):
    """
    Vérifie si le fichier existe et qu'il a au moins un certain nombre de lignes.

    Args:
        filepath (str): Chemin vers le fichier à vérifier.
        min_lines (int): Nombre minimum de lignes requis dans le fichier.

    Returns:
        bool: True si le fichier existe et contient au moins `min_lines` lignes, False sinon.
    """

    # Vérifier si le fichier existe
    if not os.path.isfile(filepath):
        print(f"Le fichier {filepath} n'existe pas.")
        return False
    
    # Compter le nombre de lignes dans le fichier
    with open(filepath, 'r') as file:
        line_count = sum(1 for line in file)
    
    if line_count < min_lines:
        print(f"Le fichier {filepath} existe mais ne contient que {line_count} lignes. Au moins {min_lines} lignes sont requises.")
        return False
    
    print(f"Le fichier {filepath} existe et contient {line_count} lignes.")
    return True


# compute model's cross validated neg_mean_squared_error
def compute_model_score(model, X, y):
    """
    compute the negative mean squared error following 
    cross_validation of the given model

    inputs:
        - model to cross validate
        - features : X
        - target: y

    output :
        - Negative Mean Squared Error
    """ 
    cross_validation = cross_val_score(
        model,
        X,
        y,
        cv=3,
        scoring='neg_mean_squared_error')

    model_score = cross_validation.mean()

    return model_score

# train and save a model into a .pckl file
def train_and_save_model(model, X, y, path_to_model='./app/model.pckl'):
    # training the model
    model.fit(X, y)
    # saving model
    print(str(model), 'saved at ', path_to_model)
    dump(model, path_to_model)

# Derive features data and target data
def prepare_data(path_to_data):
    # reading data
    df = pd.read_csv(path_to_data)
    # ordering data according to city and date
    df = df.sort_values(['city', 'date'], ascending=True)

    dfs = []

    for c in df['city'].unique():
        df_temp = df[df['city'] == c]

        # creating target
        df_temp.loc[:, 'target'] = df_temp['temperature'].shift(1)

        # creating features
        for i in range(1, 10):
            df_temp.loc[:, 'temp_m-{}'.format(i)
                        ] = df_temp['temperature'].shift(-i)

        # deleting null values
        df_temp = df_temp.dropna()

        dfs.append(df_temp)

    # concatenating datasets
    df_final = pd.concat(
        dfs,
        axis=0,
        ignore_index=False
    )

    # deleting date variable
    df_final = df_final.drop(['date'], axis=1)

    # creating dummies for city variable
    df_final = pd.get_dummies(df_final)

    features = df_final.drop(['target'], axis=1)
    target = df_final['target']

    return features, target

def model_comparison (models):
    """
    Compare les modèles et sélectionne celui avec le meilleur score.

    Args:
        models (list of tuple): Une liste de tuples, où chaque tuple contient:
            - Le nom du modèle (str)
            - Le score du modèle (float)
            - L'instance du modèle (object)

    Returns:
        tuple: Le nom du meilleur modèle (str) et son score (float).
    """
    # Préparation des données
    X, y = prepare_data('/app/clean_data/fulldata.csv')

    # Vérification du format de l'argument `models`
    for model in models:
        if not (isinstance(model, tuple) and len(model) == 3):
            raise ValueError("Chaque élément de `models` doit être un tuple de 3 éléments: (nom, score, modèle)")

    # Trouver le modèle avec le meilleur score
    best_model_name, best_score, best_model = min(models, key=lambda x: x[1])

    # Entraîner et sauvegarder le meilleur modèle
    train_and_save_model(best_model, X, y, '/app/clean_data/best_model.pickle')

    print(f"Le modèle {best_model_name} est le plus performant\navec un score neg_mean_sq_error de {best_score}.")
    return best_model_name, best_score


# compare les scores des 3 modèles
def model_comparison1(score_lr, score_dt, score_rf):

    X, y = prepare_data('/app/clean_data/fulldata.csv')

    # using neg_mean_square_error
    if score_lr < score_dt and score_lr < score_rf:
        best_score = score_lr
        best_model = "LinearRegression"
        train_and_save_model(
            LinearRegression(),
            X,
            y,
            '/app/clean_data/best_model.pickle'
        ) 

    elif score_dt < score_lr and score_dt < score_rf:
        best_score = score_dt
        best_model = "DecisionTreeRegressor"
        train_and_save_model(
            DecisionTreeRegressor(),
            X,
            y,
            '/app/clean_data/best_model.pickle'
        )
    else:
        best_score = score_rf
        best_model = "RandomForestRegressor"
        train_and_save_model(
            RandomForestRegressor(),
            X,
            y,
            '/app/clean_data/best_model.pickle'
        )
    print(f"Le modèle {best_model} est le plus performant\navec un score neg_mean_sq_error de {best_score}.")
    return best_model, best_score