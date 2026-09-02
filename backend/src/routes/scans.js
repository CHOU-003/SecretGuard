const express = require('express');
const router = express.Router();
const { createScan, listScans, getScanById } = require('../controllers/scanController');
const authenticateAdmin = require('../middleware/authenticateAdmin');
const authenticateService = require('../middleware/authenticateService');

// Python secret-detector gọi vào, dùng API key riêng
router.post('/', authenticateService, createScan);

// Frontend gọi vào, dùng JWT admin
router.get('/', authenticateAdmin, listScans);
router.get('/:id', authenticateAdmin, getScanById);

module.exports = router;