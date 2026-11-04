# Boutique intelligente : le vendeur WhatsApp

Agent IA qui vend pour une boutique de pagnes du marché Dantokpa (Cotonou) : il répond aux clients, vérifie le stock, calcule la livraison, convertit les prix et enregistre les commandes, toujours avec l'accord de la gérante (Afi).

## Règles de la boutique
1. Aucun prix, stock ou frais inventé : tout chiffre vient d'un outil.
2. En cas de rupture, l'agent le dit et propose une alternative.
3. Total = articles + frais de livraison (calculé en code).
4. Commande enregistrée seulement après l'accord du client ET la validation d'Afi.
5. Taux de change réel, récupéré au moment de la question.

## Outils
| Outil | Rôle | Erreur renvoyée |
|---|---|---|
| chercher_produits | Trouver des produits par mot-clé | aucun produit pour X |
| verifier_stock | Stock d'une référence | référence inconnue |
| frais_livraison | Frais et délai d'une zone | zone non desservie + liste des zones |
| convertir_devise | FCFA vers EUR, USD, NGN... (API open.er-api.com) | devise non prise en charge |
| creer_commande | Enregistre la commande (irréversible) | stock insuffisant pour X |

## Garde-fous
- Limite d'étapes (`max_steps = 8`) et trace lisible de chaque appel d'outil.
- Évaluation avant la réponse : règle en code (montants et total = articles + livraison) puis LLM juge (aucun chiffre inventé, alternative si rupture, moins de 80 mots). Si « pas encore », la critique est ajoutée au contexte et l'agent recommence (2 fois maximum).
- Validation humaine avant `creer_commande` (« Valider la commande ? [o/N] ») : un refus revient à l'agent comme observation.
- Mémoire persistante : stock et commandes dans `data/*.json` ; une commande validée décrémente le stock.
- Architecture multi-agents (Gérant, Vendeur, Logisticien, Rédacteur) dans `multi_agent.py`.

## Installation et lancement (Windows, PowerShell)
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Copier `.env.example` en `.env` et renseigner la clé, l'adresse de l'API et le modèle.
```
python run_tests.py      # 3 tests du palier 1 + scénario Afi
python agent.py          # discuter avec l'agent seul
python multi_agent.py    # discuter avec l'équipe
python benchmark.py      # comparaison -> comparaison.md
python reset_data.py     # remettre stock et commandes à zéro
```

## Livrables
- Traces : `traces/trace_palier1.json`, `traces/trace_afi.json`
- Comparaison : `comparaison.md`
