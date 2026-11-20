import { DatabaseSync } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

export function openStore(path) {
  if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  const db = new DatabaseSync(path);
  db.exec(`
    CREATE TABLE IF NOT EXISTS cases (
      request_key TEXT PRIMARY KEY, digest TEXT NOT NULL, payload TEXT NOT NULL, delivered INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS identities (
      case_id TEXT NOT NULL, token TEXT NOT NULL, identity TEXT NOT NULL,
      PRIMARY KEY (case_id, token, identity)
    );
  `);
  return {
    lookup: key => db.prepare('SELECT * FROM cases WHERE request_key = ?').get(key),
    save(key, digest, report, mappings) {
      db.exec('BEGIN IMMEDIATE');
      try {
        db.prepare('INSERT INTO cases(request_key, digest, payload) VALUES (?, ?, ?)')
          .run(key, digest, JSON.stringify(report));
        const insert = db.prepare('INSERT OR IGNORE INTO identities VALUES (?, ?, ?)');
        for (const m of mappings) insert.run(report.case_id, m.token, m.identity);
        db.exec('COMMIT');
      } catch (error) {
        db.exec('ROLLBACK');
        throw error;
      }
    },
    delivered: key => db.prepare('UPDATE cases SET delivered = 1 WHERE request_key = ?').run(key),
    close: () => db.close(),
  };
}
