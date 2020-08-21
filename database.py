import sqlite3


db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
db.execute('create table information (id text primary key, '
           'userid text, '
           'interval int, '
           'message text, '
           'last_wakeup_time real)')

