# 프랑스혁명 · 자유의 열쇠

한국어 프랑스혁명 방탈출 학습 게임입니다. 기본 10문제를 제공하며, 교사는 관리자 페이지에서 문제·정답·선택지·힌트·해설·출처·순서·출제 여부를 수정하고 문제를 추가·삭제할 수 있습니다.

## 기능

- 힌트, 오답 재도전, 정답 해설·출처, 진행률, 완료 화면, 재시작
- 관리자 비밀번호 로그인(PBKDF2 해시), 로그아웃, 로그인 시도 제한
- 기록 저장 허용 설정 + 플레이어별 동의: 모둠명/별명, 시도, 힌트 사용, 소요 시간, 완료 여부
- 관리자 전용 결과 조회, 플레이 요약 CSV, 문제별 시도 CSV
- 문제 JSON 백업·복원; 진행 중 게임은 시작 당시 문제를 유지
- 로컬 SQLite와 외부 PostgreSQL 지원
- 일반 Hamster 로컬 연동: 연결 확인, LED·바퀴 반응, 긴급·자동 정지

## Windows PC 실행

Python **3.11 이상**이 필요합니다. 설치 시 PATH 옵션을 켜세요.

1. 저장소 ZIP을 내려받아 압축을 해제합니다.
2. `관리자실행.cmd` 실행: 처음에는 필요한 패키지를 설치하고 12자 이상의 관리자 비밀번호를 설정합니다.
3. 열린 Streamlit 페이지의 **관리자 페이지**에서 로그인합니다.
4. 로봇 없이 Streamlit의 **방탈출 게임**을 바로 사용할 수 있습니다.
5. 실제 햄스터는 동글을 꽂고 전원을 켠 다음 별도로 `게임실행.cmd`를 실행합니다. 실행 창의 주소(기본 8877)를 열어 **햄스터 연결**을 누릅니다.

두 로컬 앱은 같은 `data/escape.db`를 사용합니다. 관리자 변경은 새 게임에 반영됩니다. 포트가 이미 사용 중이면 햄스터 서버는 다음 빈 포트를 선택합니다. Streamlit은 기본 8501을 사용합니다.

명령으로 실행하려면:

```bash
python -m pip install -r requirements-local.txt
python setup_admin.py
python -m streamlit run streamlit_app.py --server.address 127.0.0.1
# 다른 터미널에서 로봇 게임 실행
python bridge.py
```

`미리보기.html`은 기존 10문제의 독립 체험 페이지이며 관리자 변경·DB 저장·실물 연결을 제공하지 않습니다.

## GitHub → Streamlit Community Cloud 배포

저장소: https://github.com/luckya745/hjy0012

1. https://share.streamlit.io 에 GitHub로 로그인합니다.
2. Create app → Repository `luckya745/hjy0012` → Branch `main` → Main file path `streamlit_app.py`.
3. Advanced settings에서 Python 3.12를 선택하고 Secrets를 설정합니다.
4. 관리자 해시는 로컬에서 `python setup_admin.py --hash-only`를 실행하여 생성합니다. 비밀번호는 화면에 표시하거나 저장소에 올리지 않습니다.
5. 아래 두 설정을 Secrets에 넣고 배포합니다.

```toml
ADMIN_PASSWORD_HASH = "생성한 PBKDF2 해시"
DATABASE_URL = "postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require"
```

실제 값은 GitHub에 커밋하지 마세요. `secrets.example.toml`은 설정 예시입니다. 외부 DB는 사용자가 소유한 PostgreSQL(Supabase/Neon 등)의 TLS 연결 URL을 사용하며, 이 앱 전용 DB를 권장합니다. 처음 실행 때 기본 문제를 한 번 넣습니다. 기존 문제가 있으면 재시작 시 덮어쓰지 않습니다.

**Cloud에서 SQLite 파일은 영구 보관이 보장되지 않습니다.** DATABASE_URL 없이도 체험은 가능하지만 문제 수정과 기록을 유지하려면 외부 DB를 연결해야 합니다. 연결 실패 시 앱을 중단하여 다른 임시 저장소로 기록을 흘리지 않습니다.

클라우드 앱은 사용자의 PC USB에 직접 접근하지 않습니다. 실물 햄스터 제어는 로컬 `bridge.py` 서버에서 제공합니다. 클라우드와 로컬에 같은 DATABASE_URL을 설정하면 문제와 기록을 공유할 수 있습니다. 교실 PC에서는 관리자와 로봇 앱을 둘 다 로컬로 실행하는 구성이 간단합니다.

## 기록과 백업

기본값은 **저장 꺼짐**입니다. 관리자가 저장을 허용하고 참가자가 시작 때 동의한 경우에만 기록합니다. 실명 대신 별명을 사용하세요. 기록은 GitHub에 올리지 않으며 CSV는 관리자만 내려받을 수 있습니다. CSV의 텍스트 값에는 스프레드시트 수식 실행 방지 처리를 적용합니다.

진행 중 브라우저를 닫으면 그때까지의 시도는 남으며 미완료로 표시됩니다. 게임 세션은 브라우저 새로고침 후 이어서 복구하지 않습니다. 기록 저장을 도중에 끄면 이후 시도는 저장하지 않습니다. 기록 시간은 UTC, 소요 시간은 초입니다. 마지막 문제를 정답으로 풀면 기록은 완료로 표시됩니다.

문제 백업에는 질문·정답·힌트·해설·출처·활성 여부만 들어갑니다. 복원은 문제 목록만 교체하고 기록·기록 설정을 유지합니다. 로컬 전체 보관은 서버를 끈 뒤 `data/`를 별도로 복사하세요. Cloud 전체 보관은 DB 제공업체의 백업 기능을 사용하세요.

## 햄스터 주의사항

일반 Hamster용이며 Hamster S API를 사용하지 않습니다. 충전 케이블과 전용 USB 무선 동글은 다릅니다. 다른 로봇 프로그램을 종료하고 넓고 평평한 바닥에 두세요. 정답: 앞쪽 LED 초록(2), 속도 20 앞뒤 두 번 왕복. 오답: 빨강(4), 속도 18 제자리 좌우 회전 두 번. 각 구간은 0.3초이며 종료·오류 시 바퀴와 LED를 끕니다. USB 실물 동작은 자동 테스트만으로 확인할 수 없습니다.

## 검증

```bash
python -m pip install pytest
python -m pytest tests -q
```

기본 문제 출처는 `questions.json`과 정답 해설의 링크에 포함했습니다. 베르사유 궁전, 프랑스 대통령실 인권선언, 프랑스 국립도서관, 미국 의회도서관 등을 참고했습니다. 단서는 게임용 문장으로 직접 인용이 아닙니다.

Streamlit 공식 안내: [배포](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy), [Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management), [저장소의 지속성](https://docs.streamlit.io/develop/concepts/connections/connecting-to-data).
