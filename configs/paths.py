import os
from pathlib import Path


CONVERY_USR_DIR = os.path.join(Path.home(), ".convey")
MODELS_DIR = os.path.join(CONVERY_USR_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

DATASETS_DIR = os.path.join(CONVERY_USR_DIR, "datasets")
DATASETS_TEST_DIR = os.path.join(DATASETS_DIR, "test")
os.makedirs(DATASETS_TEST_DIR, exist_ok=True)


METADATA_PATH = os.path.join(CONVERY_USR_DIR, "metadata")
os.makedirs(METADATA_PATH, exist_ok=True)
ZIPPED_DIRE = os.path.join(CONVERY_USR_DIR, "zipped_files")
os.makedirs(ZIPPED_DIRE, exist_ok=True)


STATIC_MODULES_PATH = os.path.join(CONVERY_USR_DIR, "static_modules")
os.makedirs(STATIC_MODULES_PATH, exist_ok=True)
