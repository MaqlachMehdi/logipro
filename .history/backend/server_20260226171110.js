const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');

const app = express();
const PORT = 5000;

// Middleware
app.use(cors());
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb' }));

// ========================================
// ROUTES API
// ========================================

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

  // Exécuter le script Python
  const pythonProcess = spawn('python', [pythonScriptPath], {
    cwd: path.join(__dirname, '..')
  });

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
