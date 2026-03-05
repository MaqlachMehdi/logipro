const express = require('express');
const router = express.Router();
const { exportAll } = require('../controllers/exportController');

router.get('/all', exportAll);

module.exports = router;