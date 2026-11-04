"""Remet le stock et les commandes à l'état de départ (pour rejouer les tests)."""
import json, os
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
STOCKS = {"P01": 14, "P02": 3, "P03": 0, "P04": 8, "P05": 5, "P06": 40}

def reset():
    chemin = os.path.join(D, "catalogue.json")
    with open(chemin, encoding="utf-8") as f:
        cat = json.load(f)
    for p in cat:
        p["stock"] = STOCKS[p["ref"]]
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(cat, f, ensure_ascii=False, indent=2)
    with open(os.path.join(D, "commandes.json"), "w", encoding="utf-8") as f:
        json.dump({"prochain_id": 1, "commandes": []}, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    reset()
    print("Données remises à zéro.")
