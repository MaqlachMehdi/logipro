const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('./data/logipro.db');

const users = db.prepare("SELECT DISTINCT user_id FROM spots WHERE user_id != 'default'").all();
for (const { user_id } of users) {
  const short = user_id.substring(0, 8);
  const oldId = 'depot-permanent-' + short;
  const result = db.prepare('UPDATE spots SET id = ? WHERE id = ? AND user_id = ?')
    .run('depot-permanent', oldId, user_id);
  console.log(`Utilisateur ${short} — lignes corrigées: ${result.changes}`);
}
console.log('Terminé.');
