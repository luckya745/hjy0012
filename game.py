import time


def new_game(store, team='', opt_in=False):
    questions = store.list_questions(active_only=True)
    if not questions:
        raise ValueError('사용할 문제가 없습니다. 관리자에게 문의하세요.')
    return {'questions': questions, 'index': 0, 'attempts': 0, 'solved': False,
            'started': time.monotonic(), 'question_started': time.monotonic(),
            'hint': False, 'message': '', 'run_id': store.start_run(team, len(questions), opt_in),
            'record_error': False, 'complete': False}


def submit(game, store, choice):
    if game['complete'] or game['solved']:
        raise ValueError('이미 해결한 문제입니다.')
    if type(choice) is not int or not 0 <= choice < 4:
        raise ValueError('선택지 번호가 잘못되었습니다.')
    q = game['questions'][game['index']]
    correct = choice == q['answer']
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
    else:
        game.update(index=game['index'] + 1, solved=False, hint=False, message='',
                    question_started=time.monotonic())
