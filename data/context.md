# Datathon 2026 – AlphaForge AI (Polyfinances × Banque Nationale × AWS)

> Contexte de référence pour un agent IA assistant une équipe. Source : « Énoncé du défi » officiel (PDF, 19 p.). Les dates limites, plateformes de dépôt, formats et exigences d'infrastructure seront précisés dans des **consignes logistiques officielles** (non incluses ici).

## 1. Mission en une phrase

Concevoir une **solution agentique auto-explicative** (self-explaining) qui exploite des **données financières publiques** pour éclairer la décision d'investissement selon différents **profils d'investisseurs**, et qui **explique ses sources, hypothèses et limites**.

- Tout est **simulation** : aucune transaction réelle, aucun conseil financier personnalisé.
- Ce n'est **pas** un concours de rendement : on évalue une démarche **crédible, innovante et utile**.
- **Libres** : cas d'usage, actifs, architecture, nombre d'agents, modèles, outils, forme du résultat (portefeuille simulé / allocation fictive, analyse comparative, aide à la décision, autre résultat défendable).

## 2. Esprit et priorités du jury

- Valorisé : **pertinence de la démarche agentique** + **capacité à expliquer ses propres résultats** (données, hypothèses, limites).
- Une démo convaincante et des explications **fidèles aux données et aux actions observables** comptent plus que la complexité technique ou la performance passée des actifs.
- Conseil officiel : approche agentique **simple, focalisée, vérifiable**. Sophistication technique et nombre d'agents ne sont pas des fins en soi.
- Conseil : comparer **deux situations d'investisseurs contrastées** pour illustrer l'adaptabilité, sans imposer une sortie uniforme.

## 3. Les 3 personas (profils fictifs de référence)

Les équipes doivent expliquer comment leur approche tient compte de chaque contexte et de ses limites (pas obligé de tous les traiter, mais ils servent à concevoir/tester).

### Persona 01 – AMIRA (26 ans, ingénieure logicielle)
- **Risque : élevé** | **Horizon : 15 ans ou +** | Célibataire, sans enfant | Expérience : intermédiaire
- **Objectif** : faire croître son capital à long terme.
- **Préférences/contraintes** : très intéressée par l'IA et technologies émergentes ; ouverte aux entreprises en forte croissance et à une forte volatilité ; intéressée par les cryptoactifs ; veut une certaine **diversification** et éviter de miser exclusivement sur la tech.
- **Ce que le persona teste** : jusqu'où le système accepte le risque. Ne pas interpréter « risque élevé » comme « tout est acceptable ». Garder une diversification cohérente avec ses préférences.

### Persona 02 – MATEO (41 ans, gestionnaire des opérations)
- **Risque : modéré** | **Horizon : 8 à 12 ans** | En couple, 2 enfants | Expérience : intermédiaire
- **Objectif** : croissance du capital **équilibrée** à moyen/long terme.
- **Préférences/contraintes** : grande importance aux **facteurs ESG** ; éviter les entreprises liées à d'importantes controverses environnementales ou sociales ; équilibre croissance/stabilité ; ouvert aux technos émergentes si compatibles avec son profil de risque ; peu intéressé par le hautement spéculatif.
- **Ce que le persona teste** : intégrer autre chose que rendement et risque — critères financiers **et** préférences personnelles (ESG).

### Persona 03 – ROBERT (59 ans, professionnel de la santé)
- **Risque : faible à modéré** | **Horizon : 3 à 5 ans** | Marié, enfants adultes, retraite dans les prochaines années | Expérience : avancée
- **Objectif** : **préserver le capital** tout en gardant un potentiel de croissance.
- **Préférences/contraintes** : entreprises établies, modèle d'affaires compréhensible ; stabilité et qualité ; peu intéressé par les cryptos ; suit activement les marchés ; **peut être tenté par une entreprise très médiatisée, même plus risquée** que son profil.
- **Ce que le persona teste** : **remettre en question une demande incohérente** avec le profil — relever la tension, expliquer les risques, **ne pas acquiescer automatiquement**.

## 4. Démarche suggérée (guide, sans ordre imposé)

1. **Formuler une question utile** : besoin financier ou décision à éclairer.
2. **Concevoir la démarche agentique** : rôle du/des agents, données et outils mobilisés, coordination, **points de contrôle**.
3. **Tenir compte du contexte** : personas, et au besoin autres objectifs/préférences/contraintes explicites.
4. **Mettre les résultats à l'épreuve** : sensibilité à hypothèses, données ou scénarios différents.
5. **Rendre la solution auto-explicative** : relier résultats ↔ sources, hypothèses, étapes observables, limites. L'utilisateur doit pouvoir **comprendre et vérifier** ce qui soutient une conclusion.

### Pistes (optionnelles)
- **Agent d'explicabilité** : synthétise ce qui soutient le résultat, cite les données utilisées, explicite les hypothèses, signale les incertitudes. Peut être intégré à un autre agent/mécanisme. La **capacité** d'explication est recherchée, pas le composant.
- **Agent de gouvernance** : vérifie que actions/résultats respectent les contraintes de l'investisseur et les limites du défi (simulation), signale conflits et informations manquantes, rend les contrôles **visibles**. Peut être un autre agent/mécanisme.

## 5. Données

### Principes
- Jeu de départ **facultatif** : on peut le compléter ou le remplacer par d'autres données publiques.
- **Aucun actif ni classe d'actifs obligatoire** (un seul instrument, sous-ensemble propre, ou actifs différents OK si pertinence et sources expliquées).
- Dérivés / marge non exigés ; **aucune transaction réelle**.
- Pour chaque source : documenter **pertinence, origine, date, traitements, limites, conditions d'accès et de réutilisation**.

### Jeu de départ (fichiers fournis)
| Fichier | Contenu |
|---|---|
| `assets_universe.csv` | 31 actifs : 10 actions canadiennes, 10 actions américaines, 9 FNB (actions, obligations, or, 1 FNB filtré ESG), Bitcoin, Ether. Champs : identifiant, symbole, nom, classe d'actifs, marché, devise, secteur |
| `prices_daily.csv` | ~40 000 lignes de prix quotidiens : date, symbole, open, high, low, close, **close ajustée** (dividendes + fractionnements), volume, devise de cotation |
| `corporate_actions.csv` | Dividendes et fractionnements par date ex |
| `fx_usdcad_daily.csv` | Taux USD/CAD quotidien (Banque du Canada) |
| `macro_rates.csv` | 9 séries macro : taux directeurs, rendements 2 et 10 ans, IPC (Canada & É.-U.), chômage US (Banque du Canada, FRED) |
| `sources_metadata.csv`, `build_dataset.py`, `README.md` | Source, date, traitement, limites, conditions par fichier ; script qui régénère les données |

- **Période** : 5 ans, du **12 nov. 2021 au 12 nov. 2026** (inclut 2022 : actions et obligations en baisse simultanée).
- **Absent du jeu de départ** : cotes ESG, nouvelles, données fondamentales → à ajouter et documenter par l'équipe si nécessaire (ex. Mateo/ESG).

### Exemples indicatifs d'instruments (non obligatoires)
- **Actions CA** : RY.TO, TD.TO, BMO.TO, CNR.TO, CP.TO, ENB.TO, CNQ.TO, FTS.TO, SHOP.TO, CSU.TO, ATD.TO, MFC.TO
- **Actions US** : AAPL, MSFT, NVDA, GOOGL, AMZN, META, JPM, JNJ, XOM, PG, COST, TSLA
- **FNB actions** : SPY, QQQ, VTI, XLF, XLK, XLV, XIU.TO, XIC.TO, ZSP.TO
- **FNB obligataires** : AGG, BND, IEF, TLT, XBB.TO, ZAG.TO
- **FNB or** : GLD, IAU
- **Crypto** : BTC-USD, ETH-USD

### Familles de données exploitables
Prix/transactions · opérations sur titres · données des sociétés (revenus, bénéfices, dette, ratios) · FNB (holdings, pondérations, frais, AUM) · obligations et taux · macro (inflation, taux directeurs, chômage, croissance + dates de publication) · devises · nouvelles et textes (communiqués, résultats trimestriels, documents réglementaires) · durabilité/ESG et secteurs · cryptoactifs · profils et scénarios fictifs.

### Sources publiques suggérées
Publications/relations investisseurs des sociétés · **SEC EDGAR**, **SEDAR+** · **Banque du Canada**, **FRED**, **Statistique Canada** · sites d'émetteurs de FNB (fiches, holdings) · fournisseurs de cours librement consultables (respecter licences et limites d'API).

### Règles de qualité et d'utilisation
- **Traçabilité** : source, date, devise, traitements.
- **Cohérence temporelle** : distinguer date d'observation vs date de publication ; **éviter le look-ahead** (information pas encore accessible à la date simulée).
- **Comparabilité** : dividendes, fractionnements, biais de sélection, données manquantes, conversions CAD/USD.
- **Licences** : respecter accès, conservation, redistribution.
- **Confidentialité** : aucun compte client réel ni renseignement bancaire confidentiel ; profils/portefeuilles entièrement fictifs.

## 6. Encadrement responsable (contraintes dures)

- **Simulation uniquement** ; aucune transaction réelle ; ne **pas** se présenter comme conseil financier personnalisé.
- **Distinguer faits, hypothèses et scénarios fictifs** ; présenter les incertitudes de façon compréhensible.
- Explications **synthétiques, vérifiables, fidèles aux sources et aux actions observables** ; **ne pas inventer de justification** ni exposer les raisonnements internes détaillés des modèles.
- **Ne pas prédire** les rendements futurs à partir du passé ; la performance passée ne garantit rien.
- Historique = décrire les actifs et éclairer l'adéquation avec les personas (rendements, volatilité sur **période explicite**). La **volatilité n'est qu'un indicateur de risque parmi d'autres** (horizon, diversification, préférences comptent aussi). Expliquer indicateurs, limites, incertitudes ; **ne pas assimiler automatiquement un profil à un actif**.

## 7. Livrables attendus

1. **Prototype démontrable + code source** : cas d'usage complet avec explication accessible (sources, hypothèses, principaux facteurs, limites) ; dépôt de code + **README** (dépendances, sources de données, configuration, instructions de démarrage/reproduction).
2. **Vidéo de démonstration (~5 min)** : exemple de bout en bout — problème choisi, rôle des agents, données et outils, résultat, explication fournie. Idéalement **2 investisseurs distincts**.
3. **Documentation technique** (synthétique) : méthodes/modèles/technologies + justification ; sources, actifs retenus, traitements, hypothèses ; **mécanisme d'explicabilité + exemple reliant une conclusion aux données ou traces d'exécution** ; validations des résultats et explications, limites, améliorations envisagées.
4. **One pager (1 page max)** : problématique, approche agentique, originalité, sources de données, capacité d'explication, bénéfices concrets pour l'utilisateur.

Outils, infrastructures, modèles et services au choix de l'équipe (sauf règles techniques officielles contraires).

## 8. Grille d'évaluation (simplifiée, Annexe 01)

| # | Critère | Poids |
|---|---|---|
| 1 | Qualité, pertinence et innovation de la solution | 20 % |
| 2 | Intelligence agentique et explicabilité | 20 % |
| 3 | Capacité d'analyse et traitement des données | 20 % |
| 4 | Expérience utilisateur UX/UI | 10 % |
| 5 | **Qualité de l'intégration AWS** | 15 % |
| 6 | Présentation, valeur business et marketing | 15 % |

La grille complète est réservée au jury. Noter : l'**intégration AWS pèse 15 %** (non détaillée dans l'énoncé).

## 9. Checklist pour l'agent assistant

- [ ] Choisir un **problème précis** et un cas d'usage focalisé (simple > complexe).
- [ ] Architecture agentique justifiée, avec **traces d'exécution observables** et points de contrôle (gouvernance).
- [ ] **Explicabilité** reliant chaque conclusion à données/sources/hypothèses/limites.
- [ ] Prise en compte des personas (au moins **2 contrastés**) : Amira (risque ≠ « tout permis », diversification), Mateo (ESG + équilibre), Robert (contester une demande incohérente).
- [ ] Tests de **sensibilité** (hypothèses, périodes, scénarios, ex. 2022).
- [ ] Gestion correcte des **prix ajustés, devises CAD/USD, absence de look-ahead**.
- [ ] Documenter **toutes les sources** (origine, date, traitements, limites, licences).
- [ ] Mentions claires : **simulation, pas un conseil financier, pas de prédiction**.
- [ ] Intégration **AWS** solide (15 %) + **UX/UI** soignée (10 %).
- [ ] Livrables : prototype, repo + README, vidéo ~5 min, doc technique, one pager.
- [ ] Vérifier les **consignes logistiques officielles** (deadlines, plateforme de dépôt, règles techniques).