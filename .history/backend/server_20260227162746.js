const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');

const app = express();
const PORT = 5000;

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb' }));

// ========================================
// BASE DE DONNÉES SQLITE
// ========================================

const dataDir = path.join(__dirname, 'data');
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
}

const dbPath = path.join(dataDir, 'logipro.db');
const db = new Database(dbPath);

db.exec(`
  CREATE TABLE IF NOT EXISTS vehicles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    capacity REAL NOT NULL,
    color TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  )
`);

const selectVehiclesStmt = db.prepare(`
  SELECT id, name, type, capacity, color
  FROM vehicles
  ORDER BY created_at ASC
`);

const insertVehicleStmt = db.prepare(`
  INSERT INTO vehicles (id, name, type, capacity, color, created_at, updated_at)
  VALUES (@id, @name, @type, @capacity, @color, datetime('now'), datetime('now'))
`);

const replaceVehiclesTx = db.transaction((vehicles) => {
  db.prepare('DELETE FROM vehicles').run();
  for (const vehicle of vehicles) {
    insertVehicleStmt.run(vehicle);
  }
});

// ========================================
// ROUTES API
// ========================================

/**
 * GET /api/vehicles
 * Retourne les véhicules persistés
 */
app.get('/api/vehicles', (req, res) => {
  try {
    const vehicles = selectVehiclesStmt.all();
    return res.json({ success: true, vehicles });
  } catch (error) {
    console.error('❌ Erreur lecture véhicules:', error);
    return res.status(500).json({
      success: false,
      error: 'Erreur lecture base véhicules'
    });
  }
});

/**
 * PUT /api/vehicles/sync
 * Remplace la flotte complète par la version frontend
 */
app.put('/api/vehicles/sync', (req, res) => {
  const { vehicles } = req.body;

  if (!Array.isArray(vehicles)) {
    return res.status(400).json({
      success: false,
      error: 'Le champ vehicles (array) est requis'
    });
  }

  const isValid = vehicles.every((v) => (
    v &&
    typeof v.id === 'string' &&
    typeof v.name === 'string' &&
    typeof v.type === 'string' &&
    typeof v.capacity === 'number' &&
    typeof v.color === 'string'
  ));

  if (!isValid) {
    return res.status(400).json({
      success: false,
      error: 'Format véhicule invalide'
    });
  }

  try {
    replaceVehiclesTx(vehicles);
    const persisted = selectVehiclesStmt.all();
    return res.json({ success: true, vehicles: persisted });
  } catch (error) {
    console.error('❌ Erreur sync véhicules:', error);
    return res.status(500).json({
      success: false,
      error: 'Erreur sauvegarde base véhicules'
    });
  }
});

/**
 * POST /api/optimize
 * Reçoit les données de l'interface et les envoie au solveur Python
 */
app.post('/api/optimize', (req, res) => {
  const { lieux, instruments, vehicules, config } = req.body;

  // Valider les données
  if (!lieux || !instruments || !vehicules) {
    return res.status(400).json({
      success: false,
      error: 'Données incomplètes: lieux, instruments et vehicules requis'
    });
  }

  if (!lieux.length || !vehicules.length) {
    return res.status(400).json({
      success: false,
      error: 'Au moins 1 lieu et 1 véhicule requis'
    });
  }

  const selectedConfig = config || 'equilibre';

  console.log(`📥 Demande d'optimisation reçue:`);
  console.log(`   - ${lieux.length} lieux`);
  console.log(`   - ${instruments.length} instruments`);
  console.log(`   - ${vehicules.length} véhicules`);
  console.log(`   - Configuration: ${selectedConfig}`);

  // Préparer les données JSON
  const inputData = {
    lieux,
    instruments,
    vehicules,
    config: selectedConfig
  };

  // Déterminer le répertoire du script Python
  const pythonScriptPath = path.join(__dirname, '..', 'src', 'components', 'tot.py');

  // Essayer 'python' d'abord, puis 'python3'
  let pythonProcess;
  try {
    pythonProcess = spawn('python', [pythonScriptPath], {
      cwd: path.join(__dirname, '..')
    });
  } catch (err) {
    console.warn('⚠️  Python pas trouvé, en essayant python3...');
    pythonProcess = spawn('python3', [pythonScriptPath], {
      cwd: path.join(__dirname, '..')
    });
  }

  let stdout = '';
  let stderr = '';
  let isTimeout = false;

  // Écouter la sortie
  pythonProcess.stdout.on('data', (data) => {
    stdout += data.toString();
  });

  pythonProcess.stderr.on('data', (data) => {
    stderr += data.toString();
  });

  // Timeout après 5 minutes
  const timeout = setTimeout(() => {
    isTimeout = true;
    pythonProcess.kill();
  }, 300000);

  // Envoyer les données au processus Python via stdin
  pythonProcess.stdin.write(JSON.stringify(inputData));
  pythonProcess.stdin.end();

  // Gérer la fermeture du processus
  pythonProcess.on('close', (code) => {
    clearTimeout(timeout);

    if (isTimeout) {
      console.error('⏱️  Timeout du solveur (5 minutes)');
      return res.status(504).json({
        success: false,
        error: 'Timeout: le solveur a pris trop de temps'
      });
    }

    if (code !== 0) {
      console.error('❌ Erreur Python:');
      console.error(stderr);
      return res.status(500).json({
        success: false,
        error: `Erreur du solveur: ${stderr || 'Erreur inconnue'}`
      });
    }

    try {
      // Parser la réponse JSON du solveur
      const result = JSON.parse(stdout);

      if (result.success) {
        console.log(`✅ Solution obtenue: ${result.solution?.label || 'Unknown'}`);
        return res.json(result);
      } else {
        console.error('❌ Erreur du solveur:', result.error);
        return res.status(500).json(result);
      }
    } catch (parseError) {
      console.error('❌ Erreur parsing JSON:', parseError.message);
      console.error('Réponse brute:', stdout.substring(0, 200));
      return res.status(500).json({
        success: false,
        error: 'Erreur parsing résultats du solveur'
      });
    }
  });

  pythonProcess.on('error', (err) => {
    clearTimeout(timeout);
    console.error('❌ Erreur lancement Python:', err);
    return res.status(500).json({
      success: false,
      error: `Erreur lancement solveur: ${err.message}`
    });
  });
});

/**
 * GET /api/health
 * Vérifie que le serveur est actif
 */
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

/**
 * GET /api/info
 * Retourne les informations du serveur
 */
app.get('/api/info', (req, res) => {
  res.json({
    name: 'VRP Solver API',
    version: '1.0.0',
    description: 'Backend pour optimisation de tournées VRP',
    endpoints: {
      'POST /api/optimize': 'Lancer une optimisation',
      'GET /api/health': 'Vérifier l\'état du serveur',
      'GET /api/info': 'Information du serveur'
    }
  });
});

// ========================================
// GESTION DES ERREURS
// ========================================

// 404 Not Found
app.use((req, res) => {
  res.status(404).json({
    success: false,
    error: 'Endpoint non trouvé',
    path: req.path
  });
});

// Erreur globale
app.use((err, req, res, next) => {
  console.error('Erreur serveur:', err);
  res.status(500).json({
    success: false,
    error: 'Erreur serveur interne'
  });
});

// ========================================
// DÉMARRAGE DU SERVEUR
// ========================================

app.listen(PORT, () => {
  console.log('\n' + '='.repeat(60));
  console.log('🚀 VRP Solver API démarrée');
  console.log('='.repeat(60));
  console.log(`📍 Serveur: http://localhost:${PORT}`);
  console.log(`📊 Health: http://localhost:${PORT}/api/health`);
  console.log(`ℹ️  Info: http://localhost:${PORT}/api/info`);
  console.log('='.repeat(60) + '\n');
});

process.on('uncaughtException', (err) => {
  console.error('💥 Exception non gérée:', err);
  process.exit(1);
});
