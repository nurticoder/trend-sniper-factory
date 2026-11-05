from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class Conflict(Exception):
    pass


class Missing(Exception):
    pass


class Store:
    """Short-lived, per-operation connections; writes use atomic revision checks."""

    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise RuntimeError('Database schema is newer than this application')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS opportunities (
                    id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    revision INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ideas (
                    id TEXT PRIMARY KEY,
                    opportunity_id TEXT NOT NULL REFERENCES opportunities(id),
                    payload TEXT NOT NULL,
                    revision INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS ideas_parent ON ideas(opportunity_id);
                CREATE TABLE IF NOT EXISTS idea_versions (
                    idea_id TEXT NOT NULL REFERENCES ideas(id),
                    revision INTEGER NOT NULL,
                    payload TEXT NOT NULL,
                    PRIMARY KEY (idea_id, revision)
                );
                PRAGMA user_version = 1;
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def get(db, table, key):
        # table is an application constant, never a request parameter.
        row = db.execute(f'SELECT payload FROM {table} WHERE id=?', (key,)).fetchone()
        if row is None:
            raise Missing()
        return json.loads(row[0])

    def workspace(self):
        with self.connection() as db:
            return {name: [json.loads(row[0]) for row in db.execute(
                f'SELECT payload FROM {name} ORDER BY rowid DESC')]
                for name in ('opportunities', 'ideas')}

    def create_opportunity(self, fields):
        now = self.now()
        record = {**fields, 'id': str(uuid4()), 'revision': 1,
                  'created_at': now, 'updated_at': now, 'evidence_origin': 'manual'}
        with self.connection() as db:
            db.execute('INSERT INTO opportunities VALUES (?, ?, ?)',
                       (record['id'], json.dumps(record), 1))
        return record

    def update_opportunity(self, key, revision, fields):
        with self.connection() as db:
            old = self.get(db, 'opportunities', key)
            record = {**old, **fields, 'revision': revision + 1, 'updated_at': self.now()}
            cursor = db.execute('UPDATE opportunities SET payload=?, revision=? WHERE id=? AND revision=?',
                                (json.dumps(record), revision + 1, key, revision))
            if cursor.rowcount != 1:
                raise Conflict()
        return record

    def create_idea(self, parent, fields):
        now = self.now()
        record = {**fields, 'id': str(uuid4()), 'opportunity_id': parent,
                  'revision': 1, 'created_at': now, 'updated_at': now,
                  'generation_method': 'manual'}
        with self.connection() as db:
            opportunity = self.get(db, 'opportunities', parent)
            if opportunity['archived']:
                raise Conflict('Unarchive the opportunity before adding ideas')
            db.execute('INSERT INTO ideas VALUES (?, ?, ?, ?)',
                       (record['id'], parent, json.dumps(record), 1))
            db.execute('INSERT INTO idea_versions VALUES (?, ?, ?)',
                       (record['id'], 1, json.dumps(record)))
        return record

    def update_idea(self, key, revision, fields):
        with self.connection() as db:
            old = self.get(db, 'ideas', key)
            record = {**old, **fields, 'revision': revision + 1, 'updated_at': self.now()}
            cursor = db.execute('UPDATE ideas SET payload=?, revision=? WHERE id=? AND revision=?',
                                (json.dumps(record), revision + 1, key, revision))
            if cursor.rowcount != 1:
                raise Conflict()
            db.execute('INSERT INTO idea_versions VALUES (?, ?, ?)',
                       (key, revision + 1, json.dumps(record)))
        return record

    def versions(self, key):
        with self.connection() as db:
            self.get(db, 'ideas', key)
            return [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM idea_versions WHERE idea_id=? ORDER BY revision DESC', (key,))]

    def export(self, key):
        with self.connection() as db:
            opportunity = self.get(db, 'opportunities', key)
            ideas = [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM ideas WHERE opportunity_id=? ORDER BY rowid', (key,))]
        return {'schema_version': 1, 'exported_at': self.now(),
                'opportunity': opportunity, 'ideas': ideas,
                'notice': 'Manual editorial brief. Not verified trend data or publication approval.'}
