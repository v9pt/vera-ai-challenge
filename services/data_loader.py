import json


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_all_data():
    return {
        "merchants": load_json("data/merchants_seed.json"),
        "customers": load_json("data/customers_seed.json"),
        "triggers": load_json("data/triggers_seed.json")
    }