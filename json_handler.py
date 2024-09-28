import json
from filelock import FileLock

class JsonHandler:
    filename = "mapping/mapping.json"
    lock = FileLock("file.lock", timeout=5)

    @staticmethod
    def read_json():
        with JsonHandler.lock:
            with open(JsonHandler.filename, "r") as file:
                return json.load(file)

    @staticmethod
    def write_json(data):
        with JsonHandler.lock:
            with open(JsonHandler.filename, "w") as file:
                json.dump(data, file, indent=4, sort_keys=True, default=lambda x: None if x is None else x)

