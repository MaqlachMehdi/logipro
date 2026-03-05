const { DatabaseSync } = require('node:sqlite');
const path = require('path');

const DB_PATH = path.join(__dirname, '../data/logipro.db');

class DatabaseService {
  constructor() {
    this.db = new DatabaseSync(DB_PATH);
    console.log('✓ DatabaseService connected to logipro.db');
  }

  /**
   * Récupère tous les spots (lieux)
   */
  getAllSpots() {
    const stmt = this.db.prepare(`
      SELECT id, name, address, lat, lon,
             opening_time  AS openingTime,
             closing_time  AS closingTime,
             concert_time  AS concertTime,
             gear_selections_json AS gearSelectionsJson
      FROM spots ORDER BY created_at ASC
    `);
    return stmt.all();
  }

  /**
   * Récupère tous les véhicules
   */
  getAllVehicules() {
    const stmt = this.db.prepare(`
      SELECT id, name, type, capacity, color
      FROM vehicles ORDER BY created_at ASC
    `);
    return stmt.all();
  }

  /**
   * Récupère tous les instruments
   */
  getAllInstruments() {
    const stmt = this.db.prepare(`
      SELECT id, name, category, volume
      FROM gears ORDER BY created_at ASC
    `);
    return stmt.all();
  }
}

module.exports = new DatabaseService();