const express = require('express');
const router = express.Router();
const { listAuditLog } = require('../controllers/auditLogController');
const authenticateAdmin = require('../middleware/authenticateAdmin');

router.get('/', authenticateAdmin, listAuditLog);

module.exports = router;