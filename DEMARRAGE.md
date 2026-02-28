# 🚀 Guide de Démarrage RegieTour

## 1. Installation des dépendances Python

```bash
pip install pandas pulp geopy requests matplotlib numpy
```

Si vous avez python3 :
```bash
pip3 install pandas pulp geopy requests matplotlib numpy
```

## 2. Démarrage du Backend (Terminal 1)

```bash
cd c:\logipro\backend
npm start
```

Vous devriez voir:
```
============================================================
🚀 VRP Solver API démarrée
============================================================
📍 Serveur: http://localhost:5000
📊 Health: http://localhost:5000/api/health
ℹ️  Info: http://localhost:5000/api/info
============================================================
```

## 3. Démarrage Frontend (Terminal 2)

```bash
cd c:\logipro
npm run dev
```

Vous devriez voir:
```
  ➜  Local:   http://localhost:5173/
```

## 4. Utilisation

1. Ouvrir `http://localhost:5173/` dans votre navigateur
2. Ajouter des lieux (concerts/venues)
3. Ajouter du matériel à chaque lieu
4. Configurer les véhicules
5. Dans le panneau "Résumé des Tournées":
   - Sélectionner une stratégie (Équilibré, Économie Véhicules, Rapidité, Distance Min)
   - Cliquer sur "Lancer l'Optimisation"
6. Voir les résultats

## ⚠️ Dépannage

### Erreur "Serveur indisponible"
- Vérifiez que le backend est en cours d'exécution sur terminal 1
- Vérifiez que le port 5000 n'est pas utilisé

### Erreur Python/Modules manquants
- Installez les dépendances: `pip install pandas pulp geopy requests matplotlib numpy`
- Vérifiez que Python est dans le PATH: `python --version`

### Erreur OSRM
- Si les calculs de distance/temps échouent, des valeurs par défaut (50km/50min) sont utilisées
