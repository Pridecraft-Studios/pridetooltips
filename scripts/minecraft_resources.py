import logging
import os
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from timing import time_this

BUILD_PROCESS_DIR = "../build/process"

@time_this
def prepare_minecraft_resources(mc_versions: list) -> bool:
    if not download_minecraft_client_jars(mc_versions):
        return False
    unzip_minecraft_client_jars(mc_versions)
    clean_process_version_directories(mc_versions)
    return True

@time_this
def download_minecraft_client_jars(mc_versions: list) -> bool:
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(download_minecraft_client_jar, mc_version) for mc_version in mc_versions]
        for future in as_completed(futures):
            if not future.result():
                return False
    return True

def download_minecraft_client_jar(mc_version: str) -> bool:
    manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
    manifest_response = requests.get(manifest_url)
    if manifest_response.status_code != 200:
        logging.error(f"Failed to fetch manifest for {mc_version}")
        return False

    version_field = next((v for v in manifest_response.json()["versions"] if v["id"] == mc_version), None)
    if not version_field:
        logging.error(f"Version {mc_version} not found in manifest")
        return False

    version_url = version_field["url"]
    version_response = requests.get(version_url)
    if version_response.status_code != 200:
        logging.error(f"Failed to fetch version details for {mc_version}")
        return False

    client_url = version_response.json()["downloads"]["client"]["url"]
    download_path = os.path.join(BUILD_PROCESS_DIR, mc_version, "mc_client.jar")
    os.makedirs(os.path.dirname(download_path), exist_ok=True)
    client_response = requests.get(client_url)
    if client_response.status_code != 200:
        logging.error(f"Failed to download client jar for {mc_version}")
        return False

    with open(download_path, 'wb') as file:
        file.write(client_response.content)
    logging.info(f"Downloaded {download_path}")
    return True

@time_this
def unzip_minecraft_client_jars(mc_versions: list):
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(unzip_single_jar, mc_version) for mc_version in mc_versions]
        for future in as_completed(futures):
            future.result()

def unzip_single_jar(mc_version: str):
        version_dir = os.path.join(BUILD_PROCESS_DIR, mc_version)
        jar_path = os.path.join(version_dir, "mc_client.jar")
        if os.path.exists(jar_path):
            with zipfile.ZipFile(jar_path, 'r') as zip_ref:
                zip_ref.extractall(version_dir)
            logging.info(f"Unzipped {jar_path}")

@time_this
def clean_process_version_directories(mc_versions: list):
    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(clean_single_version_directory, mc_version) for mc_version in mc_versions]
        for future in as_completed(futures):
            future.result()

def clean_single_version_directory(mc_version: str):
        version_dir = os.path.join(BUILD_PROCESS_DIR, mc_version)
        for root, dirs, files in os.walk(version_dir):
            for name in files:
                if not (name.startswith("assets" + os.sep) and name.startswith("data" + os.sep)):
                    file_path = os.path.join(root, name)
                    os.remove(file_path)
            for name in dirs:
                if not (name == "assets" or name == "data"):
                    dir_path = os.path.join(root, name)
                    shutil.rmtree(dir_path)
        logging.info(f"Cleaned {version_dir}")
