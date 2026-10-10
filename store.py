"""Shared local SQLite / cloud PostgreSQL repository. No secrets in exported data."""
import csv
import io
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from sqlalchemy import (create_engine, MetaData, Table, Column, String, Text, Integer,
                        Boolean, Float, select, insert, update, delete)

ROOT = Path(__file__).parent


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_question(q):
    result = dict(q)
    for key in ('room', 'title', 'q', 'hint', 'explain'):
        if not isinstance(q.get(key), str) or not q[key].strip() or len(q[key]) > 4000:
            raise ValueError(f'{key}: 빈 값 또는 너무 긴 내용입니다.')
        result[key] = q[key].strip()
    if not isinstance(q.get('clue', ''), str) or len(q.get('clue', '')) > 4000:
        raise ValueError('단서가 너무 길거나 잘못된 형식입니다.')
    options = q.get('options')
    if not isinstance(options, list) or len(options) != 4 or any(not isinstance(v, str) or not v.strip() or len(v) > 500 for v in options):
        raise ValueError('선택지는 비어 있지 않은 문장 4개여야 합니다.')
    if len({v.strip() for v in options}) != 4:
        raise ValueError('선택지 4개는 서로 달라야 합니다.')
    if type(q.get('answer')) is not int or not 0 <= q['answer'] < 4:
        raise ValueError('정답 번호가 올바르지 않습니다.')
    source = q.get('source', '')
    if not isinstance(source, str) or len(source) > 2000:
        raise ValueError('출처 링크 형식이 잘못되었습니다.')
    parsed = urlparse(source)
    if parsed.scheme not in ('https', 'http') or not parsed.netloc:
        raise ValueError('출처에 http/https 링크를 입력하세요.')
    result.update(options=[v.strip() for v in options], active=bool(q.get('active', True)))
    return result


class Store:
    def __init__(self, url=None):
        if not url:
            (ROOT / 'data').mkdir(exist_ok=True)
            url = 'sqlite:///' + (ROOT / 'data' / 'escape.db').as_posix()
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql+psycopg://', 1)
        elif url.startswith('postgresql://'):
            url = url.replace('postgresql://', 'postgresql+psycopg://', 1)
        self.persistent_cloud = url.startswith('postgresql')
        self.engine = create_engine(url, pool_pre_ping=True,
                                    connect_args={'timeout': 20} if url.startswith('sqlite') else {})
        md = MetaData()
        self.questions = Table('questions', md, Column('id', String(36), primary_key=True),
                               Column('position', Integer, nullable=False), Column('payload', Text, nullable=False))
        self.settings = Table('settings', md, Column('id', Integer, primary_key=True),
                              Column('recording', Boolean, nullable=False))
        self.runs = Table('runs', md, Column('id', String(36), primary_key=True),
                          Column('team', String(80)), Column('started', String(40)),
                          Column('finished', String(40)), Column('total', Integer),
                          Column('solved', Integer), Column('attempts', Integer), Column('seconds', Float))
        self.events = Table('events', md, Column('id', String(36), primary_key=True),
                            Column('run_id', String(36), nullable=False), Column('question_id', String(36)),
                            Column('question', Text), Column('choice', Integer), Column('correct', Boolean),
                            Column('hint', Boolean), Column('seconds', Float), Column('created', String(40)))
        md.create_all(self.engine)
        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
        from sqlalchemy.dialects.postgresql import insert as pg_insert
        dialect_insert = pg_insert if self.persistent_cloud else sqlite_insert
        with self.engine.begin() as c:
            c.execute(dialect_insert(self.settings).values(id=1, recording=False).on_conflict_do_nothing())
            # Seed only on the first installation, including after an intentional delete-all.
            marker = c.execute(select(self.settings.c.id).where(self.settings.c.id == 2)).first()
            if marker is None:
                seed = json.loads((ROOT / 'questions.json').read_text(encoding='utf-8'))
                for i, q in enumerate(seed):
                    q = validate_question(q)
                    c.execute(dialect_insert(self.questions).values(id=q['id'], position=i,
                                payload=json.dumps(q, ensure_ascii=False)).on_conflict_do_nothing())
                c.execute(dialect_insert(self.settings).values(id=2, recording=False).on_conflict_do_nothing())

    def list_questions(self, active_only=False):
        with self.engine.connect() as c:
            rows = c.execute(select(self.questions).order_by(self.questions.c.position, self.questions.c.id)).mappings()
            return [dict(json.loads(r['payload']), id=r['id'], position=r['position']) for r in rows
                    if not active_only or json.loads(r['payload']).get('active', True)]

    def save_question(self, q, position):
        q = validate_question(q)
        q['id'] = q.get('id') or str(uuid.uuid4())
        with self.engine.begin() as c:
            exists = c.execute(select(self.questions.c.id).where(self.questions.c.id == q['id'])).first()
            values = dict(position=int(position), payload=json.dumps(q, ensure_ascii=False))
            if exists:
                c.execute(update(self.questions).where(self.questions.c.id == q['id']).values(**values))
            else:
                c.execute(insert(self.questions).values(id=q['id'], **values))
        return q['id']

    def delete_question(self, qid):
        with self.engine.begin() as c:
            c.execute(delete(self.questions).where(self.questions.c.id == qid))

    def recording(self):
        with self.engine.connect() as c:
            return bool(c.execute(select(self.settings.c.recording).where(self.settings.c.id == 1)).scalar())

    def set_recording(self, enabled):
        with self.engine.begin() as c:
            c.execute(update(self.settings).where(self.settings.c.id == 1).values(recording=bool(enabled)))

    def start_run(self, team, total, opt_in):
        if not opt_in or not self.recording():
            return None
        run_id = str(uuid.uuid4())
        with self.engine.begin() as c:
            c.execute(insert(self.runs).values(id=run_id, team=team[:80], started=now(), total=total,
                                              solved=0, attempts=0, seconds=0))
        return run_id

    def record(self, run_id, q, choice, correct, hint, seconds, solved, total_seconds, completed):
        if not run_id or not self.recording():
            return
        with self.engine.begin() as c:
            exists = c.execute(select(self.runs.c.id).where(self.runs.c.id == run_id)).first()
            if not exists:
                return
            c.execute(insert(self.events).values(id=str(uuid.uuid4()), run_id=run_id,
                      question_id=q['id'], question=q['q'], choice=choice, correct=correct,
                      hint=hint, seconds=max(0, seconds), created=now()))
            c.execute(update(self.runs).where(self.runs.c.id == run_id).values(
                solved=solved, attempts=self.runs.c.attempts + 1, seconds=max(0, total_seconds),
                finished=now() if completed else None))

    def rows(self, table):
        if table not in ('runs', 'events'):
            raise ValueError('잘못된 표')
        with self.engine.connect() as c:
            target = getattr(self, table)
            return [dict(r) for r in c.execute(select(target)).mappings()]

    def backup(self):
        return json.dumps({'version': 1, 'questions': self.list_questions(), 'recording': self.recording()},
                          ensure_ascii=False, indent=2)

    def restore_questions(self, raw):
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get('version') != 1 or not isinstance(data.get('questions'), list):
            raise ValueError('지원하지 않는 백업 형식입니다.')
        if not 1 <= len(data['questions']) <= 300:
            raise ValueError('백업 문제 수는 1~300개여야 합니다.')
        rows = [validate_question(q) for q in data['questions']]
        ids = [q.get('id') for q in rows]
        if any(not isinstance(i, str) or not i or len(i) > 36 for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('문제 ID가 없거나 중복되었습니다.')
        with self.engine.begin() as c:
            c.execute(delete(self.questions))
            for i, q in enumerate(rows):
                c.execute(insert(self.questions).values(id=q['id'], position=i,
                          payload=json.dumps(q, ensure_ascii=False)))


def csv_bytes(rows):
    output = io.StringIO(newline='')
    if rows:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            # Spreadsheet formula injection protection for user-entered names/questions.
            writer.writerow({k: "'"+v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v
                             for k, v in row.items()})
    return output.getvalue().encode('utf-8-sig')
