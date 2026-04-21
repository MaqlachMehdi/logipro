const express = require('express');
const cors = require('cors');
const cookieParser = require('cookie-parser');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const { DatabaseSync } = require('node:sqlite');
const { randomUUID } = require('crypto');

const app = express();
const PORT = 5000;

// Middleware
app.use(cors({ origin: true, credentials: true }));
app.use(cookieParser());
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
    is_available INTEGER NOT NULL DEFAULT 1,
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
    concert_duration INTEGER,
    setup_duration INTEGER,
    teardown_duration INTEGER,
    gear_selections_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
  )
`);

// Migration: add column concert_duration if missing (safe on existing DB)
try {
  const info = db.prepare("PRAGMA table_info('spots')").all();
  const hasDuration = info.some((c) => c.name === 'concert_duration');
  if (!hasDuration) {
    db.exec(`ALTER TABLE spots ADD COLUMN concert_duration INTEGER`);
    console.log('✓ Migration: added concert_duration to spots');
  }
  const hasSetup = info.some((c) => c.name === 'setup_duration');
  if (!hasSetup) {
    db.exec(`ALTER TABLE spots ADD COLUMN setup_duration INTEGER`);
    console.log('✓ Migration: added setup_duration to spots');
  }
  const hasTeardown = info.some((c) => c.name === 'teardown_duration');
  if (!hasTeardown) {
    db.exec(`ALTER TABLE spots ADD COLUMN teardown_duration INTEGER`);
    console.log('✓ Migration: added teardown_duration to spots');
  }
} catch (err) {
  console.warn('⚠️ Migration check failed:', err.message);
}

// Migration: add is_available to vehicles if missing
try {
  const vinfo = db.prepare("PRAGMA table_info('vehicles')").all();
  const hasAvailable = vinfo.some((c) => c.name === 'is_available');
  if (!hasAvailable) {
    db.exec(`ALTER TABLE vehicles ADD COLUMN is_available INTEGER NOT NULL DEFAULT 1`);
    console.log('✓ Migration: added is_available to vehicles');
  }
} catch (err) {
  console.warn('⚠️ Migration is_available check failed:', err.message);
}

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

// ========================================
// MIGRATIONS — colonne user_id sur chaque table
// Règle : les données existantes deviennent "default" (gabarit de départ)
// ========================================
const USER_DEFAULT = 'default';

(function runMigrations() {
  const tables = ['vehicles', 'spots', 'gears'];
  for (const table of tables) {
    try {
      const cols = db.prepare(`PRAGMA table_info('${table}')`).all();
      if (!cols.some((c) => c.name === 'user_id')) {
        db.exec(`ALTER TABLE ${table} ADD COLUMN user_id TEXT NOT NULL DEFAULT '${USER_DEFAULT}'`);
        console.log(`✓ Migration: user_id ajouté à ${table}`);
      }
    } catch (err) {
      console.warn(`⚠️ Migration user_id sur ${table}:`, err.message);
    }
  }
})();

// ========================================
// MIDDLEWARE — identification utilisateur par cookie UUID
// ========================================
const COOKIE_NAME  = 'logipro_uid';
const COOKIE_TTL   = 365 * 24 * 60 * 60 * 1000; // 1 an en ms

/**
 * Copie le gabarit 'default' vers un nouvel utilisateur (dans une transaction).
 * Appelée UNE seule fois à la première visite.
 */
function bootstrapUser(uid) {
  try {
    db.exec('BEGIN');

    db.prepare(`
      INSERT INTO vehicles (id, name, type, capacity, color, is_available, user_id, created_at, updated_at)
      SELECT id || '-' || ?, name, type, capacity, color, is_available, ?, created_at, updated_at
      FROM vehicles WHERE user_id = ?
    `).run(uid.substring(0, 8), uid, USER_DEFAULT);

    db.prepare(`
      INSERT INTO spots (
        id, name, address, lat, lon,
        opening_time, closing_time, concert_time,
        concert_duration, setup_duration, teardown_duration,
        gear_selections_json, user_id, created_at, updated_at
      )
      SELECT
        id || '-' || ?, name, address, lat, lon,
        opening_time, closing_time, concert_time,
        concert_duration, setup_duration, teardown_duration,
        gear_selections_json, ?, created_at, updated_at
      FROM spots WHERE user_id = ?
    `).run(uid.substring(0, 8), uid, USER_DEFAULT);

    db.prepare(`
      INSERT INTO gears (id, name, category, volume, user_id, created_at, updated_at)
      SELECT id || '-' || ?, name, category, volume, ?, created_at, updated_at
      FROM gears WHERE user_id = ?
    `).run(uid.substring(0, 8), uid, USER_DEFAULT);

    db.exec('COMMIT');
    console.log(`✓ Nouvel utilisateur ${uid.substring(0, 8)} initialisé depuis '${USER_DEFAULT}'`);
  } catch (err) {
    db.exec('ROLLBACK');
    console.warn('⚠️ Erreur bootstrap utilisateur:', err.message);
  }
}

/**
 * Middleware : lit le cookie logipro_uid.
 * Si absent → génère un UUID, pose le cookie, copie le gabarit.
 * Injecte req.userId pour toutes les routes.
 */
app.use((req, res, next) => {
  let uid = req.cookies[COOKIE_NAME];

  if (!uid) {
    uid = randomUUID();
    res.cookie(COOKIE_NAME, uid, {
      maxAge: COOKIE_TTL,
      httpOnly: true,
      sameSite: 'lax',
    });
    bootstrapUser(uid);
  }

  req.userId = uid;
  next();
});

// ========================================
// PREPARED STATEMENTS — filtrés par user_id
// ========================================

const selectVehiclesStmt = db.prepare(`
  SELECT id, name, type, capacity, color, is_available AS isAvailable
  FROM vehicles
  WHERE user_id = @userId
  ORDER BY created_at ASC
`);

const insertVehicleStmt = db.prepare(`
  INSERT INTO vehicles (id, name, type, capacity, color, is_available, user_id, created_at, updated_at)
  VALUES (@id, @name, @type, @capacity, @color, @isAvailable, @userId, datetime('now'), datetime('now'))
`);

const selectSpotsStmt = db.prepare(`
  SELECT
    id, name, address, lat, lon,
    opening_time AS openingTime,
    closing_time AS closingTime,
    concert_time AS concertTime,
    concert_duration AS concertDuration,
    setup_duration AS setupDuration,
    teardown_duration AS teardownDuration,
    gear_selections_json AS gearSelectionsJson
  FROM spots
  WHERE user_id = @userId
  ORDER BY created_at ASC
`);

const insertSpotStmt = db.prepare(`
  INSERT INTO spots (
    id, name, address, lat, lon,
    opening_time, closing_time, concert_time,
    concert_duration, setup_duration, teardown_duration,
    gear_selections_json, user_id, created_at, updated_at
  )
  VALUES (
    @id, @name, @address, @lat, @lon,
    @openingTime, @closingTime, @concertTime,
    @concertDuration, @setupDuration, @teardownDuration,
    @gearSelectionsJson, @userId, datetime('now'), datetime('now')
  )
`);

const selectGearsStmt = db.prepare(`
  SELECT id, name, category, volume
  FROM gears
  WHERE user_id = @userId
  ORDER BY created_at ASC
`);

const insertGearStmt = db.prepare(`
  INSERT INTO gears (id, name, category, volume, user_id, created_at, updated_at)
  VALUES (@id, @name, @category, @volume, @userId, datetime('now'), datetime('now'))
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
  concertDuration: row.concertDuration != null ? Number(row.concertDuration) : undefined,
  setupDuration: row.setupDuration != null ? Number(row.setupDuration) : undefined,
  teardownDuration: row.teardownDuration != null ? Number(row.teardownDuration) : undefined,
  gearSelections: JSON.parse(row.gearSelectionsJson || '[]')
});

/**
 * Remplace toute la table d'un utilisateur dans une transaction atomique.
 * @param {string} table   - nom de la table
 * @param {object} stmt    - prepared statement INSERT
 * @param {Array}  items   - lignes à insérer (doivent contenir userId)
 * @param {string} userId  - UUID de l'utilisateur
 */
const replaceTableTx = (table, stmt, items, userId) => {
  db.exec('BEGIN');
  try {
    db.prepare(`DELETE FROM ${table} WHERE user_id = ?`).run(userId);
    for (const item of items) {
      stmt.run(item);
    }
    db.exec('COMMIT');
  } catch (error) {
    db.exec('ROLLBACK');
    throw error;
  }
};

const replaceVehiclesTx = (vehicles, userId) => {
  replaceTableTx('vehicles', insertVehicleStmt, vehicles, userId);
};

const replaceSpotsTx = (spots, userId) => {
  replaceTableTx('spots', insertSpotStmt, spots, userId);
};

const replaceGearsTx = (gears, userId) => {
  replaceTableTx('gears', insertGearStmt, gears, userId);
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
    const rows = selectVehiclesStmt.all({ userId: req.userId });
    const vehicles = rows.map((r) => ({ ...r, isAvailable: r.isAvailable === 1 }));
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
    const dbRows = vehicles.map((v) => ({
      id: v.id,
      name: v.name,
      type: v.type,
      capacity: v.capacity,
      color: v.color,
      isAvailable: v.isAvailable === false || v.isAvailable === 0 ? 0 : 1,
      userId: req.userId,
    }));
    replaceVehiclesTx(dbRows, req.userId);
    const rows = selectVehiclesStmt.all({ userId: req.userId });
    const persisted = rows.map((r) => ({ ...r, isAvailable: r.isAvailable === 1 }));
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
    const rows = selectSpotsStmt.all({ userId: req.userId });
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
    !(spot.lat === 0 && spot.lon === 0) &&
    typeof spot.openingTime === 'string' &&
    typeof spot.closingTime === 'string' &&
    Array.isArray(spot.gearSelections)
  ));

  if (!isValid) {
    const badSpot = spots.find((s) => s && s.lat === 0 && s.lon === 0);
    const errorMsg = badSpot
      ? `Lieu "${badSpot.name}" non géocodé (lat=0, lon=0). Vérifiez l'adresse.`
      : 'Format lieu invalide';
    return res.status(400).json({
      success: false,
      error: errorMsg,
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
      concertDuration: typeof spot.concertDuration === 'number' ? spot.concertDuration : null,
      setupDuration: typeof spot.setupDuration === 'number' ? spot.setupDuration : null,
      teardownDuration: typeof spot.teardownDuration === 'number' ? spot.teardownDuration : null,
      gearSelectionsJson: JSON.stringify(spot.gearSelections || []),
      userId: req.userId,
    }));

    replaceSpotsTx(dbRows, req.userId);

    const rows = selectSpotsStmt.all({ userId: req.userId });
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
    const gears = selectGearsStmt.all({ userId: req.userId });
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
    const dbRows = gears.map((g) => ({ ...g, userId: req.userId }));
    replaceGearsTx(dbRows, req.userId);
    const persisted = selectGearsStmt.all({ userId: req.userId });
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
  const pythonScriptPath = path.join(__dirname, 'solver', 'tot.py');

  // Essayer 'python' d'abord, puis 'python3'
  let pythonProcess;
  try {
    if (!fs.existsSync(pythonScriptPath)) {
      throw new Error(`Solveur Python introuvable: ${pythonScriptPath}`);
    }
    pythonProcess = spawn('python', [pythonScriptPath], {
      cwd: path.join(__dirname),
      stdio: ['pipe', 'pipe', 'pipe']
    });
  } catch (err) {
    console.warn('⚠️  Python pas trouvé ou script manquant, en essayant python3...');
    try {
      pythonProcess = spawn('python3', [pythonScriptPath], {
        cwd: path.join(__dirname),
        stdio: ['pipe', 'pipe', 'pipe']
      });
    } catch (err2) {
      console.error('❌ Impossible de démarrer le solveur Python:', err2);
      return res.status(500).json({ success: false, error: 'Solveur Python indisponible' });
    }
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
 * POST /api/optimize/run
 * Lit la base de données et construit le JSON pour le solveur Python
 * Le frontend n'a plus besoin d'envoyer les données — le backend les lit depuis la DB
 */
app.post('/api/optimize/run', (req, res) => {
  const { config } = req.body;

  // 1. Lire les spots depuis la DB (dépôt inclus grâce à son id 'depot-permanent')
  let spots, vehicles, gears;
  try {
    const spotRows = selectSpotsStmt.all();
    spots = spotRows.map(mapSpotRow);

    const vehicleRows = selectVehiclesStmt.all();
    vehicles = vehicleRows;

    const gearRows = selectGearsStmt.all();
    gears = gearRows;
  } catch (err) {
    console.error('❌ Erreur lecture DB:', err);
    return res.status(500).json({ success: false, error: 'Erreur lecture base de données' });
  }

  // 2. Vérifier que le dépôt existe bien en DB
  const depot = spots.find((s) => s.id === 'depot-permanent');
  if (!depot) {
    return res.status(400).json({
      success: false,
      error: 'Dépôt introuvable en base (id: depot-permanent). Veuillez configurer le dépôt.'
    });
  }

  // 3. Vérifications minimales
  const concertSpots = spots.filter((s) => s.id !== 'depot-permanent');
  if (concertSpots.length === 0) {
    return res.status(400).json({ success: false, error: 'Aucun lieu de concert en base.' });
  }
  if (vehicles.length === 0) {
    return res.status(400).json({ success: false, error: 'Aucun véhicule en base.' });
  }

  // 4. Construire le catalogue d'instruments (map id → nom pour résoudre les gearSelections)
  const gearMap = {};
  for (const g of gears) {
    gearMap[g.id] = { name: g.name, volume: g.volume };
  }

  // 5. Construire le catalogue d'instruments (nouveau schéma VRPPD)
  const instrument_catalog = gears.map((g) => ({
    name: g.name,
    volume_m3: g.volume,
  }));

  // 6. Construire la liste "locations" — dépôt en index 0, puis les concerts
  const allSpots = [depot, ...concertSpots];

  const toMinutes = (hhmm) => {
    if (!hhmm) return null;
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + (m || 0);
  };

  const locations = allSpots.map((spot, index) => {
    const instrumentsList = [];
    for (const sel of spot.gearSelections || []) {
      const gear = gearMap[sel.gearId];
      if (gear) {
        for (let i = 0; i < sel.quantity; i++) {
          instrumentsList.push(gear.name);
        }
      }
    }

    return {
      id: index,
      name: spot.name,
      address: spot.address,
      lat: spot.lat,
      lon: spot.lon,
      open_time_min: toMinutes(spot.openingTime),
      close_time_min: toMinutes(spot.closingTime),
      concert_start_min: spot.concertTime ? toMinutes(spot.concertTime) : null,
      concert_duration_min: spot.concertDuration != null ? spot.concertDuration : 0,
      setup_duration_min: spot.setupDuration != null ? spot.setupDuration : 0,
      teardown_duration_min: spot.teardownDuration != null ? spot.teardownDuration : 0,
      instruments: instrumentsList.join(', '),
    };
  });

  // 7. Construire la liste "vehicles"
  const vehicles_json = vehicles.map((v, index) => ({
    id: index + 1,
    plate: v.name,
    capacity_m3: v.capacity,
    is_available: v.isAvailable ?? 1,
  }));

  // 8. Log de contrôle
  console.log('📦 JSON construit depuis la DB:');
  console.log(`   - Dépôt: ${depot.name} | lat=${depot.lat} lon=${depot.lon} | adresse="${depot.address}"`);
  console.log(`   - ${locations.length} lieux (dont dépôt)`);
  console.log(`   - ${instrument_catalog.length} instruments dans le catalogue`);
  console.log(`   - ${vehicles_json.length} véhicules`);

  const selectedConfig = config || 'equilibre';
  const inputData = { locations, instrument_catalog, vehicles: vehicles_json, config: selectedConfig };

  console.log('📋 JSON COMPLET ENVOYÉ AU SOLVEUR:');
  console.log(JSON.stringify(inputData, null, 2));

  // 9. Lancer VRPPD.py en mode API (lit stdin, renvoie JSON sur stdout)
  const pythonScriptPath = path.join(__dirname, 'solver', 'VRPPD.py');
  if (!fs.existsSync(pythonScriptPath)) {
    return res.status(500).json({ success: false, error: `Solveur Python introuvable: ${pythonScriptPath}` });
  }

  // Utiliser le Python du venv (qui a tqdm, pulp, etc.) en priorité
  // Support Windows (.venv/Scripts/python.exe) et Linux/Docker (.venv/bin/python)
  const venvPythonWin = path.join(__dirname, 'solver', '.venv', 'Scripts', 'python.exe');
  const venvPythonLinux = path.join(__dirname, 'solver', '.venv', 'bin', 'python');
  const venvPython = fs.existsSync(venvPythonWin) ? venvPythonWin
    : fs.existsSync(venvPythonLinux) ? venvPythonLinux
    : null;
  const pythonExe = venvPython ?? 'python';

  let pythonProcess;
  try {
    pythonProcess = spawn(pythonExe, [pythonScriptPath, '--api'], {
      cwd: path.join(__dirname),
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } catch (err2) {
    return res.status(500).json({ success: false, error: `Erreur lancement solveur: ${err2.message}` });
  }

  let stdout = '';
  let stderr = '';
  let isTimeout = false;

  pythonProcess.stdout.on('data', (data) => { stdout += data.toString(); });
  pythonProcess.stderr.on('data', (data) => { stderr += data.toString(); });

  const timeout = setTimeout(() => {
    isTimeout = true;
    pythonProcess.kill();
  }, 300000);

  pythonProcess.stdin.write(JSON.stringify(inputData));
  pythonProcess.stdin.end();

  pythonProcess.on('close', (code) => {
    clearTimeout(timeout);
    // Always print solver stderr (progress + debug summary) to Node console
    if (stderr) console.log('[solver stderr]\n' + stderr);
    if (isTimeout) {
      return res.status(504).json({ success: false, error: 'Timeout: le solveur a pris trop de temps' });
    }
    if (code !== 0) {
      return res.status(500).json({ success: false, error: `Erreur du solveur: ${stderr || 'Erreur inconnue'}` });
    }
    try {
      // Find the last non-empty line — PuLP/CBC may print junk before our JSON
      const jsonLine = stdout.trim().split('\n').filter(l => l.trim().startsWith('{')).pop();
      if (!jsonLine) throw new Error('no JSON line found in stdout');
      const result = JSON.parse(jsonLine);
      return res.json(result);
    } catch (parseErr) {
      console.error('❌ Erreur parsing JSON:', parseErr.message);
      console.error('stdout brut:', JSON.stringify(stdout.substring(0, 500)));
      console.error('stderr brut:', stderr.substring(0, 500));
      return res.status(500).json({ success: false, error: 'Erreur parsing résultats du solveur' });
    }
  });

  pythonProcess.on('error', (err) => {
    clearTimeout(timeout);
    return res.status(500).json({ success: false, error: `Erreur lancement solveur: ${err.message}` });
  });
});

/**
 * GET /api/optimize/preview
 * Retourne le JSON qui serait envoyé au solveur, SANS le lancer
 * Utile pour déboguer
 */
app.get('/api/optimize/preview', (req, res) => {
  try {
    const spotRows = selectSpotsStmt.all();
    const spots = spotRows.map(mapSpotRow);
    const vehicleRows = selectVehiclesStmt.all();
    const gears = selectGearsStmt.all();

    const depot = spots.find((s) => s.id === 'depot-permanent');
    if (!depot) {
      return res.status(400).json({ success: false, error: 'Dépôt introuvable en base.' });
    }

    const concertSpots = spots.filter((s) => s.id !== 'depot-permanent');
    const gearMap = {};
    for (const g of gears) {
      gearMap[g.id] = { name: g.name, volume: g.volume };
    }

    const allSpots = [depot, ...concertSpots];

    const toMinutesPreview = (hhmm) => {
      if (!hhmm) return null;
      const [h, m] = hhmm.split(':').map(Number);
      return h * 60 + (m || 0);
    };

    const locations = allSpots.map((spot, index) => {
      const instrumentsList = [];
      for (const sel of spot.gearSelections || []) {
        const gear = gearMap[sel.gearId];
        if (gear) {
          for (let i = 0; i < sel.quantity; i++) {
            instrumentsList.push(gear.name);
          }
        }
      }
      return {
        id: index,
        name: spot.name,
        address: spot.address,
        lat: spot.lat,
        lon: spot.lon,
        open_time_min: toMinutesPreview(spot.openingTime),
        close_time_min: toMinutesPreview(spot.closingTime),
        concert_start_min: spot.concertTime ? toMinutesPreview(spot.concertTime) : null,
        concert_duration_min: spot.concertDuration != null ? spot.concertDuration : 0,
        setup_duration_min: spot.setupDuration != null ? spot.setupDuration : 0,
        teardown_duration_min: spot.teardownDuration != null ? spot.teardownDuration : 0,
        instruments: instrumentsList.join(', '),
      };
    });

    const instrument_catalog = gears.map((g) => ({ name: g.name, volume_m3: g.volume }));
    const vehicles_json = vehicleRows.map((v, index) => ({
      id: index + 1,
      plate: v.name,
      capacity_m3: v.capacity,
      is_available: v.isAvailable ?? 1,
    }));

    return res.json({ success: true, json: { locations, instrument_catalog, vehicles: vehicles_json } });

  } catch (err) {
    return res.status(500).json({ success: false, error: err.message });
  }
});

/**
 * POST /api/geocode
 * Convertit une adresse en coordonnées GPS via Nominatim (OpenStreetMap)
 */
app.post('/api/geocode', async (req, res) => {
  const { address } = req.body;
  if (!address?.trim()) {
    return res.status(400).json({ error: 'Adresse manquante' });
  }
  try {
    const url = `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(address.trim())}&limit=1`;
    const response = await fetch(url, {
      headers: { 'User-Agent': 'RegietourApp/1.0' },
    });
    const data = await response.json();
    if (!data.length) {
      return res.status(404).json({ error: `Adresse introuvable : "${address.trim()}"` });
    }
    return res.json({ lat: parseFloat(data[0].lat), lon: parseFloat(data[0].lon) });
  } catch (err) {
    return res.status(500).json({ error: `Erreur géocodage : ${err.message}` });
  }
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

/**
 * GET /api/export/all
 * Exporte toutes les données de la DB en CSV
 */
app.get('/api/export/all', (req, res) => {
  try {
    const spotRows = selectSpotsStmt.all();
    const spots = spotRows.map(mapSpotRow);
    const vehicles = selectVehiclesStmt.all();
    const gears = selectGearsStmt.all();

    const gearMap = {};
    for (const g of gears) {
      gearMap[g.id] = { name: g.name, volume: g.volume };
    }

    const lines = [];

    // Section SPOTS
    lines.push('=== LIEUX ===');
    lines.push('id,nom,adresse,lat,lon,ouverture,fermeture,concert,duree_concert_min,instruments,volume_total');

    for (const s of spots) {
      // Dictionnaire [{ gearId, quantity }] directement depuis gearSelections
      const instrumentsDict = (s.gearSelections || [])
        .filter(sel => gearMap[sel.gearId]) // ignorer les ids inconnus
        .map(sel => ({
          gearId: sel.gearId,
          quantity: sel.quantity
        }));

      // Calcul volume total
      const volumeTotal = (s.gearSelections || []).reduce((acc, sel) => {
        const gear = gearMap[sel.gearId];
        return acc + (gear ? gear.volume * sel.quantity : 0);
      }, 0);

      // Sérialiser le dictionnaire en JSON dans la cellule CSV
      const instrumentsStr = JSON.stringify(instrumentsDict);

      lines.push(
        `"${s.id}","${s.name}","${s.address}",${s.lat},${s.lon},"${s.openingTime || ''}","${s.closingTime || ''}","${s.concertTime || ''}",${s.concertDuration != null ? s.concertDuration : ''},"${instrumentsStr.replace(/"/g, '""')}",${volumeTotal.toFixed(2)}`
      );
    }

    lines.push('');

    // Section VEHICULES
    lines.push('=== VEHICULES ===');
    lines.push('id,nom,capacite');
    for (const v of vehicles) {
      lines.push(`"${v.id}","${v.name}",${v.capacity}`);
    }

    lines.push('');

    // Section MATERIELS
    lines.push('=== MATERIELS ===');
    lines.push('id,nom,volume');
    for (const g of gears) {
      lines.push(`"${g.id}","${g.name}",${g.volume}`);
    }

    const csv = lines.join('\n');

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="base_complete_${new Date().toISOString().split('T')[0]}.csv"`);
    return res.send('\uFEFF' + csv);

  } catch (err) {
    console.error('❌ Erreur export:', err);
    return res.status(500).json({ success: false, error: 'Erreur export base de données' });
  }
});

/**
 * GET /api/solution/map-data
 * Extrait les données vehicleRoutes, markersData et concertsData
 * du fichier summary.html généré par le solveur Python.
 */
app.get('/api/solution/map-data', (req, res) => {
  const summaryPath = path.join(__dirname, 'solver', 'solution', 'summary.html');
  if (!fs.existsSync(summaryPath)) {
    return res.status(404).json({ success: false, error: 'Aucune solution disponible. Lancez d\'abord une optimisation.' });
  }

  try {
    const html = fs.readFileSync(summaryPath, 'utf-8');

    const extractVar = (varName) => {
      const rx = new RegExp(`var\\s+${varName}\\s*=\\s*(\\[.*?\\]);`, 's');
      const m = html.match(rx);
      if (!m) return null;
      return JSON.parse(m[1]);
    };

    const vehicleRoutes = extractVar('vehicleRoutes');
    const markersData   = extractVar('markersData');
    const concertsData  = extractVar('concertsData');

    if (!vehicleRoutes) {
      return res.status(500).json({ success: false, error: 'Impossible de lire les données de la solution.' });
    }

    return res.json({ success: true, vehicleRoutes, markersData: markersData || [], concertsData: concertsData || [] });
  } catch (err) {
    console.error('❌ Erreur lecture solution map-data:', err);
    return res.status(500).json({ success: false, error: 'Erreur lecture fichier solution' });
  }
});

/**
 * GET /api/solution/pdf
 * Génère un PDF du résumé de tournée via Puppeteer et le renvoie en téléchargement direct.
 */
app.get('/api/solution/pdf', async (req, res) => {
  const htmlPath = path.join(__dirname, 'solver', 'solution_terminal.html');
  if (!fs.existsSync(htmlPath)) {
    return res.status(404).json({ success: false, error: 'Aucune solution disponible. Lancez d\'abord une optimisation.' });
  }

  let browser;
  try {
    const puppeteer = require('puppeteer');
    browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();

    const htmlContent = fs.readFileSync(htmlPath, 'utf8');
    await page.setContent(htmlContent, { waitUntil: 'domcontentloaded' });

    const pdfData = await page.pdf({
      format: 'A4',
      printBackground: true,
      margin: { top: '1cm', bottom: '1cm', left: '1cm', right: '1cm' },
    });

    // Puppeteer v22+ retourne Uint8Array — conversion en Buffer nécessaire pour Express
    const pdfBuffer = Buffer.from(pdfData);

    res.setHeader('Content-Type', 'application/pdf');
    res.setHeader('Content-Disposition', 'attachment; filename="resume_tournee.pdf"');
    res.setHeader('Content-Length', pdfBuffer.length);
    res.end(pdfBuffer);
  } catch (err) {
    console.error('❌ Erreur génération PDF:', err);
    res.status(500).json({ success: false, error: 'Erreur lors de la génération du PDF' });
  } finally {
    if (browser) await browser.close();
  }
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
