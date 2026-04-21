const { DatabaseSync } = require('node:sqlite');
const db = new DatabaseSync('./data/logipro.db');

const users = db.prepare("SELECT DISTINCT user_id FROM spots WHERE user_id != 'default'").all();
for (const { user_id } of users) {
  const short = user_id.substring(0, 8);
  const oldId = 'depot-permanent-' + short;

  // Vérifier si le vieux id existe
  const old = db.prepare('SELECT id FROM spots WHERE id = ? AND user_id = ?').get(oldId, user_id);
  // Vérifier si le bon id existe déjà
  const good = db.prepare("SELECT id FROM spots WHERE id = 'depot-permanent' AND user_id = ?").get(user_id);

  if (old && good) {
    // Les deux existent — supprimer l'ancien doublon
    db.prepare('DELETE FROM spots WHERE id = ? AND user_id = ?').run(oldId, user_id);
    console.log(`${short} — supprimé doublon ${oldId}`);
  } else if (old && !good) {
    // Renommer l'ancien
    db.prepare('UPDATE spots SET id = ? WHERE id = ? AND user_id = ?').run('depot-permanent', oldId, user_id);
    console.log(`${short} — renommé ${oldId} → depot-permanent`);
  } else {
    console.log(`${short} — déjà correct`);
  }
}
console.log('Terminé.');

