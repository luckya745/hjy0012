"""Local-only Hamster bridge. Run: py bridge.py [--demo] [--port COM3]."""
import argparse
import json
import threading
import time
import webbrowser
import signal
import sys
import os
import tomllib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def initialize_robot_library():
    """roboid registers SIGINT on import, which must happen on the main thread."""
    previous = signal.getsignal(signal.SIGINT)
    try:
        import roboid
        return True
    except ImportError:
        return False
    finally:
        signal.signal(signal.SIGINT, previous)


class Controller:
    def __init__(self, robot, port=None):
        self.robot = robot
        self.port = port
        self.connection_lock = threading.Lock()
        self.cancel = threading.Event()
        self.busy = threading.Lock()
        self.hardware = threading.Lock()

    def connected(self):
        return self.robot is not None and self.robot.is_connected()

    def connect(self):
        if not self.connection_lock.acquire(blocking=False):
            raise RuntimeError('연결 시도가 진행 중입니다. 잠시 기다려 주세요.')
        try:
            if self.connected():
                return
            if self.robot:
                self.stop()
                self.robot.dispose()
                self.robot = None
            try:
                if 'roboid' not in sys.modules:
                    raise ImportError('Library was not initialized on the main thread')
                from roboid import Hamster
                import serial
                from serial.tools import list_ports
            except ImportError:
                raise RuntimeError('연결 라이브러리가 없습니다. 게임실행.cmd로 실행해 주세요.')
            ports = [self.port] if self.port else [p.device for p in list_ports.comports() if p.vid == 0x10C4 and p.pid == 0xEA60]
            if not ports:
                raise RuntimeError('햄스터 USB 동글을 찾지 못했습니다. USB 연결과 드라이버를 확인하세요.')
            # Expose access errors which the robot library otherwise suppresses.
            port = ports[0]
            try:
                with serial.Serial(port, 115200, rtscts=True, timeout=.1):
                    pass
            except serial.SerialException:
                raise RuntimeError(f'{port}를 열 수 없습니다. 다른 로봇 프로그램을 종료하고 Windows에서 게임실행.cmd를 직접 실행해 주세요.')
            self.robot = Hamster(port_name=port)
            deadline = time.monotonic() + 5
            while not self.connected() and time.monotonic() < deadline:
                time.sleep(.1)
            if not self.connected():
                raise RuntimeError('동글은 감지됐지만 햄스터가 응답하지 않습니다. 로봇 전원과 페어링을 확인하세요.')
            self.port = port
            self.stop()
        finally:
            self.connection_lock.release()

    def stop(self):
        self.cancel.set()
        with self.hardware:
            if self.robot:
                self.robot.wheels(0, 0)
                self.robot.leds(0, 0)

    def feedback(self, correct):
        if not self.connected():
            raise RuntimeError('햄스터가 연결되지 않았습니다. 전원과 USB 동글을 확인하세요.')
        if not self.busy.acquire(blocking=False):
            raise RuntimeError('로봇 반응이 진행 중입니다.')
        self.cancel.clear()
        try:
            with self.hardware:
                self.robot.leds(2 if correct else 4, 2 if correct else 4)
            # Fixed short movement, no command can prolong the motion.
            sequence = [(20, 20), (-20, -20)] if correct else [(-18, 18), (18, -18)]
            for left, right in sequence * 2:
                with self.hardware:
                    if self.cancel.is_set() or not self.connected():
                        break
                    self.robot.wheels(left, right)
                if self.cancel.wait(0.3):
                    break
                with self.hardware:
                    self.robot.wheels(0, 0)
                if self.cancel.wait(0.1):
                    break
        finally:
            self.stop()
            self.busy.release()


class Handler(SimpleHTTPRequestHandler):
    controller = None
    sessions = None

    def trusted(self):
        origin = self.headers.get('Origin')
        port = self.server.server_address[1]
        hosts = (f'127.0.0.1:{port}', f'localhost:{port}')
        return self.headers.get('Host') in hosts and (
            origin is None or origin in tuple('http://' + host for host in hosts))

    def reply(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        if not self.trusted():
            return self.reply(403, {'error': '로컬 페이지에서만 사용 가능합니다.'})
        if self.path == '/api/status':
            return self.reply(200, {'connected': self.controller.connected()})
        if self.path == '/api/config':
            return self.reply(200, {'recording': self.sessions.store.recording()})
        super().do_GET()

    def do_POST(self):
        if not self.trusted():
            return self.reply(403, {'error': '허용되지 않은 요청입니다.'})
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length < 0 or length > 2048:
                raise ValueError('요청 크기 오류')
            data = json.loads(self.rfile.read(length) or b'{}')
            if not isinstance(data, dict):
                raise ValueError('요청 형식 오류')
            if self.path == '/api/start':
                return self.reply(200, self.sessions.start(data.get('team', ''), data.get('opt_in', False)))
            if self.path in ('/api/answer', '/api/advance', '/api/hint'):
                return self.reply(200, self.sessions.action(data.get('session'), data.get('choice'),
                    next_question=self.path == '/api/advance', hint=self.path == '/api/hint'))
            if self.path == '/api/connect':
                self.controller.connect()
                return self.reply(200, {'connected': self.controller.connected(), 'port': self.controller.port})
            elif self.path == '/api/stop':
                self.controller.stop()
            elif self.path == '/api/feedback' and type(data.get('correct')) is bool:
                self.controller.feedback(data['correct'])
            else:
                return self.reply(400, {'error': '올바르지 않은 명령입니다.'})
            self.reply(200, {'ok': True})
        except (ValueError, RuntimeError) as exc:
            self.reply(409, {'error': str(exc)})
        except Exception as exc:
            self.controller.stop()
            self.reply(500, {'error': '교구 통신 오류: ' + str(exc)})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--demo', action='store_true', help='로봇 없이 웹페이지 실행')
    parser.add_argument('--no-browser', action='store_true', help='브라우저 자동 열기 생략')
    parser.add_argument('--port', help='동글의 COM 포트, 예: COM3')
    parser.add_argument('--web-port', type=int, default=8877, help='웹페이지 포트 (기본 8877)')
    args = parser.parse_args()
    from store import Store
    from local_sessions import Sessions
    secrets_path = Path(__file__).parent / '.streamlit' / 'secrets.toml'
    settings = tomllib.loads(secrets_path.read_text(encoding='utf-8')) if secrets_path.exists() else {}
    Handler.sessions = Sessions(Store(os.environ.get('DATABASE_URL') or settings.get('DATABASE_URL')))
    initialize_robot_library()
    controller = Controller(None, args.port)
    Handler.controller = controller
    server = None
    for web_port in range(args.web_port, args.web_port + 10):
        try:
            server = ThreadingHTTPServer(('127.0.0.1', web_port), partial(Handler, directory=str(Path(__file__).parent / 'dist')))
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError('웹 서버를 시작할 수 없습니다. 실행 창의 오류를 확인하세요.')
    url = f'http://127.0.0.1:{server.server_address[1]}'
    print('게임 서버 실행 완료: ' + url + ' / 종료: Ctrl+C', flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        server.server_close()
        if controller.robot:
            controller.robot.dispose()


if __name__ == '__main__':
    main()
