"""
dashboards.py
Tableaux de bord de démonstration utilisables sur la page "Ce que ça donne" des carrousels.

Chaque entrée :
  image   : capture PNG dans assets/dashboards/
  name    : nom affiché
  about   : description courte, lue par Claude pour choisir le tableau adapté au sujet
  shots   : zones de la capture à afficher (fractions gauche, haut, droite, bas)
            et repères numérotés (fractions x, y dans la zone)
  notes   : une note par repère, dans l'ordre des repères. Chiffres vérifiés sur la capture.

Pour ajouter un tableau : déposer le PNG dans assets/dashboards/ et ajouter une entrée ici.
"""

KPI_ROW = (0.03, 0.14, 0.97, 0.29)          # rangée des indicateurs en haut de chaque page
KPI_PIN = {1: 0.155, 2: 0.345, 3: 0.535, 4: 0.73, 5: 0.92}   # coin des cartes 1 à 5
CHART_TOP_RIGHT = (0.50, 0.30, 0.97, 0.61)
CHART_TOP_LEFT = (0.03, 0.30, 0.50, 0.61)
TITLE_PIN = (0.95, 0.12)                    # repère posé dans le coin haut droit du graphique


def _kpi(*cards):
    return {"crop": KPI_ROW, "pins": [(KPI_PIN[c], 0.22) for c in cards]}


DASHBOARDS = {
    "finance_synthese": {
        "image": "finance_synthese.png",
        "name": "Pilotage financier, synthèse",
        "about": "rentabilité, EBE, résultat, compte de résultat réel contre budget, marge brute, budget",
        "shots": [_kpi(2), {"crop": CHART_TOP_RIGHT, "pins": [(0.44, 0.27), (0.95, 0.40)]}],
        "notes": ["L'EBE face au budget dès la première ligne : 351 k€ sous l'objectif.",
                  "L'écart expliqué poste par poste : ce sont les achats qui pèsent.",
                  "Le total : 351 k€ d'EBE perdus, avec la cause sous les yeux."],
    },
    "finance_creances": {
        "image": "finance_creances.png",
        "name": "Pilotage financier, créances et cash",
        "about": "trésorerie, encaissements, retards de paiement, relances clients, DSO, BFR, balance âgée",
        "shots": [_kpi(2, 4), {"crop": CHART_TOP_RIGHT, "pins": [TITLE_PIN]}],
        "notes": ["Encours échu : 961 k€, soit 503 k€ de plus qu'un an plus tôt.",
                  "Délai moyen de paiement : 61 jours, une semaine de plus qu'un an plus tôt.",
                  "Les 10 clients à relancer en premier, classés par montant en retard."],
    },
    "ventes_marges": {
        "image": "ventes_marges.png",
        "name": "Ventes et marges",
        "about": "chiffre d'affaires, marge par produit ou famille, taux de marge, prix, rentabilité commerciale",
        "shots": [_kpi(1, 3), {"crop": CHART_TOP_RIGHT, "pins": [TITLE_PIN]}],
        "notes": ["Le chiffre d'affaires progresse de 11,8 % sur un an.",
                  "Dans le même temps, le taux de marge brute perd 8 points.",
                  "La marge famille par famille : on voit où elle se dégrade."],
    },
    "ventes_clients": {
        "image": "ventes_clients.png",
        "name": "Ventes, clients et commerciaux",
        "about": "commerciaux, objectifs, remises, dépendance aux gros clients, nouveaux clients",
        "shots": [_kpi(2, 5), {"crop": CHART_TOP_LEFT, "pins": [TITLE_PIN]}],
        "notes": ["36,2 % du chiffre d'affaires repose sur 10 clients.",
                  "23 nouveaux clients sur l'année, 14,8 % de moins qu'un an plus tôt.",
                  "Chaque commercial face à son objectif, avec sa marge et ses remises."],
    },
    "crm_pipeline": {
        "image": "crm_pipeline.png",
        "name": "Prospection et suivi commercial",
        "about": "prospection, CRM, suivi des opportunités, taux de transformation, cycle de vente",
        "shots": [_kpi(3, 5), {"crop": CHART_TOP_LEFT, "pins": [TITLE_PIN]}],
        "notes": ["19,8 % des opportunités se transforment en ventes.",
                  "73 jours en moyenne entre le premier contact et la signature.",
                  "Tout le parcours, du premier contact à la vente, sur un seul graphique."],
    },
    "rh_effectifs": {
        "image": "rh_effectifs.png",
        "name": "Ressources humaines",
        "about": "effectifs, masse salariale, coût employeur, absentéisme, turnover, recrutement",
        "shots": [_kpi(3, 5), {"crop": (0.03, 0.62, 0.50, 0.95), "pins": [TITLE_PIN]}],
        "notes": ["Coût employeur : 4,28 M€, en hausse de 10 % sur un an.",
                  "Taux de rotation : 18,7 %, en hausse de 10 points.",
                  "L'absentéisme service par service."],
    },
    "production_machines": {
        "image": "production_machines.png",
        "name": "Production, performance des machines",
        "about": "production, industrie, machines, TRS, arrêts, rebuts, productivité",
        "shots": [_kpi(1, 5), {"crop": CHART_TOP_LEFT, "pins": [TITLE_PIN]}],
        "notes": ["Rendement global des machines : 78,5 %, en baisse de 1,3 point.",
                  "Taux de rebut : 1,6 %.",
                  "Machine par machine : celle qui passe sous la cible ressort en rouge."],
    },
    "stocks": {
        "image": "stocks.png",
        "name": "Stocks",
        "about": "stocks, stock dormant, rotation, couverture, achats, immobilisation de trésorerie",
        "shots": [_kpi(3, 2), {"crop": (0.03, 0.30, 0.50, 0.82), "pins": [TITLE_PIN]}],
        "notes": ["Stock dormant : 161 k€, 155 k€ de plus qu'un an plus tôt.",
                  "Couverture du stock : 30 jours.",
                  "Les produits qui dorment, classés par jours de couverture."],
    },
    "livraisons": {
        "image": "livraisons.png",
        "name": "Livraisons et transport",
        "about": "logistique, livraisons, retards, transporteurs, coût de transport, qualité de service",
        "shots": [_kpi(2, 3), {"crop": CHART_TOP_RIGHT, "pins": [TITLE_PIN]}],
        "notes": ["86,9 % des livraisons à l'heure, 2,2 points de moins qu'un an plus tôt.",
                  "Retard moyen : 2,4 jours.",
                  "Chaque transporteur comparé : celui qui décroche ressort en rouge."],
    },
}
