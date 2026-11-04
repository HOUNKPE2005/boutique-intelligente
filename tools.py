"""Les 5 outils de l'agent. Tout chiffre vient d'ici, jamais du LLM."""
import json, os, re, unicodedata
import requests

DOSSIER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DEVISES = ["EUR", "USD", "GBP", "NGN", "GHS", "CAD", "CHF"]

def _lire(nom):
    with open(os.path.join(DOSSIER, nom), encoding="utf-8") as f:
        return json.load(f)

def _ecrire(nom, data):
    with open(os.path.join(DOSSIER, nom), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _norm(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn").strip()

# ---------------- outils ----------------
def chercher_produits(mot_cle):
    mots = [m for m in re.split(r"\W+", _norm(mot_cle)) if len(m) > 2]
    mots = [m[:-1] if m.endswith("s") and len(m) > 3 else m for m in mots]
    trouves = []
    for p in _lire("catalogue.json"):
        nom = _norm(p["produit"])
        if any(m in nom or m == _norm(p["ref"]) for m in mots):
            trouves.append({"ref": p["ref"], "produit": p["produit"],
                            "prix_fcfa": p["prix_fcfa"], "stock": p["stock"]})
    if not trouves:
        return {"erreur": f"aucun produit pour {mot_cle}"}
    return {"produits": trouves}

def verifier_stock(ref):
    for p in _lire("catalogue.json"):
        if p["ref"].upper() == str(ref).upper().strip():
            return {"ref": p["ref"], "produit": p["produit"],
                    "stock": p["stock"], "disponible": p["stock"] > 0}
    return {"erreur": "référence inconnue"}

def frais_livraison(zone):
    z = _lire("zones.json")
    for nom, frais in z["zones"].items():
        if _norm(nom) == _norm(zone):
            return {"zone": nom, "frais_fcfa": frais, "delai": z["delai"]}
    return {"erreur": "zone non desservie", "zones_desservies": list(z["zones"].keys())}

def convertir_devise(montant_fcfa, devise):
    devise = str(devise).upper().strip()
    if devise not in DEVISES:
        return {"erreur": "devise non prise en charge", "devises_prises_en_charge": DEVISES}
    try:
        r = requests.get("https://open.er-api.com/v6/latest/XOF", timeout=10)
        data = r.json()
        taux = data["rates"][devise]
    except Exception:
        return {"erreur": "taux de change indisponible"}
    return {"montant_fcfa": montant_fcfa, "devise": devise, "taux": taux,
            "montant_converti": round(float(montant_fcfa) * taux, 2),
            "date_taux": data.get("time_last_update_utc", "inconnue")}

def calculer_commande(zone, articles):
    """Calcule le détail et le total EN CODE (articles + livraison)."""
    if isinstance(articles, str):
        try:
            articles = json.loads(articles)
        except Exception:
            return {"erreur": "articles invalides"}
    f = frais_livraison(zone)
    if "erreur" in f:
        return f
    cat = {p["ref"]: p for p in _lire("catalogue.json")}
    lignes, sous_total = [], 0
    for a in articles:
        ref = str(a.get("ref", "")).upper().strip()
        try:
            q = int(a.get("quantite", 1))
        except Exception:
            q = 0
        if ref not in cat:
            return {"erreur": "référence inconnue"}
        if q <= 0:
            return {"erreur": "quantité invalide"}
        p = cat[ref]
        if p["stock"] < q:
            return {"erreur": f"stock insuffisant pour {p['produit']}"}
        lignes.append({"ref": ref, "produit": p["produit"], "quantite": q,
                       "prix_unitaire_fcfa": p["prix_fcfa"], "montant_fcfa": p["prix_fcfa"] * q})
        sous_total += p["prix_fcfa"] * q
    if not lignes:
        return {"erreur": "aucun article"}
    return {"zone": f["zone"], "lignes": lignes, "sous_total_fcfa": sous_total,
            "frais_fcfa": f["frais_fcfa"], "total_fcfa": sous_total + f["frais_fcfa"],
            "delai": f["delai"]}

def creer_commande(nom_client, zone, articles):
    d = calculer_commande(zone, articles)
    if "erreur" in d:
        return d
    cat = _lire("catalogue.json")
    for l in d["lignes"]:
        for p in cat:
            if p["ref"] == l["ref"]:
                p["stock"] -= l["quantite"]
    _ecrire("catalogue.json", cat)
    c = _lire("commandes.json")
    cid = c["prochain_id"]
    c["commandes"].append({"id": cid, "nom_client": nom_client, "zone": d["zone"],
                           "articles": d["lignes"], "frais_fcfa": d["frais_fcfa"],
                           "total_fcfa": d["total_fcfa"], "statut": "enregistrée"})
    c["prochain_id"] = cid + 1
    _ecrire("commandes.json", c)
    return {"commande_id": cid, "total_fcfa": d["total_fcfa"], "statut": "enregistrée"}

FONCTIONS = {"chercher_produits": chercher_produits, "verifier_stock": verifier_stock,
             "frais_livraison": frais_livraison, "convertir_devise": convertir_devise,
             "creer_commande": creer_commande}

# ---------------- schémas (tool calling) ----------------
def _fn(nom, desc, props, req):
    return {"type": "function", "function": {"name": nom, "description": desc,
            "parameters": {"type": "object", "properties": props, "required": req}}}

TOOLS = [
    _fn("chercher_produits",
        "À utiliser dès que le client parle d'un produit ou demande un prix. Cherche par mot-clé (ex. pagne, robe, sac). Renvoie ref, produit, prix en FCFA et stock.",
        {"mot_cle": {"type": "string", "description": "Mot-clé du produit"}}, ["mot_cle"]),
    _fn("verifier_stock",
        "À utiliser avant de promettre un produit ou de créer une commande. Donne le stock d'une référence (ex. P05).",
        {"ref": {"type": "string", "description": "Référence produit, ex. P05"}}, ["ref"]),
    _fn("frais_livraison",
        "À utiliser dès que le client donne un lieu de livraison. Donne les frais en FCFA et le délai pour une zone, ou signale une zone non desservie.",
        {"zone": {"type": "string", "description": "Ville ou quartier de livraison"}}, ["zone"]),
    _fn("convertir_devise",
        "À utiliser dès que le client veut un prix dans une autre devise que le FCFA (EUR, USD, GBP, NGN, GHS, CAD, CHF). Le montant FCFA doit venir d'un outil. Utilise un taux réel du jour.",
        {"montant_fcfa": {"type": "number", "description": "Montant en FCFA"},
         "devise": {"type": "string", "description": "Code devise, ex. EUR"}}, ["montant_fcfa", "devise"]),
    _fn("creer_commande",
        "Action IRRÉVERSIBLE. À utiliser uniquement après l'accord explicite du client sur le récapitulatif et le total. La gérante doit aussi valider.",
        {"nom_client": {"type": "string"}, "zone": {"type": "string"},
         "articles": {"type": "array", "description": "Liste d'articles",
                      "items": {"type": "object", "properties": {
                          "ref": {"type": "string"}, "quantite": {"type": "integer"}},
                          "required": ["ref", "quantite"]}}},
        ["nom_client", "zone", "articles"]),
]

def schemas(*noms):
    return [t for t in TOOLS if t["function"]["name"] in noms]

if __name__ == "__main__":
    print(chercher_produits("pagnes"))
    print(chercher_produits("sac"))
    print(verifier_stock("P03"))
    print(frais_livraison("Lomé"))
    print(frais_livraison("calavi"))
    print(convertir_devise(12000, "EUR"))
    print(convertir_devise(12000, "XYZ"))
