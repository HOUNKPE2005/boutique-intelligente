"""Évaluation avant la réponse finale : règle en code + LLM juge."""
import itertools, json, re
import llm

MOTIF_FCFA = re.compile(r"(\d{1,3}(?:[ \u202f\u00a0.,]\d{3})+|\d+)\s*(?:FCFA|F CFA|CFA|XOF)", re.I)
MOTIF_TOTAL = re.compile(r"total[^0-9]{0,30}(\d{1,3}(?:[ \u202f\u00a0.,]\d{3})+|\d+)\s*(?:FCFA|F CFA|CFA|XOF)", re.I)

def _entier(s):
    return int(re.sub(r"\D", "", s))

def _collecter(obj, nombres, prix, frais, totaux):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                nombres.add(round(v))
                if k in ("prix_fcfa", "prix_unitaire_fcfa"): prix.add(round(v))
                if k == "frais_fcfa": frais.add(round(v))
                if k == "total_fcfa": totaux.add(round(v))
            else:
                _collecter(v, nombres, prix, frais, totaux)
    elif isinstance(obj, list):
        for v in obj:
            _collecter(v, nombres, prix, frais, totaux)

def _outils(trace):
    return [e for e in trace if "outil" in e and not e["outil"].startswith("demander_")]

def regle_total(reponse, trace):
    """Tout montant FCFA annoncé doit venir d'un outil ; le total = articles + livraison."""
    nombres, prix, frais, totaux = set(), set(), set(), set()
    for e in _outils(trace):
        _collecter(e["resultat"], nombres, prix, frais, totaux)
    # totaux possibles = somme d'au plus 3 produits (quantité 1 à 10) + frais
    sommes = {0}
    for k in (1, 2, 3):
        for combo in itertools.combinations(sorted(prix), k):
            for qs in itertools.product(range(1, 11), repeat=k):
                sommes.add(sum(p * q for p, q in zip(combo, qs)))
    possibles_total = set(totaux)
    for s in sommes:
        for f in (frais or {0}):
            possibles_total.add(s + f)
    autorises = nombres | sommes | possibles_total
    for m in MOTIF_TOTAL.finditer(reponse):
        v = _entier(m.group(1))
        if v not in possibles_total:
            return False, f"Le total annoncé ({v} FCFA) ne correspond pas à articles + livraison calculés avec les outils."
    for m in MOTIF_FCFA.finditer(reponse):
        v = _entier(m.group(1))
        if v not in autorises:
            return False, f"Le montant {v} FCFA ne vient d'aucun outil."
    return True, "ok"

PROMPT_JUGE = """Tu es un contrôleur qualité pour un vendeur WhatsApp. On te donne le message du client, la réponse proposée et les résultats des outils. Vérifie trois critères :
1. Aucun chiffre inventé : chaque prix, stock, frais, taux et total de la réponse apparaît dans les résultats des outils ou en découle par un calcul simple.
2. Alternative proposée : si un produit demandé est en rupture, la réponse propose une alternative réelle du catalogue.
3. Longueur : la réponse fait moins de 80 mots.
Réponds uniquement avec un JSON : {"verdict": "ok" ou "pas_encore", "critique": "phrase courte qui dit quoi corriger"}."""

def _resume_outils(trace):
    lignes = [f"{e['outil']}({json.dumps(e['args'], ensure_ascii=False)}) -> {json.dumps(e['resultat'], ensure_ascii=False)}"
              for e in _outils(trace)]
    return "\n".join(lignes)[:3500] or "(aucun outil appelé)"

def juge_llm(message_client, reponse, trace):
    contenu = (f"MESSAGE DU CLIENT :\n{message_client}\n\nRÉPONSE PROPOSÉE :\n{reponse}\n\n"
               f"RÉSULTATS DES OUTILS :\n{_resume_outils(trace)}")
    msg = llm.chat([{"role": "system", "content": PROMPT_JUGE},
                    {"role": "user", "content": contenu}])
    texte = msg.content or ""
    m = re.search(r"\{.*\}", texte, re.S)
    try:
        d = json.loads(m.group(0))
        return d.get("verdict") == "ok", d.get("critique", "")
    except Exception:
        return True, "juge illisible, ignoré"

def evaluer(message_client, reponse, trace):
    ok1, c1 = regle_total(reponse, trace)
    if not ok1:
        return False, c1, {"regle": False, "juge": None}
    ok2, c2 = juge_llm(message_client, reponse, trace)
    return ok2, c2, {"regle": True, "juge": ok2}
