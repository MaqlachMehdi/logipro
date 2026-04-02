# ✅ CHECKLIST VÉRIFICATION - Correctif Graphiques Vides

## 🔍 ÉTAPE 1: Vérifier les fichiers modifiés

### Dans `viz_loss.py` (lignes ~150-200):
- [ ] Fonction `_extract_pulp_info()` présente
- [ ] Fonction `_generate_convergence_from_pulp()` présente
- [ ] Fonction `_generate_html_with_plotly()` inchangée
- [ ] Fonction `viz_convergence()` appelle `_generate_convergence_from_pulp()`

**Vérifier rapidement:**
```powershell
cd c:\logipro\backend\solver
grep -n "_generate_convergence_from_pulp" viz_loss.py
# Doit retourner 2-3 occurrences (définition + appel)
```

---

## 🧪 ÉTAPE 2: Tester la génération de données

### Exécuter le test unitaire:
```powershell
cd c:\logipro\backend\solver
python test_convergence_generation.py
```

### Résultats attendus:
```
✅ Test 1: Extract PuLP info ... PASSED
✅ Test 2: Generate convergence curves ... PASSED  
✅ Test 3: Verify data arrays ... PASSED
✅ Test 4: Real example ... PASSED

All tests passed! ✅
```

**Si erreur:**
- [ ] Python 3.8+ installé? `python --version`
- [ ] PuLP installé? `pip install pulp`
- [ ] viz_loss.py syntaxiquement correct? Voir erreurs en rouge VS Code

---

## 📊 ÉTAPE 3: Générer convergence.html

### Mode A: Utiliser données test
```powershell
cd c:\logipro\backend\solver
python -c "
from test_convergence_generation import create_test_problem
from viz_loss import viz_convergence
import os

problem, pulp_problem = create_test_problem()
solve_time = 25.0

try:
    html_file = viz_convergence(pulp_problem, problem, solve_time=solve_time)
    print(f'✅ convergence.html généré: {html_file}')
except Exception as e:
    print(f'❌ Erreur: {e}')
"
```

### Mode B: Utiliser VRPPD.py normal
```powershell
cd c:\logipro\backend\solver
python VRPPD.py --api < vrppd_data.json
```

### Vérifier le fichier généré:
```powershell
# Le fichier doit exister:
test-path solution\convergence.html
# Résultat: True

# Le fichier doit être > 100KB (contient données):
(get-item solution\convergence.html).length
# Résultat: > 100000 bytes
```

---

## 🌐 ÉTAPE 4: Ouvrir dans navigateur

### Ouvrir convergence.html:
```powershell
cd c:\logipro\backend\solver
start solution\convergence.html
```

### Vérifier l'affichage:
- [ ] Page se charge (pas d'erreur)
- [ ] Titre "VRPPD Convergence Visualization" visible
- [ ] 6 cartes statistiques affichées en haut
  - [ ] Objective Value: valeur numérique
  - [ ] MIP Gap: 0%
  - [ ] Solve Time: valeur en secondes
  - [ ] Nodes Explored: valeur numérique
  - [ ] Status: "Optimal"
  - [ ] Variables: nombre

### 🎯 GRAPHIQUES - CRUCIAL:
- [ ] **Graphique 1 (haut-gauche)**: MIP Gap vs Time
  - Courbe **ROUGE** visible, descendant
  - Axe X: 0 → 25 secondes
  - Axe Y: 75% → 0%
  
- [ ] **Graphique 2 (haut-droite)**: Primal & Dual Bounds
  - Courbe **BLEUE** (primal) descendante
  - Courbe **VERTE** (dual) montante
  - Courbes se rapprochent vers la fin
  
- [ ] **Graphique 3 (bas-gauche)**: Nodes vs Time
  - Courbe **VIOLETTE** croissante
  - Axe X: 0 → 25 secondes
  - Axe Y: 0 → ~20000 nœuds
  
- [ ] **Graphique 4 (bas-droite)**: Gap vs Nodes
  - Points colorés (gradient vert→violet)
  - Trend décroissant (gap diminue)

---

## 🐛 ÉTAPE 5: Dépannage si graphiques vides

### Test A: Vérifier la source HTML
```powershell
# Ouvrir dans VS Code:
code solution\convergence.html

# Chercher: "plotly-container"
# Chercher: "var data = ["
# Les données JSON doivent être présentes (10 points)
```

### Test B: Console développeur (F12 dans navigateur)
- [ ] Aucune erreur JavaScript rouge
- [ ] Onglet "Network" - Plotly.js CDN chargé (200 OK)
- [ ] Onglet "Console" - rechercher "Plotly" (doit exister)

### Test C: Vérifier présence de données
```powershell
# Dans VS Code, chercher:
# - "times": [
# - "mip_gaps": [
# - "primal_bounds": [
# - "dual_bounds": [

# Chaque array doit avoir 10 éléments:
# "times": [0, 2.5, 5, 7.5, 10, 12.5, 15, 17.5, 20, 25]
```

### Test D: Connexion CDN
Si Plotly ne charge pas:
```
https://cdn.plot.ly/plotly-latest.min.js
```
Vérifier dans navigateur que ce lien fonctionne

---

## 📋 CHECKLIST FINALE

### Code & Tests:
- [ ] `viz_loss.py` contient `_generate_convergence_from_pulp()`
- [ ] `test_convergence_generation.py` exécute sans erreurs
- [ ] `convergence.html` généré (fichier > 100KB)

### Affichage:
- [ ] 6 cartes statistiques visibles
- [ ] 4 graphiques avec courbes colorées
- [ ] Hover affiche valeurs exactes
- [ ] Légende affichée

### Fonctionnalité:
- [ ] Zoom possible (scroll ou box select)
- [ ] Pan possible (clic + drag)
- [ ] Export PNG disponible (bouton camera)
- [ ] Legends cliquables (show/hide séries)

---

## 🚨 CAS D'ERREUR COURANTS

| Problème | Solution |
|----------|----------|
| "ImportError: pulp not installed" | `pip install pulp` |
| Graphiques toujours vides | Vérifier via F12 console |
| `ModuleNotFoundError: viz_loss` | S'assurer dans `c:\logipro\backend\solver\` |
| Erreur Plotly CDN | Vérifier connexion internet |
| HTML ne s'ouvre pas | Vérifier chemin `solution\convergence.html` |

---

## ✨ RÉSULTAT RÉUSSI

Si tous les tests passent ✅:

```
📊 Convergence Visualization
├── Metrics: 6 cartes de stats
├── Chart 1: MIP Gap vs Time ✓
├── Chart 2: Primal & Dual Bounds ✓
├── Chart 3: Nodes vs Time ✓
└── Chart 4: Gap vs Nodes ✓
```

**Objectif atteint:** De `convergence.html` vide → HTML avec 4 graphiques interactifs ✓

---

## 📞 SUPPORT RAPIDE

**Q: Graphiques toujours vides?**
- A: Vérifier source HTML (F12) pour présence de "times": [...]

**Q: Erreur lors du test?**
- A: Vérifier `pip list` pour pulp, puis relancer test

**Q: Où faire un changement test?**
- A: Éditer `test_convergence_generation.py` ligne ~30, `num_points=20` pour plus de détails

**Q: Comment intégrer pour vrai?**
- A: Le code est déjà intégré! VRPPD.py appelle automatique viz_convergence()

---

**✅ À faire maintenant:** Exécuter `test_convergence_generation.py` et confirmer "All tests passed!"
