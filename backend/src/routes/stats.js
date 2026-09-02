const express = require('express');
const router = express.Router();
const { getStats } = require('../controllers/statsController');
const authenticateAdmin = require('../middleware/authenticateAdmin');

router.get('/', authenticateAdmin, getStats);

module.exports = router;