import time
import uuid


def new_game(store, team='', opt_in=False):
    questions = store.list_questions(active_only=True)
    if not questions:
        raise ValueError('사용할 문제가 없습니다. 관리자에게 문의하세요.')
    return {'questions': questions, 'index': 0, 'attempts': 0, 'solved': False,
            'started': time.monotonic(), 'question_started': time.monotonic(),
            'hint': False, 'message': '', 'run_id': store.start_run(team, len(questions), opt_in),
            'record_error': False, 'complete': False, 'game_id': str(uuid.uuid4()),
            'first_correct': 0, 'question_attempts': 0, 'hall_registered': False}


def submit(game, store, choice):
    if game['complete'] or game['solved']:
        raise ValueError('이미 해결한 문제입니다.')
    if type(choice) is not int or not 0 <= choice < 4:
        raise ValueError('선택지 번호가 잘못되었습니다.')
    q = game['questions'][game['index']]
    correct = choice == q['answer']
    if game['question_attempts'] == 0 and correct:
        game['first_correct'] += 1
    game['question_attempts'] += 1
    game['attempts'] += 1
    game['solved'] = correct
    completed = correct and game['index'] == len(game['questions']) - 1
    try:
        store.record(game['run_id'], q, choice, correct, game['hint'],
                     time.monotonic() - game['question_started'], game['index'] + int(correct),
                     time.monotonic() - game['started'], completed)
    except Exception:
        game['record_error'] = True
    game['message'] = q['explain'] if correct else '아직 봉인이 풀리지 않았습니다. 단서를 읽고 다시 도전하세요.'
    return correct


def advance(game):
    if not game['solved']:
        raise ValueError('먼저 문제를 해결하세요.')
    if game['index'] == len(game['questions']) - 1:
        game['complete'] = True
        game['elapsed'] = time.monotonic() - game['started']
    else:
        game.update(index=game['index'] + 1, solved=False, hint=False, message='',
                    question_started=time.monotonic(), question_attempts=0)


def score(game):
    return round(100 * game['first_correct'] / len(game['questions']), 1)


def hall_eligible(game):
    return (game['complete'] and game['first_correct'] == len(game['questions'])
            and game['attempts'] == len(game['questions']))


def register_hall(game, store, name, consent):
    if not hall_eligible(game):
        raise ValueError('모든 문제를 첫 시도에 맞히고 탈출한 100점 학습자만 등록할 수 있습니다.')
    if consent is not True:
        raise ValueError('명예의 전당 이름 공개 및 저장에 동의해 주세요.')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 40 or any(ord(c) < 32 for c in name):
        raise ValueError('이름 또는 별명을 1~40자로 입력해 주세요.')
    store.add_hall(game['game_id'], name.strip(), len(game['questions']), game['elapsed'])
    game['hall_registered'] = True
