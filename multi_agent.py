"""Équipe : Gérant -> Vendeur / Logisticien / Rédacteur."""
import tools, llm
from agent import boucle, executer_avec_evaluation, sauver_trace, valider_terminal

INSTR_VENDEUR = """Tu es le Vendeur de la boutique d'Afi (Dantokpa). Tu gères catalogue, stock et commandes avec tes outils.
Réponds par un résumé factuel court : références, prix en FCFA, stocks. Signale toute rupture et propose une alternative du catalogue (cherche-la avec l'outil). N'invente rien : tout chiffre vient d'un outil.
N'utilise creer_commande que si la demande précise que le client a donné son accord explicite ; la gérante valide ensuite."""

INSTR_LOGISTICIEN = """Tu es le Logisticien de la boutique d'Afi. Tu gères livraison et devises avec tes outils.
Réponds par un résumé factuel court : frais en FCFA, délai, taux, date du taux, montant converti. N'invente rien : tout chiffre vient d'un outil. Si la zone n'est pas desservie, donne la liste des zones desservies."""

INSTR_REDACTEUR = """Tu es le Rédacteur WhatsApp de la boutique d'Afi. Tu n'as aucun outil.
À partir des faits fournis, rédige la réponse finale au client : moins de 80 mots, vouvoiement, ton chaleureux, prix en FCFA avec espaces (12 000 FCFA), au plus un emoji, termine par une question ou la prochaine étape. N'ajoute aucun chiffre qui n'est pas dans les faits."""

INSTR_GERANT = """Tu es le Gérant de la boutique d'Afi (Dantokpa). Tu décomposes la demande du client et tu délègues :
- demander_au_vendeur : produits, prix, stock, création de commande.
- demander_au_logisticien : frais et délai de livraison, conversion de devises (donne-lui le montant FCFA).
- demander_au_redacteur : à appeler EN DERNIER avec tous les faits (prix, stock, frais, total, conversion) et le message du client.
Règles : n'invente aucun chiffre ; total annoncé = articles + frais de livraison, calculé à partir des résumés ; ne demande la création d'une commande au Vendeur qu'après l'accord explicite du client (précise-le dans la demande) ; en cas de rupture, fais proposer une alternative.
Ta réponse finale doit être EXACTEMENT le texte renvoyé par le Rédacteur."""

def _delegation(label, instr, noms_outils, trace, verbose, valider_fn):
    def f(demande):
        msgs = [{"role": "system", "content": instr}, {"role": "user", "content": demande}]
        texte = boucle(msgs, tools.schemas(*noms_outils), tools.FONCTIONS, 5,
                       trace, verbose, valider_fn, label=label)
        return {"resume": texte}
    return f

def run_multi_agent(message_client, historique=None, max_steps=8, verbose=True, valider_fn=None, evaluer=True):
    valider_fn = valider_fn or valider_terminal
    trace = []
    def redacteur(faits, message_client=""):
        msgs = [{"role": "system", "content": INSTR_REDACTEUR},
                {"role": "user", "content": f"Message du client : {message_client}\nFaits : {faits}"}]
        return {"resume": boucle(msgs, None, {}, 1, trace, verbose, valider_fn, label="Rédacteur")}
    fonctions = {
        "demander_au_vendeur": _delegation("Vendeur", INSTR_VENDEUR,
            ["chercher_produits", "verifier_stock", "creer_commande"], trace, verbose, valider_fn),
        "demander_au_logisticien": _delegation("Logisticien", INSTR_LOGISTICIEN,
            ["frais_livraison", "convertir_devise"], trace, verbose, valider_fn),
        "demander_au_redacteur": redacteur,
    }
    d = {"type": "string"}
    schemas = [
        {"type": "function", "function": {"name": "demander_au_vendeur",
            "description": "Catalogue, prix, stock, création de commande (seulement après accord explicite du client).",
            "parameters": {"type": "object", "properties": {"demande": d}, "required": ["demande"]}}},
        {"type": "function", "function": {"name": "demander_au_logisticien",
            "description": "Frais et délai de livraison pour une zone, conversion de FCFA vers une devise.",
            "parameters": {"type": "object", "properties": {"demande": d}, "required": ["demande"]}}},
        {"type": "function", "function": {"name": "demander_au_redacteur",
            "description": "À appeler en dernier : met en forme la réponse WhatsApp à partir des faits.",
            "parameters": {"type": "object", "properties": {"faits": d, "message_client": d},
                           "required": ["faits", "message_client"]}}},
    ]
    messages = [{"role": "system", "content": INSTR_GERANT}] + (historique or []) + \
               [{"role": "user", "content": message_client}]
    res = executer_avec_evaluation(message_client, messages, schemas, fonctions,
                                   max_steps, verbose, valider_fn, trace, evaluer)
    res["chemin_trace"] = sauver_trace(res)
    return res

if __name__ == "__main__":
    hist = []
    while True:
        m = input("\nClient > ")
        r = run_multi_agent(m, hist)
        hist = r["messages"][1:]
        print(f"\nVendeur > {r['reponse']}")
