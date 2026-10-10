import json
import threading
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import pytest
from bridge import Handler, Controller
from local_sessions import Sessions
from store import Store


def test_http_local_security_and_game(tmp_path):
    Handler.controller = Controller(None)
    Handler.sessions = Sessions(Store('sqlite:///'+(tmp_path/'bridge.db').as_posix()))
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(Path(__file__).parents[1]/'dist')))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with urlopen(base+'/') as r:
            assert r.status==200 and '프랑스혁명'.encode() in r.read()
        bad=Request(base+'/api/config',headers={'Origin':'https://attacker.invalid'})
        with pytest.raises(HTTPError) as e:
            urlopen(bad)
        assert e.value.code==403
        request=Request(base+'/api/start',data=json.dumps({'team':'','opt_in':False}).encode(),
                        headers={'Content-Type':'application/json'})
        with urlopen(request) as r:
            data=json.load(r)
        assert len(data['questions'])==10
        assert 'answer' not in data['questions'][0]
        request=Request(base+'/api/answer',data=json.dumps({'session':data['session'],'choice':1}).encode(),
                        headers={'Content-Type':'application/json'})
        with urlopen(request) as r:
            assert json.load(r)['correct']
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_robot_stop_and_duplicate():
    class Robot:
        def __init__(self): self.moves=[];self.colors=[]
        def is_connected(self): return True
        def wheels(self,*args): self.moves.append(args)
        def leds(self,*args): self.colors.append(args)
    r=Robot();c=Controller(r)
    c.feedback(True)
    assert (2,2) in r.colors and (20,20) in r.moves and (-20,-20) in r.moves
    assert r.moves[-1]==(0,0) and r.colors[-1]==(0,0)
    c.busy.acquire()
    with pytest.raises(RuntimeError): c.feedback(False)
    c.busy.release()
    t=threading.Thread(target=c.feedback,args=(False,));t.start()
    import time
    time.sleep(.05);c.stop();t.join(1)
    assert not t.is_alive() and (4,4) in r.colors
    assert r.moves[-1]==(0,0) and r.colors[-1]==(0,0)
