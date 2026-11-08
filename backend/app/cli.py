import argparse
import secrets
import json
from alembic.config import Config
from alembic import command
from app.config import ROOT
from app.db import Session
from app.db.models import User
from app.api.auth import hash_password
from app.domain.ingest import import_folder

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('command',choices=['migrate','seed-users','import-dataset']); parser.add_argument('--path'); args=parser.parse_args()
    if args.command=='migrate':
        config=Config(str(ROOT/'backend'/'alembic.ini')); command.upgrade(config,'head'); print('Schema migrated')
    elif args.command=='seed-users':
        with Session.begin() as db:
            for role in ('supervisor','operator','judge'):
                if db.get(User,role): continue
                password=secrets.token_urlsafe(15)
                db.add(User(id=role,role=role,password_hash=hash_password(password)))
                print(f'{role}: {password}')
        print('Save generated credentials locally. Existing users were preserved.')
    else:
        if not args.path: parser.error('--path required')
        with Session.begin() as db: print(json.dumps(import_folder(db,args.path),indent=2))

if __name__=='__main__': main()
