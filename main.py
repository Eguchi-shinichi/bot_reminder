import requests_async
import requests

import sqlite3
import time
from uuid import uuid4
import asyncio
import re

import key

tasks = {}
return_message_url = 'https://api.telegram.org/bot' + key.token + '/sendMessage'


# update 以及获取用户信息
async def get_updates(update_id):
    text_start = '欢迎使用！我可以定时给你发提醒哦！\n 使用 /help 来查看帮助'
    text_help = '/new - 创建一个新的提醒 \n/delete - 删除你不需要的提醒 \n/list - 查看已设置的提醒列表 \n/empty - 清空所有提醒'
    while True:
        args_update = {'offset': update_id, 'timeout': 60}
        url_update = 'https://api.telegram.org/bot' + key.token + '/getUpdates'
        try:
            async_re_update = requests_async.post(url_update, json=args_update, timeout=70)
            data = (await async_re_update).json()
            print('data:', data)
        except requests.exceptions.ConnectTimeout:
            continue
        try:
            update_id = data['result'][0]['update_id'] + 1
        except (IndexError, KeyError):
            continue
        # 检查用户需求
        re_str_start = r'/start'
        re_str_help = r'/help'
        re_str_list = r'/list'
        re_str_empty = r'/empty'
        re_str_creat_new = r'(/new)( )?([0-9]+)?( )?(.+)?'
        re_str_delete = r'(/delete)( )?([0-9]+)?( )?(.+)?'
        try:
            text = data['result'][0]['message']['text']
            chat_id = data['result'][0]['message']['from']['id']
            re_start = re.match(re_str_start, text)
            re_help = re.match(re_str_help, text)
            re_list = re.match(re_str_list, text)
            re_empty = re.match(re_str_empty, text)
            re_creat_new = re.match(re_str_creat_new, text)
            re_delete = re.match(re_str_delete, text)
            if re_start:
                args_start = {'chat_id': chat_id, 'text': text_start}
                while True:
                    try:
                        await requests_async.post(return_message_url, args_start, timeout=10)
                        break
                    except requests.exceptions.Timeout:
                        continue
            elif re_help:
                args_help = {'chat_id': chat_id, 'text': text_help}
                while True:
                    try:
                        await requests_async.post(return_message_url, args_help, timeout=10)
                        break
                    except requests.exceptions.Timeout:
                        continue
            elif re_list:
                print('if/list...')
                asyncio.create_task(async_re_list(chat_id))
            elif re_empty:
                asyncio.create_task(empty(chat_id))
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
        while True:
            try:
                await requests_async.post(return_message_url, args_list, timeout=10)
                break
            except requests.exceptions.Timeout:
                continue
    else:
        print('db_list', db_list)
        list_text = ''
        for list_tuple in db_list:
            list_text = list_text + '间隔时长：' + str(list_tuple[0]) + '， '
            print('tt', list_text)
            list_text = list_text + '提醒信息：' + list_tuple[1] + '\n'
        args_list = {'chat_id': chat_id, 'text': list_text}
        print('args_list:', args_list)
        while True:
            try:
                await requests_async.post(return_message_url, args_list, timeout=10)
                break
            except requests.exceptions.Timeout:
                continue


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
        while True:
            try:
                await requests_async.post(return_message_url, json=args_new, timeout=10)
                break
            except requests.exceptions.ConnectTimeout:
                continue
    else:
        # 存储
        interval = re_groups[2]
        message = re_groups[4]
        db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
        id_ = str(uuid4())
        db.execute('insert into information (id, userid, interval, message)'
                   'values (?, ?, ?, ?)',
                   (id_, chat_id, interval, message))
        args_new = {'chat_id': chat_id, 'text': '创建成功！'}
        while True:
            try:
                await requests_async.post(return_message_url, json=args_new, timeout=10)
                break
            except requests.exceptions.ConnectTimeout:
                continue
        task_reminder = asyncio.create_task(
            timing_reminder({'chat_id': chat_id, 'interval': interval, 'message': message}))
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
        while True:
            try:
                await requests_async.post(return_message_url, json=args_delete, timeout=10)
                break
            except requests.exceptions.ConnectTimeout:
                continue
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
            while True:
                try:
                    await requests_async.post(return_message_url, json=args_delete, timeout=10)
                    break
                except requests.exceptions.ConnectTimeout:
                    continue
        else:
            args_delete = {'chat_id': chat_id, 'text': '不存在该提醒哦！'}
            while True:
                try:
                    await requests_async.post(return_message_url, json=args_delete, timeout=10)
                    break
                except requests.exceptions.ConnectTimeout:
                    continue


# 提醒
async def timing_reminder(args):
    chat_id = args['chat_id']
    interval = int(args['interval']) * 60
    message = args['message']
    while True:
        time_now = time.time()
        time_looking = time_now + interval
        await asyncio.sleep(interval)

        args = {'chat_id': chat_id, 'text': message}
        while True:
            try:
                await requests_async.post(return_message_url, json=args, timeout=10)
                break
            except requests.exceptions.ConnectTimeout:
                pass

        time_now = time.time()
        time_lag = time_looking - time_now
        interval = interval + time_lag


# 提醒 start
async def timing_reminder_start():
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    db_list = list(db.execute('select userid, interval, message, id from information'))
    for db_tuple in db_list:
        args = {'chat_id': db_tuple[0], 'interval': db_tuple[1], 'message': db_tuple[2]}
        task_reminder = asyncio.create_task(timing_reminder(args))
        tasks[db_tuple[3]] = task_reminder


# empty
async def empty(chat_id):
    db = sqlite3.connect('定时提醒.db', isolation_level=None).cursor()
    db_list = list(db.execute('select id from information where userid=?', (chat_id,)))
    for db_tuple in db_list:
        id_ = db_tuple[0]
        task_reminder = tasks[id_]
        task_reminder.cancel()
    db.execute('delete from information where userid=?', (chat_id,))
    args_empty = {'chat_id': chat_id, 'text': '清空成功'}
    while True:
        try:
            await requests_async.post(return_message_url, json=args_empty, timeout=10)
            break
        except requests.exceptions.ConnectTimeout:
            continue


async def main():
    update_id = 387510161
    task_get_updates = asyncio.create_task(get_updates(update_id))
    asyncio.create_task(timing_reminder_start())
    await task_get_updates


asyncio.run(main())
