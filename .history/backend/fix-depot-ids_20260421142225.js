/**
 * Migration : changer la PRIMARY KEY de spots de (id) vers (id, user_id)
 * Puis recréer les depots avec l'id 'depot-permanent' pour chaque user.
 */
const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('./data/logipro.db');

db.exec('BEGIN');
try {
  // 1. Recréer la table spots avec PK composite (id, user_id)
  db.exec(`
    CREATE TABLE IF NOT EXISTS spots_new (
      id TEXT NOT NULL,
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
      user_id TEXT NOT NULL DEFAULT 'default',
      created_at TEXT NOT NULL DEFAULT (datetime('now')),
      updated_at TEXT NOT NULL DEFAULT (datetime('now')),
      PRIMARY KEY (id, user_id)
    )
  `);

  // 2. Copier toutes les données — en normalisant le depot-permanent-XXXX → depot-permanent
  const rows = db.prepare('SELECT * FROM spots').all();
  const insert = db.prepare(`
    INSERT OR REPLACE INTO spots_new
      (id, name, address, lat, lon, opening_time, closing_time, concert_time,
       concert_duration, setup_duration, teardown_duration, gear_selections_json,
       user_id, created_at, updated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
  `);

  for (const r of rows) {
    // Normaliser l'id du dépôt
    const id = r.id.startsWith('depot-permanent') ? 'depot-permanent' : r.id;
    insert.run(id, r.name, r.address, r.lat, r.lon,
      r.opening_time, r.closing_time, r.concert_time,
      r.concert_duration, r.setup_duration, r.teardown_duration,
      r.gear_selections_json, r.user_id, r.created_at, r.updated_at);
  }

  // 3. Remplacer l'ancienne table
  db.exec('DROP TABLE spots');
  db.exec('ALTER TABLE spots_new RENAME TO spots');

  db.exec('COMMIT');
  console.log('✓ Migration réussie — table spots recréée avec PK (id, user_id)');

  // Vérification
  const check = db.prepare("SELECT user_id, COUNT(*) as nb FROM spots GROUP BY user_id").all();
  console.table(check);
} catch (err) {
  db.exec('ROLLBACK');
  console.error('✗ Erreur migration:', err.message);
}


