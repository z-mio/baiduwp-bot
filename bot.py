# -*- coding: UTF-8 -*-
import asyncio
import concurrent.futures
import datetime
import functools
import logging
import math
import os
import re
from typing import Dict

import httpx
from pyrogram import Client, filters
from pyrogram.types import BotCommand, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

#########################################
# bot

api_id = ''  # 在 https://my.telegram.org/apps 获取

api_hash = ''  # 在 https://my.telegram.org/apps 获取

bot_token = ''  # 在 https://t.me/BotFather 获取

members = [123456789, 987654321]  # 允许使用解析的 用户、群组、频道（群组和频道id需要加上-100）可通过 https://t.me/getletbot 获取id

baidu_url = ''  # 你的百度解析地址

baidu_password = ''  # 解析密码(不是后台密码)
#########################################
# 代理支持“socks4”、“socks5”和“http”
scheme = ''  # 'http'
hostname = ''  # '127.0.0.1'
port = 7890  # 7890
#########################################
logging.basicConfig(
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ],
    format='%(asctime)s - %(name)s - %(levelname)s: %(message)s',
    level=logging.ERROR
)

baidu_url = baidu_url.rstrip('/')
baidu_password = baidu_password.rstrip('/')
proxy = {"scheme": scheme, "hostname": hostname, "port": port}

app = Client(
    "my_bot", bot_token=bot_token, api_id=api_id, api_hash=api_hash,
    proxy=proxy if all([scheme, hostname, port]) else None,
)


def output_error():
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(client, message: Message, *args, **kw):
            try:
                return await func(client, message, *args, **kw)
            except Exception as e:
                logging.error(
                    f"错误:聊天id：{message.chat.id}-用户id：{message.from_user.id}-用户名：@{message.from_user.username}-用户昵称：{message.from_user.first_name}-{e}")
                m = message.message if isinstance(message, CallbackQuery) else message
                return await m.reply(f"错误:{e}")
        
        return wrapper
    
    return decorator


# 设置菜单
@app.on_message(filters.command('menu') & filters.private)
async def menu(_, message: Message):
    await app.set_bot_commands([BotCommand(command="bd", description="百度网盘解析")])
    await app.send_message(chat_id=message.chat.id, text="菜单设置成功，请退出聊天界面重新进入来刷新菜单")


# 构建菜单
def build_menu(root_list):
    text = f"""目录：{f"`{root_list['dirdata']['src'][-1]['fullsrc']}`" if root_list['dirdata']['src'] else '`/`'}
数量：{root_list['filenum']}
"""
    button = [
        [InlineKeyboardButton(
            text=f"{i + 1}.{'📁' if v['isdir'] else formats.get(os.path.splitext(v['name'])[1], '📄')}{v['name']}",
            callback_data=f'bd_{i}' if v['isdir'] else f"bdf_{i}"
        )] for i, v in enumerate(root_list['filedata'])
    ]
    but = [
        InlineKeyboardButton('🔙返回上级', callback_data='bd_rt'),
        InlineKeyboardButton('❌关闭菜单', callback_data='bdexit')
    ]
    but_all_dl = [
        InlineKeyboardButton('🌐获取本页所有文件下载链接', callback_data='bdAll_dl')
    ]
    if [v for v in root_list['filedata'] if not v['isdir']]:
        button.insert(0, but_all_dl)
    button.insert(0, but)
    if root_list['filedata'][7:]:
        button.append(but)
    return text, button


@app.on_message(filters.command('bd'))
async def baidu_jx(_, message: Message):
    if message.chat.id not in members:
        return
    mid = f'{message.chat.id}_{message.id + 1}'
    parameter = ' '.join(message.command[1:])
    parameter = parameter or (message.reply_to_message.text if message.reply_to_message else None)
    baidu = Baidu()
    parse_count = await baidu.parse_count()
    last_parse = await baidu.last_parse()
    text = f"""
{parse_count}

{last_parse}

请加上分享链接，链接格式随意，例：
`/bd 链接: https://pan.baidu.com/s/1w9GGad_-wkipeRVtnxdZiQ?pwd=qysn 提取码: qysn 复制这段内容后打开百度网盘手机App，操作更方便哦`
"""
    if not parameter:
        return await message.reply(text)
    msg = await message.reply('解析中...', quote=True)
    
    def extract_link_and_password(txt: str):
        formatted_links = re.search(r'/s/(\S+)', txt)[1].split('?')[0]  # 匹配/s/后面的码
        password_pattern = r"(?<=\bpwd=)[a-zA-Z0-9]+|\b[a-zA-Z0-9]{4}\b(?!\.)"  # 匹配密码
        passwords = re.findall(password_pattern, txt.replace(formatted_links, ''))
        password = passwords[0] if passwords else None
        return formatted_links, password
    
    try:
        surl, pwd = extract_link_and_password(parameter)
        
        root_list = await baidu.get_root_list(surl, pwd)
        if root_list['error']:
            return await msg.edit_text(root_list['msg'])
        chat_data[f'bd_rlist_{mid}'] = root_list
        text, button = build_menu(root_list)
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(button))
    except Exception as e:
        await msg.edit_text(f'错误：{e}')


@app.on_callback_query(filters.regex(r'^bd_'))
@output_error()
async def baidu_list(_, query: CallbackQuery):
    mid = f'{query.message.chat.id}_{query.message.id}'
    rlist = chat_data[f'bd_rlist_{mid}']
    baidu = Baidu(rlist)
    
    num = query.data.split('_')[1]
    surl = rlist['dirdata']['surl']
    pwd = rlist['dirdata']['pwd']
    # 普通返回，如果目录为一级目录，就返回根目录，否则返回上一层目录
    if query.data == 'bd_rt':
        if len(rlist['dirdata']['src']) == 1:
            dir_list = await baidu.get_root_list(surl, pwd)
        else:
            _dir = rlist['dirdata']['src'][-2]['fullsrc']
            dir_list = await baidu.get_list(dir=_dir)
    # 下载返回，返回当前目录
    elif query.data == 'bd_dl_rt':
        if rlist['dirdata']['src']:
            _dir = rlist['dirdata']['src'][-1]['fullsrc']
            dir_list = await baidu.get_list(dir=_dir)
        else:
            dir_list = await baidu.get_root_list(surl, pwd)
    else:
        _dir = rlist['filedata'][int(num)]['path']
        dir_list = await baidu.get_list(dir=_dir)
    
    chat_data[f'bd_rlist_{mid}'] = dir_list
    text, button = build_menu(dir_list)
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(button))


@app.on_callback_query(filters.regex(r'^bdf_'))
@output_error()
async def baidu_file(_, query: CallbackQuery):
    mid = f'{query.message.chat.id}_{query.message.id}'
    rlist = chat_data[f'bd_rlist_{mid}']
    num = query.data.split('_')[1]
    fs_id = rlist['filedata'][int(num)]['fs_id']
    
    baidu = Baidu(rlist)
    dir_list = await baidu.get_dlurl(fs_id=fs_id)
    text = f"""
路径：`{dir_list['filedata']['path']}`

文件名称：`{dir_list['filedata']['filename']}`
文件大小：`{pybyte(dir_list['filedata']['size'])}`
MD5：`{dir_list['filedata']['md5']}`
上传时间：`{datetime.datetime.fromtimestamp(int(dir_list['filedata']['uploadtime']))}`
User-Agent：`{dir_list['user_agent']}`

**>>>[点击查看下载教程](https://telegra.ph/%E4%B8%8B%E8%BD%BD%E6%8F%90%E7%A4%BA-07-13)<<<**
"""
    button = [
        [
            InlineKeyboardButton('💾下载文件', url=dir_list['directlink']),
            InlineKeyboardButton('📖查看下载教程', url='https://telegra.ph/%E4%B8%8B%E8%BD%BD%E6%8F%90%E7%A4%BA-07-13')
        ],
        [
            InlineKeyboardButton("🔙返回上级", callback_data='bd_dl_rt'),
            InlineKeyboardButton('❌关闭菜单', callback_data='bdexit')
        ]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(button), disable_web_page_preview=True)


@app.on_callback_query(filters.regex(r'^bdAll_dl'))
@output_error()
async def baidu_all_dl(_, query: CallbackQuery):
    mid = f'{query.message.chat.id}_{query.message.id}'
    rlist = chat_data[f'bd_rlist_{mid}']
    baidu = Baidu(rlist)
    fetch_failed = []
    
    async def add_dl(v):
        try:
            fs_id = v['fs_id']
            dir_list = await baidu.get_dlurl(fs_id=fs_id)
            return dir_list['filedata']['filename'], dir_list['directlink']
        except Exception as ee:
            logging.error(ee)
            fetch_failed.append(v['name'])
    
    dirname = rlist['dirdata']['src'][-1]['dirname']
    await query.message.edit_text(f'{dirname}|获取中...')
    a = [v for v in rlist['filedata'] if not v['isdir']]
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(asyncio.run, add_dl(v)) for v in a]
    results = [future.result() for future in concurrent.futures.wait(futures).done]
    
    button = [
        [
            InlineKeyboardButton('📖查看下载教程', url='https://telegra.ph/%E4%B8%8B%E8%BD%BD%E6%8F%90%E7%A4%BA-07-13')
        ],
        [
            InlineKeyboardButton("🔙返回上级", callback_data='bd_dl_rt'),
            InlineKeyboardButton('❌关闭菜单', callback_data='bdexit')
        ]
    ]
    
    t = [f"➡️{v[0]}\n{v[1]}" for v in results]
    u = '\n'.join([n[1] for n in results])
    text = f'\n\n{("=" * 40)}\n\n'.join(t)
    text = f"""路径：{rlist['dirdata']['src'][-1]['fullsrc']}
上部分为单个链接
下部分为全部链接

{text}
\n\n\n
{('*' * 100)}
全部链接：
{('*' * 100)}

{u}

"""
    if not os.path.exists('downloads'):
        os.mkdir('downloads')
    path = f"downloads/{dirname}.txt"
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    e = '\n'.join(fetch_failed)
    msg = await query.message.reply_document(document=path, reply_markup=InlineKeyboardMarkup(button),
                                             caption=f"获取失败：\n{e}" if fetch_failed else '',
                                             reply_to_message_id=query.message.id - 1)
    await query.message.delete()
    chat_data[f'bd_rlist_{msg.chat.id}_{msg.id}'] = chat_data[f'bd_rlist_{mid}']
    chat_data.pop(f'bd_rlist_{mid}')
    os.remove(path)


@app.on_callback_query(filters.regex(r'^bdexit'))
async def baidu_exit(_, query: CallbackQuery):
    await query.message.edit_text('已退出『百度解析』')


###########################################################################
# 字节数转文件大小
def pybyte(size, dot=2):
    size = float(size)
    # 位 比特 bit
    if 0 <= size < 1:
        human_size = f'{str(round(size / 0.125, dot))}b'
    elif 1 <= size < 1024:
        human_size = f'{str(round(size, dot))}B'
    elif math.pow(1024, 1) <= size < math.pow(1024, 2):
        human_size = f'{str(round(size / math.pow(1024, 1), dot))}KB'
    elif math.pow(1024, 2) <= size < math.pow(1024, 3):
        human_size = f'{str(round(size / math.pow(1024, 2), dot))}MB'
    elif math.pow(1024, 3) <= size < math.pow(1024, 4):
        human_size = f'{str(round(size / math.pow(1024, 3), dot))}GB'
    elif math.pow(1024, 4) <= size < math.pow(1024, 5):
        human_size = f'{str(round(size / math.pow(1024, 4), dot))}TB'
    else:
        raise ValueError(
            f'{pybyte.__name__}() takes number than or equal to 0, but less than 0 given.'
        )
    return human_size


class Baidu:
    def __init__(self, page_results: dict = None):
        if page_results:
            self.timestamp = page_results['dirdata']['timestamp']
            self.sign = page_results['dirdata']['sign']
            self.randsk = page_results['dirdata']['randsk']
            self.shareid = page_results['dirdata']['shareid']
            self.surl = page_results['dirdata']['surl']
            self.pwd = page_results['dirdata']['pwd']
            self.uk = page_results['dirdata']['uk']
    
    # 获取解析统计
    async def parse_count(self) -> str:
        async with httpx.AsyncClient() as client:
            result = await client.get(f'{baidu_url}/api.php?m=ParseCount')
            result = result.json()['msg'].replace('<br />', '\n')
            return result
    
    # 获取上次解析数据
    async def last_parse(self) -> str:
        async with httpx.AsyncClient() as client:
            result = await client.get(f'{baidu_url}/api.php?m=LastParse')
            result = result.json()['msg'].replace('<br />', '\n')
            return result
    
    # 解析链接根目录
    async def get_root_list(
            self,
            surl: str,
            pwd: str,
            password: str = baidu_password
    ) -> Dict:
        """

        :param surl:
        :param pwd:
        :param password:
        :return:
        {
            "error": 0,
            "isroot": true,
            "dirdata": {
                "src": [
                    "string"
                ],
                "timestamp": "string",
                "sign": "string",
                "randsk": "string",
                "shareid": "string",
                "surl": "string",
                "pwd": "string",
                "uk": "string"
            },
            "filenum": 0,
            "filedata": [
                {
                    "isdir": 0,
                    "name": "string",
                    "fs_id": "string",
                    "path": "string",
                    "size": 0,
                    "uploadtime": 0,
                    "dlink": "string"
                }
            ]
        }
        """
        data = {
            'surl': surl,
            'pwd': pwd,
            'password': password,
        }
        
        async with httpx.AsyncClient() as client:
            result = await client.post(f'{baidu_url}/api.php?m=GetList', data=data)
        return result.json()
    
    # 解析链接文件夹
    async def get_list(
            self,
            dir: str,
            password: str = baidu_password
    ) -> Dict:
        """

        :param dir:
        :param password:
        :return:
        {
      "error": 0,
      "isroot": true,
      "dirdata": {
        "src": [
          {}
        ],
        "timestamp": "string",
        "sign": "string",
        "randsk": "string",
        "shareid": "string",
        "surl": "string",
        "pwd": "string",
        "uk": "string"
      },
      "filenum": 0,
      "filedata": [
        {
          "isdir": 0,
          "name": "string",
          "fs_id": "string",
          "path": "string",
          "size": 0,
          "uploadtime": 0,
          "dlink": "string"
        }
      ]
    }
        """
        
        data = {
            'dir': dir,
            'timestamp': self.timestamp,
            'sign': self.sign,
            'randsk': self.randsk,
            'shareid': self.shareid,
            'surl': self.surl,
            'pwd': self.pwd,
            'uk': self.uk, 'password': password,
        }
        async with httpx.AsyncClient() as client:
            result = await client.post(f'{baidu_url}/api.php?m=GetList', data=data)
            result = result.json()
            # 对文件重新排序
            result['filedata'] = sorted(sorted(result['filedata'], key=lambda x: x['name']),
                                        key=lambda x: x['isdir'],
                                        reverse=True)
        return result
    
    # 获取下载地址
    async def get_dlurl(
            self,
            fs_id: str,
            password: str = baidu_password
    ) -> Dict:
        """

        :param fs_id:
        :param password:
        :return:
        {
  "error": 0,
  "msg": "string",
  "title": "string",
  "filedata": {
    "filename": "string",
    "size": "string",
    "path": "string",
    "uploadtime": 0,
    "md5": "string"
  },
  "directlink": "string",
  "user_agent": "string",
  "message": [
    "string"
  ]
}
        """
        data = {
            'fs_id': fs_id,
            'timestamp': self.timestamp,
            'sign': self.sign,
            'randsk': self.randsk,
            'shareid': self.shareid,
            'surl': self.surl,
            'pwd': self.pwd,
            'uk': self.uk,
            'password': password,
        }
        async with httpx.AsyncClient() as client:
            result = await client.post(f'{baidu_url}/api.php?m=Download', data=data)
        return result.json()


if __name__ == '__main__':
    chat_data = {}
    formats = {
        ".txt": "📄", ".docx": "📝", ".pdf": "📑", ".xlsx": "📊", ".pptx": "📑", ".jpg": "🖼️", ".png": "🖼️",
        ".mp3": "🎵", ".mp4": "🎥", ".flv": "🎥", ".avi": "🎥", ".wmv": "🎥", ".mov": "🎥", ".webm": "🎥",
        ".mkv": "🎥", ".zip": "📦", ".rar": "📦", ".7z": "📦", ".tar": "📦", ".gz": "📦", ".bz2": "📦", ".xz": "📦",
        ".tar.gz": "📦", ".tar.bz2": "📦", ".tar.xz": "📦", ".zipx": "📦", ".cab": "📦", ".iso": "📦", ".jar": "📦"
    }
    app.run()
