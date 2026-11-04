"""Agent seul : boucle penser -> agir -> observer -> évaluer."""
import json, os, time
from datetime import datetime
import llm, tools, evaluation
from instructions import INSTRUCTIONS

MSG_LIMITE = "Désolé, je n'ai pas pu finir, Afi va vous répondre."
MAX_CORRECTIONS = 2

def valider_terminal(recap):
    return input(f"\n{recap}\nValider la commande ? [o/N] ")

def _court(x, n=260):
    s = json.dumps(x, ensure_ascii=False) if not isinstance(x, str) else x
    return s if len(s) <= n else s[:n] + "..."

def executer(nom, args, fonctions, valider_fn, trace_label=""):
    if nom not in fonctions:
        return {"erreur": f"outil inconnu : {nom}"}
    if nom == "creer_commande":  # validation humaine avant action irréversible
        d = tools.calculer_commande(args.get("zone", ""), args.get("articles", []))
        if "erreur" in d:
            return d
        recap = (f"RÉCAPITULATIF : {args.get('nom_client', '?')} - {d['zone']}\n" +
                 "\n".join(f"  {l['quantite']} x {l['produit']} = {l['montant_fcfa']} FCFA" for l in d["lignes"]) +
                 f"\n  Livraison : {d['frais_fcfa']} FCFA\n  TOTAL : {d['total_fcfa']} FCFA")
        if str(valider_fn(recap)).strip().lower() not in ("o", "oui"):
            return {"erreur": "commande refusée par la gérante"}
    try:
        return fonctions[nom](**args)
    except Exception as e:
        return {"erreur": f"échec de l'outil {nom} : {e}"}

def boucle(messages, schemas, fonctions, max_steps, trace, verbose, valider_fn, label=""):
    for etape in range(1, max_steps + 1):
        msg = llm.chat(messages, schemas)
        if not msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content or ""})
            return msg.content or ""
        messages.append({"role": "assistant", "content": msg.content or "",
                         "tool_calls": [{"id": tc.id, "type": "function",
                                         "function": {"name": tc.function.name,
                                                      "arguments": tc.function.arguments}}
                                        for tc in msg.tool_calls]})
        for tc in msg.tool_calls:
            nom = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}
            res = executer(nom, args, fonctions, valider_fn)
            trace.append({"etape": etape, "agent": label, "outil": nom, "args": args, "resultat": res})
            if verbose:
                print(f"[étape {etape}]{' ' + label if label else ''} OUTIL {nom} args={_court(args)}\n           résultat={_court(res)}")
            messages.append({"role": "tool", "tool_call_id": tc.id,
                             "content": json.dumps(res, ensure_ascii=False)})
    return MSG_LIMITE

def executer_avec_evaluation(message_client, messages, schemas, fonctions, max_steps,
                             verbose, valider_fn, trace, evaluer=True):
    a0, t0, d0 = llm.STATS["appels"], llm.STATS["tokens"], time.time()
    texte = boucle(messages, schemas, fonctions, max_steps, trace, verbose, valider_fn)
    verdict = None
    if evaluer and texte != MSG_LIMITE:
        for essai in range(MAX_CORRECTIONS + 1):
            ok, critique, det = evaluation.evaluer(message_client, texte, trace)
            verdict = {"ok": ok, "critique": critique, **det}
            trace.append({"evaluation": verdict, "essai": essai})
            if verbose:
                print(f"[évaluation] règle={det['regle']} juge={det['juge']} -> {'OK' if ok else 'PAS ENCORE : ' + critique}")
            if ok or essai == MAX_CORRECTIONS:
                break
            messages.append({"role": "user", "content":
                             f"Évaluation : pas encore. Critique : {critique} Corrige ta réponse en respectant les règles."})
            texte = boucle(messages, schemas, fonctions, max_steps, trace, verbose, valider_fn)
    res = {"reponse": texte, "trace": trace, "messages": messages, "evaluation": verdict,
           "nb_appels_llm": llm.STATS["appels"] - a0, "tokens": llm.STATS["tokens"] - t0,
           "duree_s": round(time.time() - d0, 2)}
    return res

def sauver_trace(res, nom=None):
    os.makedirs("traces", exist_ok=True)
    nom = nom or "trace_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".json"
    chemin = os.path.join("traces", nom)
    data = {k: v for k, v in res.items() if k != "messages"}
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return chemin

def run_agent(message_client, historique=None, max_steps=8, verbose=True, valider_fn=None, evaluer=True):
    messages = [{"role": "system", "content": INSTRUCTIONS}] + (historique or []) + \
               [{"role": "user", "content": message_client}]
    res = executer_avec_evaluation(message_client, messages, tools.TOOLS, tools.FONCTIONS,
                                   max_steps, verbose, valider_fn or valider_terminal, [], evaluer)
    res["chemin_trace"] = sauver_trace(res)
    return res

if __name__ == "__main__":
    print("Vendeur WhatsApp - tapez votre message (Ctrl+C pour quitter)")
    hist = []
    while True:
        m = input("\nClient > ")
        r = run_agent(m, hist)
        hist = r["messages"][1:]
        print(f"\nVendeur > {r['reponse']}")
