import { openDatabaseAsync, type SQLiteDatabase } from 'expo-sqlite';
import type { Portfolio } from '@gridforge/api-client';
import type { PendingReport } from './outbox';

let database: Promise<SQLiteDatabase> | undefined;
function getDatabase(): Promise<SQLiteDatabase> {
  database ??= openDatabaseAsync('gridforge-field-reports.db')
    .then(async (db) => {
      await db.execAsync(`
      PRAGMA journal_mode=WAL;
      CREATE TABLE IF NOT EXISTS reports (
        requestId TEXT PRIMARY KEY, userId TEXT NOT NULL, facilityId TEXT NOT NULL,
        text TEXT NOT NULL, state TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS portfolio_cache (owner TEXT PRIMARY KEY, body TEXT NOT NULL);
    `);
      return db;
    })
    .catch((error) => {
      database = undefined;
      throw error;
    });
  return database;
}
export async function listReports(owner: string): Promise<PendingReport[]> {
  return (await getDatabase()).getAllAsync<PendingReport>(
    'SELECT * FROM reports WHERE userId=? ORDER BY rowid DESC LIMIT 100',
    owner,
  );
}
export async function saveReport(report: PendingReport): Promise<void> {
  const db = await getDatabase();
  const count = await db.getFirstAsync<{ total: number }>(
    'SELECT count(*) AS total FROM reports WHERE userId=?',
    report.userId,
  );
  if ((count?.total ?? 0) >= 100)
    throw new Error('Queue full. Remove synchronized reports first.');
  await db.runAsync(
    'INSERT INTO reports VALUES(?,?,?,?,?)',
    report.requestId,
    report.userId,
    report.facilityId,
    report.text,
    report.state,
  );
}
export async function markReport(report: PendingReport): Promise<void> {
  await (
    await getDatabase()
  ).runAsync(
    'UPDATE reports SET state=? WHERE requestId=? AND userId=? AND state=?',
    report.state,
    report.requestId,
    report.userId,
    'PENDING',
  );
}
export async function clearSynced(owner: string): Promise<void> {
  await (
    await getDatabase()
  ).runAsync('DELETE FROM reports WHERE userId=? AND state=?', owner, 'SYNCED');
}

export async function cachePortfolio(
  owner: string,
  data: Portfolio,
): Promise<void> {
  await (
    await getDatabase()
  ).runAsync(
    'INSERT OR REPLACE INTO portfolio_cache VALUES(?,?)',
    owner,
    JSON.stringify(data),
  );
}
export async function readPortfolio(owner: string): Promise<Portfolio | null> {
  const row = await (
    await getDatabase()
  ).getFirstAsync<{ body: string }>(
    'SELECT body FROM portfolio_cache WHERE owner=?',
    owner,
  );
  return row ? (JSON.parse(row.body) as Portfolio) : null;
}
