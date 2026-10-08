"""Catalog facts shared by the checks: independent labels + what the app serves."""
import csv
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Catalog:
    def __init__(self, labels_path=None, app_data_path=None):
        labels_path = labels_path or os.path.join(ROOT, "eval", "datasets", "catalog_labels.csv")
        app_data_path = app_data_path or os.path.join(ROOT, "app", "app_data.json")
        with open(labels_path, encoding="utf-8") as f:
            self.labels = {r["product_id"]: r for r in csv.DictReader(f)}
        with open(app_data_path, encoding="utf-8") as f:
            self.app = {str(p["product_id"]): p for p in json.load(f)}

    def is_skincare(self, pid):
        return self.labels.get(pid, {}).get("is_skincare") == "1"

    def label_concerns(self, pid):
        return {c for c in self.labels[pid]["concerns"].split(";") if c}

    def system_concerns(self, pid):
        return set(self.app[pid].get("concerns", []))

    def brands(self):
        return {(p.get("brand") or "").strip() for p in self.app.values()} - {""}

    def ingredient_vocabulary(self):
        """Every ingredient name the catalog lists (lower-cased), minus water synonyms."""
        vocab = set()
        for p in self.app.values():
            for ing in p.get("ingredients", []):
                name = ing.strip().lower()
                if name and not name.startswith(("aqua", "water", "eau", "di water", "purified water")):
                    vocab.add(name)
        return vocab
