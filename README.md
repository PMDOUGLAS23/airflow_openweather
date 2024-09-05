# airflow_openweather
Mise en coeuvre d'un DAG qui permet de :
- récupérer des informations depuis l' API de données météo en ligne OpenWeatherData
- stocker les données collectées
- transformer les données
- Entrainer des modèles de machine learning
- et de comparer et choisir le meilleur modèle

## Organisation du projet 
< arborescence du repos>


## Mise en oeuvre
- Installation de Airflow
- Paramétrage du DAG
- Definition du DAG
    - Collecte des données
    - Transformation des données
    - Entrainement des modèles
    - Comparaison des modèles


## Installation de Airflow
Dans la ligne de commande,
se positionner dans le répertoire projet,
attribuer les permissions d'execution au script setup.sh puis exécuter le script.
```
chmod +x setup.sh
./setup.sh
```
## Description du DAG

### Schema du DAG
![DAG.jpeg]

### Composition du DAG:

#### Variables Airflow :

- cities : liste de villes pour lesquelles les données météo seront collectées (par   défaut : Paris, Londres, Washington, Yaoundé, Bamako).
- api_key : clé API pour accéder à OpenWeather.
- clean_data_path : chemin de stockage des données nettoyées.

### Tâches principales :

- fetch_weather_data (PythonOperator) : Utilise l'opérateur PythonOperator pour exécuter la fonction Python fetch_weather_data, qui collecte les données météo des villes spécifiées à l'aide de l'API OpenWeather et enregistre les résultats dans un fichier JSON horodaté. Cet opérateur permet d'intégrer du code Python directement dans le DAG.

- check_raw_files (ShortCircuitOperator) : Cette tâche utilise l'opérateur ShortCircuitOperator, qui vérifie si le dossier contenant les fichiers bruts (raw files) contient au moins 15 fichiers. Si cette condition n'est pas remplie, il court-circuite (skip) les tâches suivantes. Cela permet d'éviter de poursuivre le flux de travail si les données brutes ne sont pas suffisantes.

- transform_and_concat_last_20_files (PythonOperator) : Utilise l'opérateur PythonOperator pour exécuter la fonction transform_data_into_csv, qui transforme et concatène les 20 derniers fichiers collectés dans un fichier nommé data.csv. Cet opérateur gère l'exécution de la logique de transformation et assure la création d'un fichier consolidé.

- clean_data_sensor1 (FileSensor) : Utilise l'opérateur FileSensor pour surveiller la présence du fichier data.csv dans un répertoire. Cet opérateur attend que ce fichier soit disponible avant de permettre l'exécution de la tâche suivante. Cela garantit que les tâches dépendantes ne démarrent que lorsque le fichier requis est disponible.

- transform_and_create_fulldata (PythonOperator) : Utilise également l'opérateur PythonOperator pour exécuter la fonction transform_data_into_csv, qui cette fois concatène tous les fichiers collectés (pas seulement les 20 derniers) dans un fichier unique nommé fulldata.csv. Cette tâche est cruciale pour préparer un ensemble de données complet à partir de toutes les données disponibles.

- check_fulldata_file (ShortCircuitOperator) : Utilise un autre ShortCircuitOperator pour vérifier si le fichier fulldata.csv existe et contient plus de 15 lignes. Si cette condition n'est pas remplie, il court-circuite les tâches suivantes. Cela permet de s'assurer que l'ensemble de données est suffisamment large pour procéder à l'entraînement des modèles.

- select_best_models (groupe de tâches avec PythonOperator) : Ce groupe de tâches contient trois tâches, chacune utilisant un PythonOperator pour entraîner et sélectionner le meilleur modèle à partir des trois algorithmes suivants :

    - train_select_best_linear_regression_model : Entraîne et évalue un modèle de régression linéaire via validation croisée.
    - train_select_best_decision_tree_model : Entraîne et évalue un modèle d'arbre de décision via validation croisée.
    - train_select_best_random_forest_model : Entraîne et évalue un modèle de forêt aléatoire via validation croisée.

    Chaque tâche utilise PythonOperator pour appeler la fonction get_model_cross_val_score, qui entraîne les modèles et envoie les scores via XCom (système de partage de données entre tâches).

- select_and_train_the_best_model (PythonOperator) : Cette tâche utilise un PythonOperator pour sélectionner le modèle ayant obtenu le meilleur score (parmi les trois modèles évalués précédemment) et l'entraîner. Cette fonction s'appuie sur les données des XComs partagées par les tâches précédentes pour choisir le modèle optimal.

### Opérateurs spécifiques :

- PythonOperator : Exécute des fonctions Python définies pour chaque tâche (collecte de données, transformation, entraînement des modèles). Cet opérateur est clé dans l'intégration de la logique métier (collecte de données et traitement).

- ShortCircuitOperator : Utilisé pour interrompre le flux de travail lorsque certaines conditions ne sont pas remplies (ex. nombre minimum de fichiers ou taille des fichiers). Cela permet de contrôler les flux dépendant de l'état des fichiers.

- FileSensor : Attend la disponibilité d'un fichier avant d'autoriser l'exécution des tâches dépendantes. Cela assure que les tâches ne démarrent que lorsque les fichiers requis sont accessibles.

### Flux de dépendances

- Le DAG commence par la collecte des données via fetch_weather_data, puis vérifie le nombre de fichiers avec check_raw_files.

- En fonction des résultats, les données sont transformées et concaténées dans des fichiers consolidés avec transform_and_concat_last_20_files et transform_and_create_fulldata.

- Une fois que les fichiers nécessaires sont disponibles et valides, les modèles de machine learning sont entraînés et évalués dans le groupe de tâches select_best_models.

- Enfin, le meilleur modèle est sélectionné et entraîné dans la tâche select_and_train_the_best_model.

### Le package personnalisé utils
Pour alléger le fichier de définition du DAG, les principales fonctions utisées dans les taches du DAG sont définit dans le fochier utils.py. Ce fonctions sont décrites ci-après.

1. collect_data
    - Rôle : Cette fonction collecte les données météorologiques pour une liste de villes spécifiées à partir de l'API OpenWeatherData.
    - Entrées :
cities: Liste des villes pour lesquelles les données météorologiques seront collectées.
api_key: Clé d'API pour accéder à OpenWeatherData.
filename: Nom du fichier .json dans lequel les données seront stockées.
Fonctionnement : Pour chaque ville, la fonction envoie une requête à l'API, collecte les données et les stocke dans un fichier JSON. Si aucune donnée n'est collectée, elle lève une erreur.

2. check_file_count
    - Rôle : Cette fonction vérifie s'il y a au moins 15 fichiers dans le répertoire /app/raw_files.
    - Retour : Renvoie True si au moins 15 fichiers sont présents, sinon False.

3. transform_data_into_csv
    - Rôle : Cette fonction transforme les fichiers .json collectés en un fichier CSV.

    - Entrées :
    n_files: Nombre de fichiers à transformer (par défaut tous les fichiers).
    filename: Nom du fichier CSV dans lequel les données seront stockées (par défaut data.csv).

    - Fonctionnement : Elle lit les fichiers JSON, extrait les données importantes (température, pression, nom de la ville, date) et les transforme en un fichier CSV.

4. check_file_15_lines
    - Rôle : Vérifie si un fichier CSV contient au moins 15 lignes.

    - Entrées :
    filepath: Chemin du fichier à vérifier (par défaut /app/clean_data/fulldata.csv).
    min_lines: Nombre minimum de lignes requis (par défaut 15).

    - Retour : Renvoie True si le fichier contient au moins 15 lignes, sinon False.
    
5. compute_model_score
    - Rôle : Calcule le score d'un modèle de machine learning basé sur l'erreur quadratique moyenne négative (neg_mean_squared_error) en utilisant la validation croisée.

    - Entrées :
    model: Le modèle de machine learning à évaluer.
    X: Les caractéristiques d'entrée.
    y: La variable cible.

    - Retour : Renvoie le score moyen de la validation croisée.

6. train_and_save_model
    - Rôle : Entraîne un modèle de machine learning et le sauvegarde dans un fichier .pckl.

    Entrées :
    - model: Le modèle à entraîner.
    X, y: Les données d'entraînement (caractéristiques et cible).
    path_to_model: Chemin où le modèle sera sauvegardé.
    
7. prepare_data
    - Rôle : Prépare les données pour l'entraînement de modèles en créant des variables explicatives (features) et la variable cible (target).

    - Entrée : Chemin vers les données (CSV).

    - Fonctionnement : Trie les données par ville et date, crée des décalages temporels pour les températures précédentes comme variables, puis génère des indicateurs (dummies) pour les villes.

    - Retour : Renvoie les caractéristiques (features) et la variable cible (target).

8. model_comparison
    - Rôle : Compare plusieurs modèles de machine learning et sélectionne celui avec le meilleur score.

    - Entrée : Liste de tuples contenant le nom du modèle, le score et l'instance du modèle.

    - Fonctionnement : Entraîne le meilleur modèle sur les données et le sauvegarde sous forme de fichier .pickle.

    - Retour : Le nom du meilleur modèle et son score.
    
9. model_comparison1
    - Rôle : Compare les scores de trois modèles (LinearRegression, DecisionTreeRegressor, et RandomForestRegressor) pour sélectionner le meilleur.

    - Entrées : Scores des trois modèles.

    - Fonctionnement : Entraîne et sauvegarde le modèle avec le score le plus bas (meilleur), puis renvoie son nom et son score.
