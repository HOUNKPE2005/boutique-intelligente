"""Compare agent seul et multi-agents sur les 3 mêmes demandes -> comparaison.md"""
import reset_data
from agent import run_agent
from multi_agent import run_multi_agent
from run_tests import TESTS

def mesurer(fonction):
    ok, appels, tokens, durees = 0, 0, 0, []
    for msg, check in TESTS:
        reset_data.reset()
        res = fonction(msg, valider_fn=lambda r: "n", verbose=False)
        ok += bool(check(res))
        appels += res["nb_appels_llm"]; tokens += res["tokens"]; durees.append(res["duree_s"])
        print(f"  - {msg[:50]}... {'PASS' if check(res) else 'FAIL'} ({res['nb_appels_llm']} appels, {res['duree_s']} s)")
    return {"ok": ok, "appels": appels, "tokens": tokens, "duree": round(sum(durees) / len(durees), 1)}

print("Agent seul :"); a = mesurer(run_agent)
print("Multi-agents :"); m = mesurer(run_multi_agent)
verdict = "a valu" if m["ok"] > a["ok"] else "n'a pas valu"
md = f"""# Comparaison agent seul / multi-agents

| | Agent seul | Multi-agents |
|---|---|---|
| Réponses correctes (/3) | {a['ok']} | {m['ok']} |
| Nombre d'appels LLM | {a['appels']} | {m['appels']} |
| Temps de réponse moyen | {a['duree']} s | {m['duree']} s |
| Coût estimé (RODI) | {a['tokens']} tokens (à convertir en RODI avec le tarif du cours) | {m['tokens']} tokens (idem) |

## Conclusion

Ici, le multi-agents {verdict} le coup : {m['appels']} appels LLM contre {a['appels']} et {m['duree']} s contre {a['duree']} s en moyenne, pour {m['ok']}/3 réponses correctes contre {a['ok']}/3. Chaque étape ajoutée coûte du temps, de l'argent et un risque d'erreur (95 % de réussite par étape sur 10 étapes donne environ 60 % de bout en bout), donc le découpage ne se justifie que s'il améliore nettement la qualité.
"""
open("comparaison.md", "w", encoding="utf-8").write(md)
reset_data.reset()
print("\n" + md)
