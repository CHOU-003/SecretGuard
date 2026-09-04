const express = require('express');
const router = express.Router();
const { getOverview, getTimeline } = require('../controllers/statsController');
const authenticateAdmin = require('../middleware/authenticateAdmin');

router.get('/overview', authenticateAdmin, getOverview);
router.get('/timeline', authenticateAdmin, getTimeline);

module.exports = router;