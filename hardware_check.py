"""Interactive physical check using the game's actual Controller."""
import json
import time
from datetime import datetime
from pathlib import Path
from roboid import Hamster
from bridge import Controller


def main():
    results = []
    robot = None
    control = None
    try:
        port = input('동글 COM 포트 [COM5]: ').strip() or 'COM5'
        print('햄스터 전원을 켜고 다른 로봇 프로그램을 종료해 주세요.')
        robot = Hamster(port_name=port)
        control = Controller(robot)
        deadline = time.monotonic() + 10
        while not control.connected() and time.monotonic() < deadline:
            time.sleep(.1)
        if not control.connected():
            print('연결 실패. 포트 사용 프로그램, 동글, 로봇 전원 및 페어링을 확인하세요.')
            return
        control.stop()
        print('햄스터 연결 확인 완료. Ctrl+C로 중단할 수 있습니다.')
        print('앞쪽 양쪽 LED를 확인하세요. 상단 충전/블루투스 표시등은 시험 대상이 아닙니다.')
        for name, color in [('빨강', 4), ('초록', 2)]:
            input(f'Enter: {name} LED만 켜기 (바퀴는 정지)')
            try:
                robot.leds(color, color)
                time.sleep(2)
                observed = input(f'양쪽 앞 LED가 {name}으로 켜졌나요? [y/n]: ').strip().lower()
                results.append({'test': name + ' LED', 'observed_pass': observed == 'y'})
            finally:
                control.stop()
        print('바퀴 시험 전에 햄스터를 넓고 평평한 바닥에 놓으세요.')
        for name, correct in [('오답: 빨강 LED + 좌우 제자리 회전', False), ('정답: 초록 LED + 앞뒤 이동', True)]:
            input('Enter: ' + name + ' 시험 시작')
            control.feedback(correct)
            observed = input('색상과 움직임이 설명과 같았고 마지막에 정지했나요? [y/n]: ').strip().lower()
            results.append({'test': name, 'observed_pass': observed == 'y'})
        print('시험 완료. 아래 기록은 사용자가 관찰한 결과입니다.')
        print(json.dumps(results, ensure_ascii=False, indent=2))
    except KeyboardInterrupt:
        print('\n시험 중단. 정지 명령을 보냅니다.')
    except Exception as exc:
        results.append({'error': str(exc)})
        print('시험 오류:', exc)
    finally:
        if control:
            control.stop()
        if robot:
            robot.dispose()
        report = {'checked_at': datetime.now().astimezone().isoformat(), 'results': results}
        target = Path(__file__).with_name('hardware_check_result.json')
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print('결과 파일:', target)


if __name__ == '__main__':
    main()
