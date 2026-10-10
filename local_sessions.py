import threading
import time
import uuid
from game import new_game, submit, advance


class Sessions:
    def __init__(self, store):
        self.store = store
        self.games = {}
        self.lock = threading.Lock()

    def start(self, team, opt_in):
        if not isinstance(team, str) or len(team) > 80 or type(opt_in) is not bool:
            raise ValueError('모둠명과 기록 동의를 확인하세요.')
        with self.lock:
            cutoff = time.monotonic() - 14400
            self.games = {k:g for k,g in self.games.items() if g['started'] > cutoff}
            if len(self.games) >= 100:
                raise ValueError('실행 중인 게임이 많습니다. 서버를 다시 시작해 주세요.')
            game = new_game(self.store, team, opt_in)
            sid = str(uuid.uuid4())
            self.games[sid] = game
            questions = [{k:v for k,v in q.items() if k not in ('answer', 'explain')} for q in game['questions']]
            return {'session':sid, 'questions':questions, 'recording':bool(game['run_id'])}

    def action(self, sid, choice=None, next_question=False, hint=False):
        with self.lock:
            if not isinstance(sid, str) or sid not in self.games:
                raise ValueError('게임 세션이 만료되었습니다. 다시 시작해 주세요.')
            game = self.games[sid]
            if hint:
                game['hint'] = True
                return {'ok':True}
            if next_question:
                advance(game)
                return {'complete':game['complete'], 'index':game['index']}
            correct = submit(game, self.store, choice)
            q = game['questions'][game['index']]
            return {'correct':correct, 'explain':q['explain'] if correct else '',
                    'source':q['source'], 'record_error':game['record_error']}
