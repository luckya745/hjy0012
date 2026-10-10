import json
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parents[1]))
from store import Store, csv_bytes
from game import new_game, submit, advance
from security import hash_password, verify_password
from local_sessions import Sessions


@pytest.fixture
def store(tmp_path):
    return Store('sqlite:///' + (tmp_path / 'test.db').as_posix())


def test_edit_add_remove_and_restart(store):
    qs = store.list_questions()
    assert len(qs) == 10
    old_game = new_game(store)
    q = dict(qs[0], title='수정 제목', active=False)
    store.save_question(q, 2)
    added = dict(q, title='추가 문제', active=True)
    added.pop('id')
    new_id = store.save_question(added, 0)
    assert len(store.list_questions()) == 11
    assert len(new_game(store)['questions']) == 10
    assert old_game['questions'][0]['title'] != '수정 제목'
    store.delete_question(new_id)
    assert len(store.list_questions(active_only=True)) == 9
    reopened = Store(str(store.engine.url))
    assert len(reopened.list_questions()) == 10


def test_record_opt_in_retry_complete(store):
    store.set_recording(True)
    assert new_game(store, '기록 없음', False)['run_id'] is None
    g = new_game(store, '=모둠', True)
    g['hint'] = True
    assert not submit(g, store, (g['questions'][0]['answer']+1)%4)
    assert submit(g, store, g['questions'][0]['answer'])
    with pytest.raises(ValueError):
        submit(g, store, 0)
    advance(g)
    while not g['complete']:
        submit(g, store, g['questions'][g['index']]['answer'])
        advance(g)
    rows = store.rows('runs')
    assert len(rows) == 1 and rows[0]['finished'] and rows[0]['attempts'] == 11
    assert rows[0]['solved'] == 10
    assert len(store.rows('events')) == 11
    assert store.rows('events')[0]['hint']
    assert "'=모둠" in csv_bytes(rows).decode('utf-8-sig')


def test_record_off_mid_game(store):
    store.set_recording(True)
    g = new_game(store, '별명', True)
    store.set_recording(False)
    submit(g, store, g['questions'][0]['answer'])
    assert store.rows('events') == []


def test_backup_restore_atomic(store):
    original = store.backup()
    q = store.list_questions()[0]
    store.delete_question(q['id'])
    store.restore_questions(original)
    assert len(store.list_questions()) == 10
    broken = json.loads(original)
    broken['questions'][1]['source'] = 'javascript:alert(1)'
    with pytest.raises(ValueError):
        store.restore_questions(json.dumps(broken))
    assert len(store.list_questions()) == 10


def test_password():
    value = hash_password('test-password-long')
    assert verify_password('test-password-long', value)
    assert not verify_password('wrong', value)
    assert not verify_password('test-password-long', '')


def test_local_server_grading(store):
    sessions = Sessions(store)
    start = sessions.start('', False)
    assert len(start['questions']) == 10 and 'answer' not in start['questions'][0]
    sid = start['session']
    for q in store.list_questions():
        assert sessions.action(sid, q['answer'])['correct']
        response = sessions.action(sid, next_question=True)
    assert response['complete']
    with pytest.raises(ValueError):
        sessions.action(sid, 0)


def test_empty_not_reseeded(store):
    for q in store.list_questions():
        store.delete_question(q['id'])
    assert Store(str(store.engine.url)).list_questions() == []
    with pytest.raises(ValueError):
        new_game(store)
