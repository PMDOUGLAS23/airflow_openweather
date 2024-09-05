#!/bin/bash

# script pour télécharger Docker-Compose et initialiser Apache Airflow

# teelchargement du docker-compose pour déployer airflow
wget https://dst-de.s3.eu-west-3.amazonaws.com/airflow_fr/eval/docker-compose.yaml

# Création des répertoires
mkdir ./dags ./logs ./plugins
mkdir clean_data
mkdir raw_files

# Attribution des permissions
sudo chmod -R 777 logs/
sudo chmod -R 777 dags/
sudo chmod -R 777 plugins/

# parametrage du Airflow user
echo -e "AIRFLOW_UID=$(id -u)\nAIRFLOW_GID=0" > .env

# initialisation de la base de données
docker-compose up airflow-init

# téléchargement des données
wget https://dst-de.s3.eu-west-3.amazonaws.com/airflow_avance_fr/eval/data.csv -O clean_data/data.csv
echo '[]' >> raw_files/null_file.json

# démarrage de docker-compose
docker-compose up -d