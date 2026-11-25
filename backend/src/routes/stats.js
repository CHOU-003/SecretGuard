const express = require('express');
const router = express.Router();
const { getOverview, getTimeline, getBreakdown } = require('../controllers/statsController');
const authenticateAdmin = require('../middleware/authenticateAdmin');

router.get('/overview', authenticateAdmin, getOverview);
router.get('/timeline', authenticateAdmin, getTimeline);
router.get('/breakdown', authenticateAdmin, getBreakdown);

module.exports = router;