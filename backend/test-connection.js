const { getPool } = require('./src/db');

async function test() {
  try {
    const pool = await getPool();
    const result = await pool.request().query('SELECT name FROM sys.tables');
    console.log('📋 Danh sách bảng trong DB:');
    console.table(result.recordset);
    process.exit(0);
  } catch (err) {
    console.error('Test thất bại:', err);
    process.exit(1);
  }
}

test();