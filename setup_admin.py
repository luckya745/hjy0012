import argparse
import getpass
from pathlib import Path
from security import hash_password

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--hash-only', action='store_true')
    args = parser.parse_args()
    password = getpass.getpass('New administrator password (12+ characters): ')
    if password != getpass.getpass('Repeat password: '):
        raise SystemExit('Passwords do not match.')
    encoded = hash_password(password)
    if args.hash_only:
        print('ADMIN_PASSWORD_HASH = "' + encoded + '"')
    else:
        target = Path(__file__).parent / '.streamlit' / 'secrets.toml'
        if target.exists():
            raise SystemExit('secrets.toml already exists; preserve existing database settings.')
        target.parent.mkdir(exist_ok=True)
        target.write_text('ADMIN_PASSWORD_HASH = "' + encoded + '"\n', encoding='utf-8')
        print('Administrator configured. Start the app again.')
