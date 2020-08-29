import requests_async
from requests.exceptions import ConnectTimeout

import sqlite3
import time
from uuid import uuid4
import asyncio
import re

import key

tasks = {}
return_message_url = 'https://api.telegram.org/bot' + key.token + '/sendMessage'


async def send_request(args):
    while True:
        try:
            await requests_async.post(return_message_url, json=args, timeout=10)
            break
        except ConnectTimeout:
            continue


# update 以及获取用户信息
async def get_updates(update_id):
    text_start = '欢迎使用！我可以定时给你发提醒哦！\n 使用 /help 来查看帮助'
    text_help = '/new - 创建一个新的提醒 \n' \
                '/delete - 删除你不需要的提醒 \n' \
                '/list - 查看已设置的提醒列表 \n' \
                '/pause - 暂停所有提醒 \n' \
                '/restart - 恢复所有提醒 \n'\
                '/empty - 清空所有提醒'
    while True:
        args_update = {'offset': update_id, 'timeout': 60}
        url_update = 'https://api.telegram.org/bot' + key.token + '/getUpdates'
        try:
            async_re_update = requests_async.post(url_update, json=args_update, timeout=70)
            data = (await async_re_update).json()
            print('data:', data)
        except ConnectTimeout:
            continue
        try:
            update_id = data['result'][0]['update_id'] + 1
        except (IndexError, KeyError):
            continue
        # 检查用户需求
        re_str_start = r'/start'
        re_str_help = r'/help'
        re_str_list = r'/list'
        re_str_pause = r'/pause'
        re_str_restart = r'/restart'
        re_str_empty = r'/empty'
        re_str_creat_new = r'(/new)( )?([0-9]+)?( )?(.+)?'
        re_str_delete = r'(/delete)( )?([0-9]+)?( )?(.+)?'
        try:
            text = data['result'][0]['message']['text']
            chat_id = data['result'][0]['message']['from']['id']
            re_start = re.match(re_str_start, text)
            re_help = re.match(re_str_help, text)
            re_list = re.match(re_str_list, text)
            re_pause = re.match(re_str_pause, text)
            re_restart = re.match(re_str_restart, text)
            re_empty = re.match(re_str_empty, text)
            re_creat_new = re.match(re_str_creat_new, text)
            re_delete = re.match(re_str_delete, text)
            if re_start:
                args_start = {'chat_id': chat_id, 'text': text_start}
                asyncio.create_task(send_request(args_start))
            elif re_help:
                args_help = {'chat_id': chat_id, 'text': text_help}
                asyncio.create_task(send_request(args_help))
            elif re_list:
                print('if/list...')
                asyncio.create_task(async_re_list(chat_id))
            elif re_pause:
                asyncio.create_task(empty_and_pause(chat_id, 'pause'))
            elif re_restart:
                asyncio.create_task(restart(chat_id))
            elif re_empty:
                asyncio.create_task(empty_and_pause(chat_id, 'empty'))
            elif re_creat_new:
                print('if /new ...')
                new_args = {'re': re_creat_new, 'chat_id': chat_id}
                asyncio.create_task(new(new_args))
                print('创建new')

            elif re_delete:
                print('if/delete...')
                delete_args = {'re': re_delete, 'chat_id': chat_id}
                asyncio.create_task(delete(delete_args))
                print('创建delete')
        except (IndexError, KeyError):
            pass


# /list
async def async_re_list(chat_id):
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    db_list = list(db.execute('select interval, message from information where '
                              'userid=?', (chat_id,)))

    if not db_list:
        args_list = {'chat_id': chat_id, 'text': '还没有已经设置的提醒哦！'}
        asyncio.create_task(send_request(args_list))
    else:
        print('db_list', db_list)
        list_text = ''
        for list_tuple in db_list:
            list_text = list_text + '间隔时长：' + str(list_tuple[0]) + '， '
            print('tt', list_text)
            list_text = list_text + '提醒信息：' + list_tuple[1] + '\n'
        args_list = {'chat_id': chat_id, 'text': list_text}
        print('args_list:', args_list)
        asyncio.create_task(send_request(args_list))


# /new
async def new(args):
    print('进入new')
    text_new = '没问题！请像这样发送给我：\n /new 60 需要的提醒的信息 \n' \
               '请注意时间间隔的单位是分钟哦！'
    re_ = args['re']
    chat_id = args['chat_id']
    re_groups = re_.groups()
    print(re_groups)
    if not (re_groups[2] and re_groups[4]):
        # 发送用法信息
        args_new = {'chat_id': chat_id, 'text': text_new}
        asyncio.create_task(send_request(args_new))
    else:
        # 存储
        interval = re_groups[2]
        message = re_groups[4]
        db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
        id_ = str(uuid4())
        db.execute('insert into information (id, userid, interval, message, last_wakeup_time)'
                   'values (?, ?, ?, ?, ?)',
                   (id_, chat_id, interval, message, time.time()))
        args_new = {'chat_id': chat_id, 'text': '创建成功！'}
        asyncio.create_task(send_request(args_new))
        task_reminder = asyncio.create_task(timing_reminder(id_))
        tasks[id_] = task_reminder


# /delete
async def delete(args):
    text_delete = '好的！请告诉我要删除哪个提醒，像这样：\n /delete 60 需要删除的提醒的信息'
    re_ = args['re']
    chat_id = args['chat_id']
    re_groups = re_.groups()
    print(re_groups)
    if not (re_groups[2] and re_groups[4]):
        # 发送用法信息
        args_delete = {'chat_id': chat_id, 'text': text_delete}
        asyncio.create_task(send_request(args_delete))
    else:
        # 删除
        db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
        db_list = list(db.execute('select id from information where '
                                  'userid=? and interval=? and message=?',
                                  (chat_id, re_groups[2], re_groups[4])))
        if db_list:
            for db_tuple in db_list:
                id_ = db_tuple[0]
                task_reminder = tasks[id_]
                task_reminder.cancel()
            db.execute('delete from information where userid=? and interval=? and message=?',
                       (chat_id, re_groups[2], re_groups[4]))
            args_delete = {'chat_id': chat_id, 'text': '删除成功！'}
            asyncio.create_task(send_request(args_delete))
        else:
            args_delete = {'chat_id': chat_id, 'text': '不存在该提醒哦！'}
            asyncio.create_task(send_request(args_delete))


# 提醒
async def timing_reminder(id_):
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    information = list(db.execute('select userid, interval, message, last_wakeup_time from information '
                                  'where id=?', (id_,)))[0]
    print('information', information)
    chat_id = information[0]
    interval = information[1]*60
    message = information[2]
    last_wakeup_time = information[3]

    while True:
        list_wake_up_time = list(db.execute('select last_wakeup_time from information where id=?', (id_,)))
        if not list_wake_up_time:
            break
        last_wakeup_time = list_wake_up_time[0][0]
        print(message, 'last time:', time.localtime(last_wakeup_time))
        time_looking = last_wakeup_time + interval
        time_now = time.time()
        time_sleep = time_looking - time_now
        await asyncio.sleep(time_sleep)
        args = {'chat_id': chat_id, 'text': message}
        await asyncio.create_task(send_request(args))
        db.execute('update information set last_wakeup_time=? where id=?', (time.time(), id_))


#  清空和暂停 empty pause
async def empty_and_pause(chat_id, keyword):
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    db_list = list(db.execute('select id from information where userid=?', (chat_id,)))
    for db_tuple in db_list:
        id_ = db_tuple[0]
        task_reminder = tasks[id_]
        task_reminder.cancel()
    if keyword == 'empty':
        db.execute('delete from information where userid=?', (chat_id,))
        args_empty = {'chat_id': chat_id, 'text': '清空成功'}
        asyncio.create_task(send_request(args_empty))
    if keyword == 'pause':
        args_pause = {'chat_id': chat_id, 'text': '已经暂停'}
        asyncio.create_task(send_request(args_pause))


# 重启 restart
async def restart(chat_id):
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    db_list = list(db.execute('select id from information where userid=?', (chat_id,)))
    for db_tuple in db_list:
        id_ = db_tuple[0]
        task_reminder = asyncio.create_task(timing_reminder(id_))
        tasks[id_] = task_reminder


# 程序重启 开启提醒
async def timing_reminder_start():
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    id_list = list(db.execute('select id from information'))
    for id_tuple in id_list:
        id_ = id_tuple[0]
        task_reminder = asyncio.create_task(timing_reminder(id_))
        tasks[id_] = task_reminder


async def main():
    update_id = 387510161
    task_get_updates = asyncio.create_task(get_updates(update_id))
    asyncio.create_task(timing_reminder_start())
    await task_get_updates


asyncio.run(main())
