"""Tests du palier 1 (3 demandes) + scénario Afi du palier 2a."""
import json, os, sys
import reset_data, tools
from agent import run_agent, sauver_trace

def noms_outils(res):
    return [e["outil"] for e in res["trace"] if "outil" in e]

def _txt(s):
    return tools._norm(s).replace("\u202f", " ").replace("\u00a0", " ")

def check1(res):
    n = noms_outils(res)
    return ("chercher_produits" in n and "convertir_devise" in n
            and n.index("chercher_produits") < n.index("convertir_devise"))

def check2(res):
    erreurs = [e for e in res["trace"] if e.get("outil") == "frais_livraison"
               and e["resultat"].get("erreur") == "zone non desservie"]
    return bool(erreurs) and "cotonou" in _txt(res["reponse"])

def check3(res):
    r = _txt(res["reponse"])
    prix = "7 500" in r or "7500" in r
    rupture = any(m in r for m in ("rupture", "epuise", "plus en stock", "indisponible", "plus disponible", "n'est plus"))
    alt = any(_txt(m) in r for m in ("pagne", "sandales", "robe", "chemise", "beurre"))
    return prix and rupture and alt

TESTS = [
    ("Vous avez des pagnes ? Combien ça fait en euros pour ma sœur à Paris ?", check1),
    ("Livrez-moi à Lomé.", check2),
    ("C'est combien le sac en raphia ?", check3),
]

if __name__ == "__main__":
    reset_data.reset()
    score, traces = 0, []
    for i, (msg, check) in enumerate(TESTS, 1):
        print(f"\n===== TEST {i} : {msg}")
        res = run_agent(msg, valider_fn=lambda r: "n")
        ok = check(res)
        score += ok
        print(f"\nRéponse : {res['reponse']}\n-> {'PASS' if ok else 'FAIL'}  (outils : {noms_outils(res)})")
        traces.append({"test": i, "message": msg, "pass": bool(ok), "reponse": res["reponse"], "trace": res["trace"]})
    with open("traces/trace_palier1.json", "w", encoding="utf-8") as f:
        json.dump(traces, f, ensure_ascii=False, indent=2)
    print(f"\n##### SCORE PALIER 1 : {score}/3")

    # --- Scénario Afi (palier 2a) : 1er refus de la gérante, puis accord ---
    print("\n===== TEST AFI (validation humaine : refus puis accord)")
    reset_data.reset()
    reponses = iter(["n", "o"])
    def valider(recap):
        r = next(reponses, "o")
        print(f"\n{recap}\nValider la commande ? [o/N] -> {r}")
        return r
    hist, etapes = [], []
    for msg in ["Je m'appelle Afi. Je veux 2 robes en wax et 1 sac en raphia, livrés à Calavi.",
                "Oui je confirme la commande sans le sac.",
                "Je confirme toujours, pouvez-vous réessayer ?"]:
        print(f"\nClient > {msg}")
        res = run_agent(msg, hist, valider_fn=valider)
        hist = res["messages"][1:]
        print(f"Vendeur > {res['reponse']}")
        etapes.append({"message": msg, "reponse": res["reponse"], "trace": res["trace"]})
    with open("traces/trace_afi.json", "w", encoding="utf-8") as f:
        json.dump(etapes, f, ensure_ascii=False, indent=2)
    cmd = json.load(open("data/commandes.json", encoding="utf-8"))["commandes"]
    robe = [p for p in json.load(open("data/catalogue.json", encoding="utf-8")) if p["ref"] == "P05"][0]
    print("\nCommandes enregistrées :", json.dumps(cmd, ensure_ascii=False))
    ok = len(cmd) == 1 and cmd[0]["total_fcfa"] == 46000 and robe["stock"] == 3
    print(f"Stock des robes : {robe['stock']} (attendu 3)")
    print(f"-> SCÉNARIO AFI : {'PASS' if ok else 'FAIL'} (attendu : 1 commande de 46 000 FCFA)")
