import os
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from security import hash_password

APP=Path(__file__).parents[1] / 'streamlit_app.py'


def button(app, label):
    return next(b for b in app.button if b.label == label)


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL','sqlite:///'+(tmp_path/'ui.db').as_posix())
    monkeypatch.setenv('ADMIN_PASSWORD_HASH',hash_password('ui-test-password-long'))
    return AppTest.from_file(str(APP),default_timeout=20).run()


def test_game_ui(app):
    assert not app.exception
    button(app,'기록실 입장').click().run()
    assert not app.exception
    for i in range(10):
        q=app.session_state.game['questions'][i]
        # question radio follows sidebar radio.
        next(r for r in app.radio if r.label=='답을 선택하세요').set_value(q['options'][q['answer']]).run()
        button(app,'봉인 해제').click().run()
        assert not app.exception
        button(app,'탈출하기' if i==9 else '다음 봉인으로').click().run()
    assert app.session_state.game['complete']
    button(app,'처음부터 다시 시작').click().run()
    assert 'game' not in app.session_state


def test_admin_ui_login_and_edit(app):
    next(r for r in app.radio if r.label=='페이지').set_value('관리자 페이지').run()
    assert not app.exception
    assert not any(b.label=='문제 저장' for b in app.button)
    app.text_input[0].set_value('wrong')
    button(app,'로그인').click().run()
    assert any('올바르지' in e.value for e in app.error)
    app.text_input[0].set_value('ui-test-password-long')
    button(app,'로그인').click().run()
    assert not app.exception
    assert app.selectbox, [e.value for e in app.error]
    app.selectbox[0].set_value(app.selectbox[0].options[1]).run()
    next(t for t in app.text_input if t.label=='문제 제목').set_value('UI 수정 제목')
    button(app,'문제 저장').click().run()
    assert not app.exception
    button(app,'목록 갱신').click().run()
    app.selectbox[0].set_value(next(v for v in app.selectbox[0].options if 'UI 수정 제목' in v)).run()
    assert next(t for t in app.text_input if t.label=='문제 제목').value=='UI 수정 제목'
    button(app,'관리자 로그아웃').click().run()
    assert not any(b.label=='문제 저장' for b in app.button)
