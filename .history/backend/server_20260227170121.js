const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { DatabaseSync } = require('node:sqlite');

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
const db = new DatabaseSync(dbPath);

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

db.exec(`
  CREATE TABLE IF NOT EXISTS spots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    address TEXT NOT NULL,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    opening_time TEXT NOT NULL,
    closing_time TEXT NOT NULL,
    concert_time TEXT,
    gear_selections_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS gears (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    volume REAL NOT NULL,
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

const selectSpotsStmt = db.prepare(`
  SELECT
    id,
    name,
    address,
    lat,
    lon,
    opening_time AS openingTime,
    closing_time AS closingTime,
    concert_time AS concertTime,
    gear_selections_json AS gearSelectionsJson
  FROM spots
  ORDER BY created_at ASC
`);

const insertSpotStmt = db.prepare(`
  INSERT INTO spots (
    id, name, address, lat, lon,
    opening_time, closing_time, concert_time,
    gear_selections_json, created_at, updated_at
  )
  VALUES (
    @id, @name, @address, @lat, @lon,
    @openingTime, @closingTime, @concertTime,
    @gearSelectionsJson, datetime('now'), datetime('now')
  )
`);

const selectGearsStmt = db.prepare(`
  SELECT id, name, category, volume
  FROM gears
  ORDER BY created_at ASC
`);

const insertGearStmt = db.prepare(`
  INSERT INTO gears (id, name, category, volume, created_at, updated_at)
  VALUES (@id, @name, @category, @volume, datetime('now'), datetime('now'))
`);

const mapSpotRow = (row) => ({
  id: row.id,
  name: row.name,
  address: row.address,
  lat: row.lat,
  lon: row.lon,
  openingTime: row.openingTime,
  closingTime: row.closingTime,
  concertTime: row.concertTime || undefined,
  gearSelections: JSON.parse(row.gearSelectionsJson || '[]')
});

const replaceTableTx = (deleteSql, insertStmt, items) => {
  db.exec('BEGIN');
  try {
    db.prepare(deleteSql).run();
    for (const item of items) {
      insertStmt.run(item);
    }
    db.exec('COMMIT');
  } catch (error) {
    db.exec('ROLLBACK');
    throw error;
  }
};

const replaceVehiclesTx = (vehicles) => {
  replaceTableTx('DELETE FROM vehicles', insertVehicleStmt, vehicles);
};

const replaceSpotsTx = (spots) => {
  replaceTableTx('DELETE FROM spots', insertSpotStmt, spots);
};

const replaceGearsTx = (gears) => {
  replaceTableTx('DELETE FROM gears', insertGearStmt, gears);
};

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
 * GET /api/spots
 * Retourne les lieux de concert persistés
 */
app.get('/api/spots', (req, res) => {
  try {
    const rows = selectSpotsStmt.all();
    const spots = rows.map(mapSpotRow);
    return res.json({ success: true, spots });
  } catch (error) {
    console.error('❌ Erreur lecture lieux:', error);
    return res.status(500).json({
      success: false,
      error: 'Erreur lecture base lieux'
    });
  }
});

/**
 * PUT /api/spots/sync
 * Remplace la liste complète des lieux par la version frontend
 */
app.put('/api/spots/sync', (req, res) => {
  const { spots } = req.body;

  if (!Array.isArray(spots)) {
    return res.status(400).json({
      success: false,
      error: 'Le champ spots (array) est requis'
    });
  }

  const isValid = spots.every((spot) => (
    spot &&
    typeof spot.id === 'string' &&
    typeof spot.name === 'string' &&
    typeof spot.address === 'string' &&
    typeof spot.lat === 'number' &&
    typeof spot.lon === 'number' &&
    typeof spot.openingTime === 'string' &&
    typeof spot.closingTime === 'string' &&
    Array.isArray(spot.gearSelections)
  ));

  if (!isValid) {
    return res.status(400).json({
      success: false,
      error: 'Format lieu invalide'
    });
  }

  try {
    const dbRows = spots.map((spot) => ({
      id: spot.id,
      name: spot.name,
      address: spot.address,
      lat: spot.lat,
      lon: spot.lon,
      openingTime: spot.openingTime,
      closingTime: spot.closingTime,
      concertTime: spot.concertTime || null,
      gearSelectionsJson: JSON.stringify(spot.gearSelections || [])
    }));

    replaceSpotsTx(dbRows);

    const rows = selectSpotsStmt.all();
    const persisted = rows.map(mapSpotRow);

    return res.json({ success: true, spots: persisted });
  } catch (error) {
    console.error('❌ Erreur sync lieux:', error);
    return res.status(500).json({
      success: false,
      error: 'Erreur sauvegarde base lieux'
    });
  }
});

/**
 * GET /api/gears
 * Retourne le catalogue matériel persisté
 */
app.get('/api/gears', (req, res) => {
  try {
    const gears = selectGearsStmt.all();
    return res.json({ success: true, gears });
  } catch (error) {
    console.error('❌ Erreur lecture matériels:', error);
    return res.status(500).json({
      success: false,
      error: 'Erreur lecture base matériels'
    });
  }
});

/**
 * PUT /api/gears/sync
 * Remplace le catalogue matériel complet par la version frontend
 */
app.put('/api/gears/sync', (req, res) => {
  const { gears } = req.body;

  if (!Array.isArray(gears)) {
    return res.status(400).json({
      success: false,
      error: 'Le champ gears (array) est requis'
    });
  }

  const isValid = gears.every((gear) => (
    gear &&
    typeof gear.id === 'string' &&
    typeof gear.name === 'string' &&
    typeof gear.category === 'string' &&
    typeof gear.volume === 'number'
  ));

  if (!isValid) {
    return res.status(400).json({
      success: false,
      error: 'Format matériel invalide'
    });
  }

  try {
    replaceGearsTx(gears);
    const persisted = selectGearsStmt.all();
    return res.json({ success: true, gears: persisted });
  } catch (error) {
    console.error('❌ Erreur sync matériels:', error);
    return res.status(500).json({
      success: false,
      error: 'Erreur sauvegarde base matériels'
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
