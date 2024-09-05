from airflow import DAG
from airflow.utils.dates import days_ago
import datetime
from airflow.operators.python import PythonOperator, ShortCircuitOperator
from airflow.utils.task_group import TaskGroup
from airflow.sensors.filesystem import FileSensor
from airflow.models import Variable

from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor

from utils import (
    collect_data,
    check_file_count, 
    transform_data_into_csv,
    check_file_15_lines,
    compute_model_score, 
    prepare_data, 
    model_comparison,
)

# Airflow variable for cities and the API Key
cities = Variable.get("cities", default_var=["paris", "london", "washington", "yaounde", "bamako"], deserialize_json=True)
api_key = Variable.get("api_key", default_var="87930e129580f796c4b773ad439e26be")

# files path 
clean_data_path = Variable.get("clean_data_path", default_var="/app/clean_data/")

# Collect data from OpenWeatherData API
def fetch_weather_data(**context):
    """ 
    Fetches weather data of the given cities and 
    saves it to a timestamped JSON file.
    """

    execution_date_utc = context['execution_date']
    filename = f"{execution_date_utc.strftime('%Y-%m-%d %H:%M')}.json"
    collect_data(cities, api_key, filename)

# Select the best model using cross validation
def get_model_cross_val_score(model, task_instance, XComs=None):
    X, y = prepare_data(f"{clean_data_path}/fulldata.csv")
    model_score = compute_model_score(model, X, y)
    task_instance.xcom_push(key=XComs, value=model_score)

# Compare models, select and train the best one
def select_and_train_the_best_model(task_instance=None):
    """Select and train the best machine learning model based on XCom scores.

    Args:
        task_instance (AirflowTaskInstance): The current task instance.

    Raises:
        ValueError: If any of the XCom scores are missing.
    """

    # Get all scores from XCom in a single call
    scores = {
        "LinearRegression": task_instance.xcom_pull(
            key="score_lr",
            task_ids=["4_select_best_models.train_select_best_linear_regression_model"]
        )[0],
        "DecisionTreeRegressor": task_instance.xcom_pull(
            key="score_dt",
            task_ids=["4_select_best_models.train_select_best_decision_tree_model"]
        )[0],
        "RandomForestRegressor": task_instance.xcom_pull(
            key="score_rf",
            task_ids=["4_select_best_models.train_select_best_random_forest_model"]
        )[0]
    }

    # Check for missing scores
    if any(score is None for score in scores.values()):
        raise ValueError("At least one model score is missing from XCom.")
    
    # Create a list of tuples (model_name, score, model_instance)
    models = [
        (model_name, score, model_class)
        for model_name, score, model_class in zip(
            scores.keys(), 
            scores.values(), 
            [LinearRegression(), DecisionTreeRegressor(), RandomForestRegressor()]
        )
    ]
    
    # Find the best model and its score
    best_model, best_score = model_comparison(models)
    
    # Push the results to XCom
    task_instance.xcom_push(key="best_score", value=best_score)
    task_instance.xcom_push(key="best_model", value=best_model)

# Default settings applied to all tasks
default_args = {
    "owner": "airflow",
    "start_date": days_ago(0),
    "trigger_rule": "all_success"
}

# Instantiate DAG
with DAG(
    dag_id="open_weather_dag_v1",
    description="Fetch weather data and train and evaluate machine learning models to predict weather",
    tags=["airflow_tp", "OpenWeather", "Datascientest"],
    schedule_interval="* * * * *",
    default_args=default_args,
    catchup=False,
) as dag:
    
    # Collect data via OpenWeatherData API
    fetch_weather_data = PythonOperator(
        task_id="1.fetch_weather_data",
        python_callable=fetch_weather_data,
        retries=2,
        retry_delay=datetime.timedelta(seconds=20),
        doc_md=""" Collection of data from targeted cities via 
        the OpenWeatherData API and storage in a timestamped file."""
    )

    # Short-circuits all the following tasks raw_files folder has less than 15 files
    check_raw_files = ShortCircuitOperator(
        task_id="1a.check_raw_files_count",
        python_callable=check_file_count,
        doc_md=""" Skip all following tasks if raw_files has less than 15 files."""
    )

    # check if fulldata csv exists and has more than 15 lines
    # other wise short-circuit all the following tasks.
    check_fulldata_file = ShortCircuitOperator(
        task_id="3a.check_fulldata_file",
        python_callable=check_file_15_lines,
        doc_md=""" Skip all following tasks if fulldata.csv doesn't exist or has less than 15 lines."""
    )

    # check if data.csv exists
    clean_data_sensor1 = FileSensor(
        task_id="2a.check_clean_data",
        filepath="data.csv",
        fs_conn_id="clean_data_fs",
        poke_interval=30,
        dag=dag,
        timeout=5*30,
    )

    # transformation et concatenation des  des 20 derniers fichiers
    transform_and_concat_last_20_files = PythonOperator(
        task_id="2.transform_last_20_files_data", 
        python_callable=transform_data_into_csv,
        doc_md=""" Transform and concatenate the 20 last collected files 
        into a single data.csv file""",
        op_kwargs={
            'n_files': 20,
            'filename': 'data.csv'
        },
        dag=dag
    )

    transform_and_create_fulldata = PythonOperator(
        task_id="3.transform_and_create_fulldata", 
        python_callable=transform_data_into_csv,
        op_kwargs={
            'n_files': None,
            'filename': 'fulldata.csv'
        },
        doc_md="""
        Transform and concatenate all collected data files 
        into a single fulldata.csv file.""",
        dag=dag
    )
    
    with TaskGroup("4_select_best_models") as select_best_models:
        train_and_select_best_lr = PythonOperator(
            task_id="train_select_best_linear_regression_model", 
            python_callable=get_model_cross_val_score,
            op_kwargs={
                "model": LinearRegression(),
                "XComs": "score_lr"
            },
            doc_md="""select the best linear regressin model with cross validation.""",
            dag=dag
        )
        train_and_select_best_dt = PythonOperator(
            task_id="train_select_best_decision_tree_model",
            python_callable=get_model_cross_val_score,
            op_kwargs={
                "model": DecisionTreeRegressor(),
                "XComs": "score_dt"
            },
            doc_md="""select the best decision tree regressor  with cross validation.""",
            dag=dag
        )
        train_and_select_best_rf = PythonOperator(
            task_id="train_select_best_random_forest_model",
            python_callable=get_model_cross_val_score,
            op_kwargs={
                "model": RandomForestRegressor(),
                "XComs": "score_rf"
            },
            doc_md="""select the best random forest regessor with cross validation.""",
            dag=dag
        )

    select_and_train_the_best_model = PythonOperator(
        task_id="5.select_and_train_the_best_model", 
        python_callable=select_and_train_the_best_model,
        dag=dag
    )

    # define task dependencies
    fetch_weather_data >> check_raw_files
    check_raw_files >> [transform_and_concat_last_20_files, transform_and_create_fulldata]
    transform_and_concat_last_20_files >> clean_data_sensor1
    transform_and_create_fulldata >> check_fulldata_file
    check_fulldata_file >> select_best_models >> select_and_train_the_best_model