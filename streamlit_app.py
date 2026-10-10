import json
import os
import threading
import time
from pathlib import Path
import streamlit as st
from store import Store, csv_bytes
from security import verify_password
from game import new_game, submit, advance

st.set_page_config(page_title='프랑스혁명 · 자유의 열쇠', page_icon='🗝️', layout='wide')


def config(key):
    value = os.environ.get(key)
    if value is not None:
        return value
    try:
        return st.secrets.get(key, '')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ''


@st.cache_resource
def repository(url):
    return Store(url or None)


@st.cache_resource
def login_guard():
    return {'lock': threading.Lock(), 'failures': [], 'until': 0}


def connection_diagnosis(exc):
    """Return fixed guidance only; exception text can contain credentials."""
    original = getattr(exc, 'orig', exc)
    code = getattr(original, 'sqlstate', None)
    message = str(original).lower()
    if code == '28P01' or 'password authentication failed' in message:
        return 'DB_AUTH', 'DB 서버가 비밀번호를 거부했습니다. 프로젝트의 DB 비밀번호와 한 번만 적용한 URL 인코딩을 확인하세요.'
    if 'tenant or user not found' in message:
        return 'DB_USER', 'Pooler 사용자명 또는 호스트가 프로젝트와 일치하지 않습니다. Connect의 Session pooler 주소를 다시 확인하세요.'
    if code == '42501' or 'permission denied' in message:
        return 'DB_PERMISSION', '연결은 되었지만 테이블 생성 또는 데이터 접근 권한이 없습니다. DB 사용자 권한을 확인하세요.'
    if 'could not translate host' in message or 'name or service not known' in message or 'getaddrinfo' in message:
        return 'DB_HOST', 'DB 호스트 이름을 찾을 수 없습니다. 복사한 호스트와 비밀번호의 URL 인코딩을 확인하세요.'
    if 'timeout' in message or 'timed out' in message or 'network is unreachable' in message or 'connection refused' in message:
        return 'DB_NETWORK', 'DB 서버에 도달하지 못했습니다. Supabase 프로젝트가 실행 중인지와 Session pooler 연결 정보를 확인하세요.'
    if 'ssl' in message or 'certificate' in message:
        return 'DB_TLS', '암호화 연결 설정을 확인하세요. 연결 주소의 sslmode=require 옵션을 확인하세요.'
    if isinstance(exc, (ImportError, ModuleNotFoundError)):
        return 'DB_PACKAGE', 'DB 드라이버 또는 필수 라이브러리를 불러오지 못했습니다. requirements.txt 설치 로그를 확인하세요.'
    if 'could not parse' in message or 'invalid dsn' in message or 'invalid integer' in message or 'invalid connection option' in message:
        return 'DB_URL', '연결 주소 형식이 잘못되었습니다. DATABASE_URL에는 설명 문구 없이 실제 URI만 입력하세요.'
    if isinstance(exc, FileNotFoundError):
        return 'DB_SEED', '초기 문제 파일 questions.json이 배포 저장소에 있는지 확인하세요.'
    if code == '42P01' or code == '42703':
        return 'DB_SCHEMA', '기존 데이터베이스의 테이블 구조가 앱과 다릅니다. 앱 전용 데이터베이스인지 확인하세요.'
    if isinstance(exc, ValueError):
        return 'DB_VALUE', '연결 주소 또는 초기 문제 데이터의 형식을 확인하세요.'
    return 'DB_UNKNOWN', '추가 진단이 필요합니다. 아래 오류 종류와 진단 코드만 알려주세요.'


try:
    store = repository(config('DATABASE_URL'))
except Exception as exc:
    st.error('데이터 저장소에 연결할 수 없습니다. 관리자가 DATABASE_URL과 데이터베이스 연결 상태를 확인해 주세요.')
    diagnosis, guidance = connection_diagnosis(exc)
    st.info(guidance)
    # Class names and a fixed code are safe to share; never show the raw error/URI.
    st.code(f'진단 코드: {diagnosis}\n오류 종류: {type(exc).__name__}', language=None)
    st.stop()

st.markdown('''<style>
.stApp{background:radial-gradient(ellipse at top left,#ede6d7,transparent 55%),#f7f3eb}
h1,h2,h3{letter-spacing:-.04em}div[data-testid="stMetric"]{background:#eae2d4;border-radius:12px;padding:14px}
section[data-testid="stSidebar"]{border-right:3px solid #b68135}
div.stButton>button{border-radius:10px;min-height:46px}
</style>''', unsafe_allow_html=True)
with st.sidebar:
    st.caption('PARIS, 1789 · ESCAPE ARCHIVE')
    st.title('자유의 열쇠')
    page = st.radio('페이지', ['방탈출 게임', '관리자 페이지', '사용 안내'])
    st.divider()
    st.caption('질문·힌트·해설은 한국어로 제공됩니다.')
    if os.environ.get('ESCAPE_LOCAL') == '1':
        st.link_button('햄스터 연결 게임 열기', os.environ.get('ROBOT_GAME_URL', 'http://127.0.0.1:8877'))
    else:
        st.caption('햄스터 실물 연결은 PC용 실행 꾸러미에서 제공합니다.')


def play():
    st.title('프랑스혁명 · 자유의 열쇠')
    st.write('잠긴 파리의 기록실에서 혁명의 흔적을 찾으세요. 모든 봉인을 풀면 자유의 문이 열립니다.')
    if 'game' not in st.session_state:
        questions = store.list_questions(active_only=True)
        st.info(f'현재 활성 문제 {len(questions)}개 · 힌트와 재도전을 사용할 수 있습니다.')
        enabled = store.recording()
        team = st.text_input('모둠명 또는 별명 (실명 입력 불필요)', max_chars=80) if enabled else ''
        opt_in = st.checkbox('모둠명, 답안 시도, 힌트 사용 여부, 소요 시간을 저장합니다.') if enabled else False
        if not enabled:
            st.caption('현재 학습 기록 저장이 꺼져 있습니다.')
        if st.button('기록실 입장', type='primary', disabled=not questions):
            try:
                st.session_state.game = new_game(store, team, opt_in)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))
        return
    g = st.session_state.game
    qs = g['questions']
    count = len(qs)
    if g['record_error']:
        st.warning('일부 기록을 저장하지 못했습니다. 게임은 계속할 수 있으며 관리자에게 저장소 확인을 요청해 주세요.')
    st.caption('기록 저장 동의한 플레이' if g['run_id'] else '기록을 저장하지 않는 플레이')
    solved_count = count if g['complete'] else g['index'] + int(g['solved'])
    st.progress(solved_count / count, text=f'봉인 {solved_count} / {count}')
    a,b = st.columns(2)
    a.metric('해결한 봉인', f'{solved_count} / {count}')
    b.metric('총 도전', f"{g['attempts']}회")
    if g['complete']:
        st.success('자유의 문이 열렸습니다!')
        st.write(f"{count}개의 기록을 되찾았습니다. 총 {g['attempts']}번 도전했습니다.")
        st.caption('진행 중이던 게임에는 시작 시점의 문제를 사용합니다. 새 게임에는 관리자 수정 내용이 반영됩니다.')
    else:
        q = qs[g['index']]
        with st.container(border=True):
            st.caption(q['room'])
            st.subheader(q['title'])
            st.info(q['clue'])
            st.write(q['q'])
            selected = st.radio('답을 선택하세요', q['options'],
                                index=None, key=f"choice_{g['index']}", disabled=g['solved'])
            if st.button('봉인 해제', type='primary', disabled=selected is None or g['solved']):
                submit(g, store, q['options'].index(selected))
                st.rerun()
            if st.button('힌트 보기', disabled=g['solved']):
                g['hint'] = True
                st.rerun()
            if g['hint']:
                st.info(q['hint'])
            if g['message']:
                (st.success if g['solved'] else st.error)(g['message'])
            if g['solved']:
                st.link_button('해설 출처 확인', q['source'])
                if st.button('탈출하기' if g['index']==count-1 else '다음 봉인으로', type='primary'):
                    advance(g)
                    st.rerun()
    if st.button('처음부터 다시 시작'):
        del st.session_state['game']
        for key in list(st.session_state):
            if key.startswith('choice_'):
                del st.session_state[key]
        st.rerun()


def authenticate():
    encoded = config('ADMIN_PASSWORD_HASH')
    if not encoded:
        st.warning('관리자 비밀번호 설정이 필요합니다. 로컬: python setup_admin.py / 배포: Streamlit Secrets에 ADMIN_PASSWORD_HASH를 설정하세요.')
        return False
    if st.session_state.get('admin_hash') == encoded:
        if st.button('관리자 로그아웃'):
            st.session_state.pop('admin_hash', None)
            st.rerun()
        return True
    st.caption('비밀번호는 서버에서만 확인합니다.')
    with st.form('admin_login'):
        password = st.text_input('관리자 비밀번호', type='password', max_chars=200, key='admin_password_input')
        clicked = st.form_submit_button('로그인', type='primary')
    if clicked:
        guard = login_guard()
        with guard['lock']:
            current = time.monotonic()
            if current < guard['until']:
                st.error('로그인 시도가 많습니다. 잠시 후 다시 시도하세요.')
            elif verify_password(password, encoded):
                guard['failures'] = []
                st.session_state.admin_hash = encoded
                st.rerun()
            else:
                guard['failures'] = [v for v in guard['failures'] if current-v < 60] + [current]
                if len(guard['failures']) >= 10:
                    guard['until'] = current+60
                st.error('비밀번호가 올바르지 않습니다.')
    return False


def admin():
    st.title('관리자 페이지')
    if not authenticate():
        return
    if not store.persistent_cloud and os.environ.get('ESCAPE_LOCAL') != '1':
        st.warning('현재 SQLite 저장입니다. Streamlit Cloud에서는 재시작·재배포 후 데이터가 사라질 수 있습니다. 운영 배포 전에 DATABASE_URL을 설정하세요.')
    tabs = st.tabs(['문제 관리', '기록 설정·조회', '백업·복원'])
    with tabs[0]:
        qs = store.list_questions()
        st.caption('문제 변경은 새로 시작하는 게임에 반영됩니다. 활성 표시를 끄면 해당 문제가 게임에서 제외됩니다.')
        choices = ['새 문제 추가'] + [f"{i+1}. {q['title']}" for i,q in enumerate(qs)]
        chosen = choices.index(st.selectbox('편집할 문제', choices))
        q = qs[chosen-1] if chosen else {'room':'새 봉인', 'title':'', 'clue':'', 'q':'',
                'options':['','','',''], 'answer':0, 'hint':'', 'explain':'', 'source':'https://', 'active':True}
        with st.form(f"edit_{q.get('id','new')}"):
            room = st.text_input('방 이름', q['room'], max_chars=200)
            title = st.text_input('문제 제목', q['title'], max_chars=200)
            clue = st.text_area('이야기 단서', q['clue'], max_chars=4000)
            question = st.text_area('질문', q['q'], max_chars=4000)
            options = [st.text_input(f'선택지 {i+1}', v, max_chars=500) for i,v in enumerate(q['options'])]
            answer = st.selectbox('정답 번호', [1,2,3,4], index=q['answer'])-1
            hint = st.text_area('힌트', q['hint'], max_chars=4000)
            explain = st.text_area('정답 해설', q['explain'], max_chars=4000)
            source = st.text_input('출처 링크 (http/https)', q['source'], max_chars=2000)
            position = st.number_input('출제 순서 (작은 숫자부터)', min_value=1,
                                       value=int(q.get('position', len(qs)))+1, step=1)
            active = st.checkbox('게임에서 사용', value=q['active'])
            saved = st.form_submit_button('문제 저장', type='primary')
        if saved:
            try:
                store.save_question(dict(q, room=room, title=title, clue=clue, q=question, options=options,
                                         answer=answer, hint=hint, explain=explain, source=source, active=active), position-1)
                st.success('저장했습니다. 목록 갱신 버튼으로 새 목록을 확인하세요.')
            except ValueError as exc:
                st.error(str(exc))
        if chosen:
            confirmed = st.checkbox('선택한 문제를 삭제합니다. 기존 플레이 기록은 유지됩니다.', key=f"delete_{q['id']}")
            if st.button('선택한 문제 삭제', disabled=not confirmed):
                store.delete_question(q['id'])
                st.rerun()
        if st.button('목록 갱신'):
            st.rerun()
    with tabs[1]:
        with st.form('record_setting'):
            enabled = st.checkbox('학습 기록 저장 허용', value=store.recording())
            st.caption('저장을 허용해도 플레이어가 시작 화면에서 동의한 경우에만 저장합니다. 끄면 진행 중인 게임의 추가 기록도 중단합니다.')
            if st.form_submit_button('기록 설정 저장'):
                store.set_recording(enabled)
                st.success('기록 설정을 저장했습니다.')
        runs = store.rows('runs')
        events = store.rows('events')
        a,b,c = st.columns(3)
        a.metric('기록된 플레이', len(runs))
        b.metric('완료된 플레이', sum(bool(r['finished']) for r in runs))
        c.metric('오답 시도', sum(not e['correct'] for e in events))
        st.caption('소요 시간은 초, 시각은 UTC입니다. 미완료 기록도 표시됩니다.')
        st.dataframe(runs, use_container_width=True)
        st.download_button('플레이 요약 CSV', csv_bytes(runs), 'runs.csv', 'text/csv')
        st.dataframe(events, use_container_width=True)
        st.download_button('문제별 시도 CSV', csv_bytes(events), 'attempts.csv', 'text/csv')
    with tabs[2]:
        st.download_button('문제 백업 JSON', store.backup(), 'questions-backup.json', 'application/json')
        st.caption('문제 백업에는 비밀번호·DB 연결정보·학생 기록이 포함되지 않습니다. 기록은 CSV로 별도 내려받으세요.')
        uploaded = st.file_uploader('문제 백업 복원', type=['json'])
        confirm = st.checkbox('현재 문제 목록을 백업 파일의 문제로 교체합니다.')
        if st.button('문제 복원', disabled=uploaded is None or not confirm):
            if uploaded.size > 2_000_000:
                st.error('백업 파일은 2MB 이하만 지원합니다.')
            else:
                try:
                    store.restore_questions(uploaded.getvalue().decode('utf-8-sig'))
                    st.success('복원했습니다. 기록 설정과 기존 학습 기록은 유지됩니다.')
                except (ValueError, KeyError, TypeError) as exc:
                    st.error(f'백업을 확인해 주세요: {exc}')


if page == '방탈출 게임':
    play()
elif page == '관리자 페이지':
    admin()
else:
    st.title('사용 안내')
    st.write('프랑스혁명 기본 문제 10개로 시작합니다. 관리자 페이지에서 수정·추가·삭제 및 출제 여부를 변경할 수 있습니다.')
    st.write('게임 도중 관리자 수정은 현재 게임에 영향을 주지 않습니다. 새 게임을 시작하면 최신 문제를 사용합니다.')
    st.write('학습 기록은 관리자의 저장 허용과 플레이어의 저장 동의가 모두 있을 때만 저장합니다. 실명 대신 모둠명이나 별명을 사용하세요.')
    st.write('웹 배포에서는 퀴즈·관리자·기록 기능을 제공합니다. USB 햄스터 제어는 동글이 연결된 PC에서 게임실행.cmd로 실행합니다.')
    st.write('로컬 관리자: 관리자실행.cmd → 최초 비밀번호 설정 → 관리자 페이지. 로봇 게임은 별도로 게임실행.cmd를 실행합니다.')
    st.caption('햄스터를 평평하고 넓은 바닥에 놓으세요. 정답은 앞뒤 왕복, 오답은 제자리 좌우 회전이며 긴급 정지 버튼을 제공합니다.')
