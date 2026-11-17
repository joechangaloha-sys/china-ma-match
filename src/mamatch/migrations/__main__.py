import argparse
from .. import db
from . import check, head, upgrade

p=argparse.ArgumentParser(description='Reviewed database migration commands')
p.add_argument('command',choices=['check','upgrade'])
p.add_argument('--adopt-existing',action='store_true',help='Validate and adopt the exact frozen baseline; refuses partial schemas')
a=p.parse_args()
if a.command=='upgrade':upgrade(db.get_engine(),adopt_existing=a.adopt_existing)
else:check(db.get_engine())
print('Schema ready at '+head())
