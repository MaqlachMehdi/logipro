const express = require('express');
const { spawn } = require('child_process');
const path = require('path');

const router = express.Router();

router.post('/', (req, res) => {
  const { address } = req.body;
  if (!address || typeof address !== 'string' || !address.trim()) {
    return res.status(400).json({ error: 'Adresse manquante' });
  }

  const scriptPath = path.join(__dirname, '../solver/geocode.py');
  const python = spawn('python3', [scriptPath, address.trim()]);

  let stdout = '';
  let stderr = '';

  python.stdout.on('data', (d) => { stdout += d.toString(); });
  python.stderr.on('data', (d) => { stderr += d.toString(); });

  python.on('close', (code) => {
    if (code !== 0) {
      console.error('❌ Geocode error:', stderr);
      return res.status(500).json({ error: 'Erreur géocodage' });
    }
    try {
      res.json(JSON.parse(stdout));
    } catch {
      res.status(500).json({ error: 'Réponse invalide' });
    }
  });
});

module.exports = router;