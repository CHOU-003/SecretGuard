const express = require('express');
const router = express.Router();
const {
  createProject,
  listProjects,
  getProjectById,
  updateThreshold,
} = require('../controllers/projectController');
const authenticateAdmin = require('../middleware/authenticateAdmin');

router.use(authenticateAdmin);

router.post('/', createProject);
router.get('/', listProjects);
router.get('/:id', getProjectById);
router.put('/:id/threshold', updateThreshold);

module.exports = router;