const databaseService = require('../services/databaseService');
const CSVBuilder = require('../utils/csvBuilder');

const exportAll = (req, res) => {
  try {
    const spots       = databaseService.getAllSpots();
    const vehicules   = databaseService.getAllVehicules();
    const instruments = databaseService.getAllInstruments();

    const date = new Date().toISOString().split('T')[0];
    let csv = '';

    csv += '### SPOTS ###\n';
    csv += CSVBuilder.toCSV(spots.map(s => ({
      'ID'        : s.id,
      'Nom'       : s.name,
      'Adresse'   : s.address,
      'Latitude'  : s.lat,
      'Longitude' : s.lon,
      'Ouverture' : s.openingTime,
      'Fermeture' : s.closingTime,
      'Concert'   : s.concertTime || '',
      'DuréeConcert(min)' : s.concertDuration != null ? s.concertDuration : '',
      'Matériel'  : s.gearSelectionsJson
    })));

    csv += '\n\n### VEHICULES ###\n';
    csv += CSVBuilder.toCSV(vehicules.map(v => ({
      'ID'         : v.id,
      'Nom'        : v.name,
      'Type'       : v.type,
      'Volume (m³)': v.capacity,
      'Couleur'    : v.color
    })));

    csv += '\n\n### INSTRUMENTS ###\n';
    csv += CSVBuilder.toCSV(instruments.map(i => ({
      'ID'         : i.id,
      'Nom'        : i.name,
      'Catégorie'  : i.category,
      'Volume (m³)': i.volume
    })));

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="base_complete_${date}.csv"`);
    res.send(csv);

    console.log(`✓ Export: ${spots.length} spots, ${vehicules.length} véhicules, ${instruments.length} instruments`);

  } catch (error) {
    console.error('❌ Export error:', error);
    res.status(500).json({ error: error.message });
  }
};

// ✅ Export simple — PAS de classe
module.exports = { exportAll };