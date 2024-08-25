import json


class Config:
    token = ""
    latency = 0.05
    subjects: dict[str, int] = {}

    def __init__(self, cfg_file: str = "config.json"):
        with open(cfg_file) as f:
            cfg = json.load(f)

        self.subjects = cfg["subjects"]
        self.latency = cfg["latency"]
        self.token = cfg["token"]


config = Config("config.json")
