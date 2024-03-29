# -*- coding: UTF-8 -*-
import asyncio
import contextlib
import datetime
import hashlib
import logging
import math
import os
import re
from dataclasses import dataclass
from typing import List, Tuple

import httpx
from pyrogram import Client, filters
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

#########################################
# bot

api_id = ""  # 在 https://my.telegram.org/apps 获取

api_hash = ""  # 在 https://my.telegram.org/apps 获取

bot_token = ""  # 在 https://t.me/BotFather 获取

# 允许使用解析的 用户、群组、频道（群组和频道id需要加上-100）可通过 https://t.me/getletbot 获取id，不填则为公开使用
members = []

baidu_version = "4"  # 你部署的baiduwp-php版本，填 3 或 4

baidu_url = "https://"  # 你的百度解析地址

baidu_password = ""  # 解析密码(不是后台密码)
#########################################
# 代理支持“socks4”、“socks5”和“http”
scheme = ""  # 'http'
hostname = ""  # '127.0.0.1'
port: int = 7890  # 7890
#########################################
WARNING_MESSAGE = "这不是你的解析结果哦"
PER_PAGE = 15  # 每页数量

logging.basicConfig(
    handlers=[logging.StreamHandler(), logging.FileHandler("bot.log")],
    format="%(asctime)s - %(name)s - %(levelname)s: %(message)s",
    level=logging.INFO,
)
logging.info("Bot开始运行...")
baidu_url = baidu_url.rstrip("/")

app = Client(
    "my_bot",
    bot_token=bot_token,
    api_id=api_id,
    api_hash=api_hash,
    proxy={"scheme": scheme, "hostname": hostname, "port": port}
    if all([scheme, hostname, port])
    else None,
)


# 设置菜单
@app.on_message(filters.command("menu") & filters.private)
async def menu(_, message: Message):
    await app.set_bot_commands([BotCommand(command="bd", description="百度网盘解析")])
    await app.send_message(chat_id=message.chat.id, text="菜单设置成功，请退出聊天界面重新进入来刷新菜单")


class SrcData:
    def __init__(self, src_data):
        self.isactive = src_data.get("isactive", 0)
        self.fullsrc = src_data.get("fullsrc", "")
        self.dirname = src_data.get("dirname", "")


class DirData:
    def __init__(self, dirdata):
        self.src: List[SrcData] = [SrcData(src) for src in dirdata.get("src", [])]
        self.timestamp = dirdata.get("timestamp", "")
        self.sign = dirdata.get("sign", "")
        self.randsk = dirdata.get("randsk", "")
        self.shareid = dirdata.get("shareid", "")
        self.surl = dirdata.get("surl", "")
        self.pwd = dirdata.get("pwd", "")
        self.uk = dirdata.get("uk", "")


class FileData:
    def __init__(self, filedata):
        self.isdir = filedata.get("isdir", 0)
        self.name = filedata.get("name", "")
        self.fs_id = filedata.get("fs_id", "")
        self.path = filedata.get("path", "")
        self.size = filedata.get("size", 0)
        self.uploadtime = filedata.get("uploadtime", 0)
        self.dlink = filedata.get("dlink", "")


class ParseList:
    def __init__(self, response_data):
        self.error = response_data.get("error", None)
        self.isroot = response_data.get("isroot", False)
        self.dirdata: DirData = DirData(response_data.get("dirdata", {}))
        self.filenum = response_data.get("filenum", 0)
        self.filedata: List[FileData] = [
            FileData(file) for file in response_data.get("filedata", [])
        ]
        self.error_msg = response_data["msg"] if self.error else ""

    @staticmethod
    def parse_dirdata(dirdata):
        return {
            "src": dirdata.get("src", []),
            "timestamp": dirdata.get("timestamp", ""),
            "sign": dirdata.get("sign", ""),
            "randsk": dirdata.get("randsk", ""),
            "shareid": dirdata.get("shareid", ""),
            "surl": dirdata.get("surl", ""),
            "pwd": dirdata.get("pwd", ""),
            "uk": dirdata.get("uk", ""),
        }

    @staticmethod
    def parse_filedata(filedata_list):
        return [
            {
                "isdir": filedata.get("isdir", 0),
                "name": filedata.get("name", ""),
                "fs_id": filedata.get("fs_id", ""),
                "path": filedata.get("path", ""),
                "size": filedata.get("size", 0),
                "uploadtime": filedata.get("uploadtime", 0),
                "dlink": filedata.get("dlink", ""),
            }
            for filedata in filedata_list
        ]


class ParseData:
    def __init__(self, bd_rlist=None, bd_rlist_root=None, page=None, pre_dir=None):
        if pre_dir is None:
            pre_dir = {}
        if page is None:
            page = {}

        self.page = page
        self.bd_rlist = bd_rlist
        self.bd_rlist_root = bd_rlist_root
        self.pre_dir = pre_dir

    def get_pre_dir(self, key, default=None):
        return self.pre_dir.get(key, default)

    def get_page(self, key):
        return self.page.get(key, 1)


def return_dir(root_list: ParseList):
    return root_list.dirdata.src[-1].fullsrc if root_list.dirdata.src else "/"


def return_dir_md5(root_list: ParseList):
    return md5_hash(return_dir(root_list))


# 构建菜单
def build_menu(
    root_list: ParseList,
    mid: str,
    page: int = 1,
):
    text = f"""目录：{f'`{return_dir(root_list)}`'}
数量：{root_list.filenum}
"""
    button = [
        [
            InlineKeyboardButton(
                text=f"{i + 1}.{'📁' if v.isdir else formats.get(os.path.splitext(v.name)[1], '📄')}{v.name}",
                callback_data=f"bd_{i}" if v.isdir else f"bdf_{i}",
            )
        ]
        for i, v in enumerate(root_list.filedata)
    ]

    page = max(1, min(page, math.ceil(len(button) / PER_PAGE)))
    chat_data[mid].page[return_dir_md5(root_list)] = page

    tp = [
        InlineKeyboardButton(text="上一页", callback_data="page_p_p"),
        InlineKeyboardButton(
            text=f"{page}/{math.ceil(len(button) / PER_PAGE)}", callback_data="page"
        ),
        InlineKeyboardButton(text="下一页", callback_data="page_n_p"),
    ]
    but = [
        InlineKeyboardButton(text="🔙返回上级", callback_data="bd_rt"),
        InlineKeyboardButton(text="❌关闭菜单", callback_data="bdexit"),
    ]
    but_1 = [
        InlineKeyboardButton(text="🌐获取本页所有文件下载链接", callback_data="bdAll_dl"),
    ]
    button = button[(page - 1) * PER_PAGE : page * PER_PAGE]

    # 添加获取全部按钮
    rlf = root_list.filedata[(page - 1) * PER_PAGE : page * PER_PAGE]
    if [v for v in rlf if not v.isdir]:
        button.insert(0, but_1)
        if rlf[10:]:
            button.append(but_1)
    # 翻页按钮
    if root_list.filedata[PER_PAGE:]:
        button.append(tp)
        if rlf[10:]:
            button.insert(1, tp)
    # 返回上级按钮
    button.insert(0, but)
    if rlf[10:]:
        button.append(but)

    return text, button


@app.on_callback_query(filters.regex("^page_"))
async def turn_page(_, cq: CallbackQuery):
    mid = f"{cq.from_user.id}_{cq.message.id}"
    data = cq.data
    rl = chat_data.get(mid)
    if not rl:
        return await cq.answer(text=WARNING_MESSAGE, show_alert=True)
    rl = rl.bd_rlist
    text, button = build_menu(
        rl,
        mid,
        chat_data[mid].get_page(return_dir_md5(rl)) + (-1 if data == "page_p_p" else 1),
    )
    try:
        await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup(button))
    except MessageNotModified:
        ...


@app.on_message(filters.command("bd"))
async def baidu_jx(_, message: Message):
    if members and message.chat.id not in members:
        return
    parameter = " ".join(message.command[1:])
    parameter = parameter or (
        message.reply_to_message.text if message.reply_to_message else None
    )
    baidu = Baidu()

    if not parameter:
        system = await baidu.system_text()
        text = f"""
{system}
请加上分享链接，链接格式随意，例：
`/bd 链接: https://pan.baidu.com/s/1uY-UL9KN9cwKiTX5TzIEuw?pwd=jwdp 提取码: jwdp 复制这段内容后打开百度网盘手机App，操作更方便哦`
"""
        return await message.reply(text)
    msg = await message.reply("解析中...", quote=True)
    mid = f"{message.from_user.id}_{msg.id}"

    def extract_link_and_password(_text: str) -> Tuple[str, str]:
        formatted_links = re.search(r"(?:/s/|surl=)([\w-]+)", _text)[1]  # 匹配/s/后面的码
        formatted_links = (
            formatted_links
            if formatted_links.startswith("1")
            else f"1{formatted_links}"
        )
        password_pattern = r"(?<=\bpwd=)[a-zA-Z0-9]+|[^/](\b[a-zA-Z0-9]{4}\b(?!\.))(?<!link)(?<!https)(?<!surl)"  # 匹配密码
        passwords = re.search(password_pattern, _text.replace(formatted_links, ""))
        password = passwords[1] if passwords else None
        return formatted_links, password

    try:
        surl, pwd = extract_link_and_password(parameter)
        root_list = await baidu.parse_list(surl, pwd)
        if root_list.error:
            return await msg.edit_text(root_list.error_msg)
        chat_data[mid] = ParseData(bd_rlist=root_list, bd_rlist_root=root_list)

        text, button = build_menu(root_list, mid)
        await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(button))
    except Exception as e:
        await msg.edit_text(f"错误：{e}")


async def get_or_fetch_dir_list(
    parse_data: ParseData, baidu_instance, dir_hash: str, surl: str, pwd: str, dir_=None
):
    dir_list = parse_data.pre_dir.get(dir_hash)
    if not dir_list:
        dir_list = await baidu_instance.parse_list(surl=surl, pwd=pwd, dir_=dir_)
        parse_data.pre_dir[dir_hash] = dir_list
    return dir_list


@app.on_callback_query(filters.regex(r"^bd_"))
async def baidu_list(_, query: CallbackQuery):
    mid = f"{query.from_user.id}_{query.message.id}"
    pd = chat_data.get(mid)
    if not pd or not pd.bd_rlist:
        return await query.answer(text=WARNING_MESSAGE, show_alert=True)

    baidu = Baidu(pd.bd_rlist)
    rlist: ParseList = pd.bd_rlist
    surl = rlist.dirdata.surl
    pwd = rlist.dirdata.pwd

    dir_list = None
    _dir = None

    # 根据callback数据决定动作
    if query.data == "bd_rt":
        if len(rlist.dirdata.src) == 1:
            dir_list = pd.bd_rlist_root or await baidu.parse_list(surl=surl, pwd=pwd)
        else:
            _dir = rlist.dirdata.src[-2].fullsrc

    elif query.data == "bd_dl_rt":
        if rlist.dirdata.src:
            _dir = rlist.dirdata.src[-1].fullsrc
        else:
            dir_list = pd.bd_rlist_root or await baidu.parse_list(surl=surl, pwd=pwd)

    else:
        num = int(query.data.split("_")[1])
        _dir = rlist.filedata[num].path

    if _dir:
        dir_hash = md5_hash(_dir)
        dir_list = await get_or_fetch_dir_list(
            pd, baidu, dir_hash, surl, pwd, dir_=_dir
        )

    # 更新当前目录列表
    pd.bd_rlist = dir_list

    # 构建响应
    text, button = build_menu(dir_list, mid, pd.get_page(return_dir_md5(dir_list)))
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(button))
    await preloading(rlist, dir_list, mid)


# 预加载文件夹
async def preloading(rlist, dir_list: ParseList, mid):
    baidu = Baidu(rlist)

    async def load(dir_):
        try:
            dir_list = await baidu.parse_list(dir_=dir_)
            chat_data[mid].pre_dir[md5_hash(dir_)] = dir_list
        except Exception as ee:
            logging.error(ee)

    d_l = [
        i.path
        for i in dir_list.filedata
        if i.isdir and not chat_data[mid].get_pre_dir(md5_hash(i.path))
    ]
    if not d_l[20:]:
        task = [load(v) for v in d_l]
        await asyncio.gather(*task)


@app.on_callback_query(filters.regex(r"^bdf_"))
async def baidu_file(_, query: CallbackQuery):
    mid = f"{query.from_user.id}_{query.message.id}"
    rlist = chat_data.get(mid)
    if not rlist:
        return await query.answer(text=WARNING_MESSAGE, show_alert=True)
    rlist = rlist.bd_rlist
    num = query.data.split("_")[1]
    fs_id = rlist.filedata[int(num)].fs_id

    baidu = Baidu(rlist)
    dir_list = await baidu.get_dlurl(fs_id=fs_id)
    text = f"""
路径：`{dir_list.path}`

文件名称：`{dir_list.file_name}`
文件大小：`{dir_list.file_size}`
MD5：`{dir_list.md5}`
上传时间：`{dir_list.upload_time}`
User-Agent：`{dir_list.user_agent}`

**>>>[点击查看下载教程](https://telegra.ph/%E4%B8%8B%E8%BD%BD%E6%8F%90%E7%A4%BA-07-13)<<<**
"""
    button = [
        [
            InlineKeyboardButton("💾下载文件", url=dir_list.directlink),
            InlineKeyboardButton(
                "📖查看下载教程",
                url="https://telegra.ph/%E4%B8%8B%E8%BD%BD%E6%8F%90%E7%A4%BA-07-13",
            ),
        ],
        [
            InlineKeyboardButton("🔙返回上级", callback_data="bd_dl_rt"),
            InlineKeyboardButton("❌关闭菜单", callback_data="bdexit"),
        ],
    ]
    await query.message.edit_text(
        text, reply_markup=InlineKeyboardMarkup(button), disable_web_page_preview=True
    )


@app.on_callback_query(filters.regex(r"^bdAll_dl"))
async def baidu_all_dl(_, query: CallbackQuery):
    mid = f"{query.from_user.id}_{query.message.id}"
    rlist = chat_data.get(mid)
    if not rlist:
        return await query.answer(text=WARNING_MESSAGE, show_alert=True)
    rlist = rlist.bd_rlist
    baidu = Baidu(rlist)
    fetch_failed = []

    async def add_dl(v):
        try:
            fs_id = v.fs_id
            dir_list = await baidu.get_dlurl(fs_id=fs_id)
            return dir_list.file_name, dir_list.directlink
        except Exception as ee:
            logging.error(ee)
            fetch_failed.append(v.name)

    dirname = rlist.dirdata.src[-1].dirname if rlist.dirdata.src else "根目录"
    await query.message.edit_text(f"{dirname}|获取中...")
    page = chat_data[mid].get_page(return_dir_md5(rlist))
    a = [
        v
        for v in rlist.filedata[(page - 1) * PER_PAGE : page * PER_PAGE]
        if not v.isdir
    ]
    task = [add_dl(v) for v in a]
    results = await asyncio.gather(*task)

    button = [
        [
            InlineKeyboardButton(
                "📖查看下载教程",
                url="https://telegra.ph/%E4%B8%8B%E8%BD%BD%E6%8F%90%E7%A4%BA-07-13",
            )
        ],
        [
            InlineKeyboardButton("🔙返回上级", callback_data="bd_dl_rt"),
            InlineKeyboardButton("❌关闭菜单", callback_data="bdexit"),
        ],
    ]
    t = [f"➡️{v[0]}\n{v[1]}" for v in results if v]
    u = "\n".join([n[1] for n in results if n])
    text = f'\n\n{("=" * 40)}\n\n'.join(t)
    text = f"""路径：{rlist.dirdata.src[-1].fullsrc if rlist.dirdata.src else '根目录'}
上部分为单个链接
下部分为全部链接

{text}
\n\n\n
{('*' * 100)}
全部链接：
{('*' * 100)}

{u}

"""
    if not os.path.exists("downloads"):
        os.mkdir("downloads")
    path = f"downloads/{dirname}.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    e = "\n".join(fetch_failed)
    msg: Message = await query.message.reply_document(
        document=path,
        reply_markup=InlineKeyboardMarkup(button),
        caption=f"**获取失败：**\n{e}" if fetch_failed else "",
        reply_to_message_id=query.message.id - 1,
    )
    await query.message.delete()
    chat_data[f"{query.from_user.id}_{msg.id}"] = chat_data[mid]
    chat_data.pop(mid)
    os.remove(path)


@app.on_callback_query(filters.regex(r"^bdexit"))
async def baidu_exit(_, query: CallbackQuery):
    mid = f"{query.from_user.id}_{query.message.id}"
    rl = chat_data.get(mid)
    if not rl:
        return await query.answer(text=WARNING_MESSAGE, show_alert=True)
    await query.message.edit_text("已退出『百度解析』")
    chat_data.pop(mid)


###########################################################################
# 字节数转文件大小
def pybyte(size, dot=2):
    size = float(size)
    # 位 比特 bit
    if 0 <= size < 1:
        human_size = f"{str(round(size / 0.125, dot))}b"
    elif 1 <= size < 1024:
        human_size = f"{str(round(size, dot))}B"
    elif math.pow(1024, 1) <= size < math.pow(1024, 2):
        human_size = f"{str(round(size / math.pow(1024, 1), dot))}KB"
    elif math.pow(1024, 2) <= size < math.pow(1024, 3):
        human_size = f"{str(round(size / math.pow(1024, 2), dot))}MB"
    elif math.pow(1024, 3) <= size < math.pow(1024, 4):
        human_size = f"{str(round(size / math.pow(1024, 3), dot))}GB"
    elif math.pow(1024, 4) <= size < math.pow(1024, 5):
        human_size = f"{str(round(size / math.pow(1024, 4), dot))}TB"
    else:
        raise ValueError(
            f"{pybyte.__name__}() takes number than or equal to 0, but less than 0 given."
        )
    return human_size


def md5_hash(input_string: str) -> str:
    md5_hash_object = hashlib.md5()
    md5_hash_object.update(input_string.encode("utf-8"))
    return md5_hash_object.hexdigest()


def retry(max_retries=3):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            for _ in range(max_retries):
                with contextlib.suppress(Exception):
                    return await func(*args, **kwargs)
                await asyncio.sleep(1)
            raise Exception("连接超时")

        return wrapper

    return decorator


@dataclass
class System:
    last_time: str
    limit: bool
    today_times: int
    today_flow: str
    all_times: int
    all_flow: str


@dataclass
class B:
    timestamp: str = None
    sign: str = None
    randsk: str = None
    shareid: str = None
    surl: str = None
    pwd: str = None
    uk: str = None


class DlUrl:
    def __init__(self, result):
        self.result = result
        self.path: str = self.result["filedata"]["path"]
        self.file_name: str = self.result["filedata"]["filename"]
        self.file_size: str = pybyte(self.result["filedata"]["size"])
        self.md5: str = self.result["filedata"]["md5"]
        self.upload_time: datetime = datetime.datetime.fromtimestamp(
            int(self.result["filedata"]["uploadtime"])
        )
        self.user_agent: str = self.result["user_agent"]
        self.directlink: str = self.result["directlink"]


class Baidu:
    def __init__(self, page_results: ParseList = None):
        self.B = B()
        if page_results:
            dirdata = page_results.dirdata
            self.B = B(
                dirdata.timestamp,
                dirdata.sign,
                dirdata.randsk,
                dirdata.shareid,
                dirdata.surl,
                dirdata.pwd,
                dirdata.uk,
            )

    # 获取解析统计 3.x
    @staticmethod
    @retry()
    async def parse_count() -> str:
        async with httpx.AsyncClient() as client:
            result = await client.get(f"{baidu_url}/api.php?m=ParseCount")
            result = result.json()["msg"].replace("<br />", "\n")
            return result

    # 获取上次解析数据 3.x
    @staticmethod
    @retry()
    async def last_parse() -> str:
        async with httpx.AsyncClient() as client:
            result = await client.get(f"{baidu_url}/api.php?m=LastParse")
            result = result.json()["msg"].replace("<br />", "\n")
            return result

    # 获取上次解析数据 & 获取解析状态 4.x
    @staticmethod
    @retry()
    async def get_system() -> System:
        async with httpx.AsyncClient() as client:
            result = await client.get(f"{baidu_url}/system")
            result = result.json()

        return System(
            result["account"]["last_time"],
            result["account"]["limit"],
            result["count"]["today"]["times"],
            result["count"]["today"]["flow"],
            result["count"]["all"]["times"],
            result["count"]["all"]["flow"],
        )

    async def system_text(self):
        if baidu_version == "3":
            parse_count = await self.parse_count()
            last_parse = await self.last_parse()
            return f"""
{parse_count}

{last_parse}
"""
        else:
            system = await self.get_system()
            return f"""
系统使用统计
累计解析: {system.all_times} ({pybyte(system.all_flow)})
今日解析: {system.today_times} ({pybyte(system.today_flow)})

SVIP账号状态
上次解析: {system.last_time}
账号状态: {'限速' if system.limit else '正常'}
"""

    # 解析链接根目录 3.x
    @staticmethod
    @retry()
    async def get_root_list(
        surl: str,
        pwd: str,
    ) -> ParseList:
        """

        :param surl:
        :param pwd:
        :return:
        """
        data = {
            "surl": surl,
            "pwd": pwd,
            "password": baidu_password,
        }

        async with httpx.AsyncClient() as client:
            result = await client.post(f"{baidu_url}/api.php?m=GetList", data=data)
        return ParseList(result.json())

    # 解析链接文件夹 3.x 4.x

    @retry()
    async def get_list(
        self,
        surl: str = None,
        pwd: str = None,
        dir_: str = None,
    ) -> ParseList:
        """

        :param surl:
        :param pwd:
        :param dir_:
        :return:
        """

        data = {
            "dir": dir_,
            "timestamp": self.B.timestamp,
            "sign": self.B.sign,
            "randsk": self.B.randsk,
            "shareid": self.B.shareid,
            "surl": surl or self.B.surl,
            "pwd": pwd or self.B.pwd,
            "uk": self.B.uk,
            "password": baidu_password,
        }

        async with httpx.AsyncClient() as client:
            api = "/api.php?m=GetList" if baidu_version == "3" else "/parse/list"
            result = await client.post(f"{baidu_url}{api}", data=data)
            result = ParseList(result.json())
            # 对文件重新排序
            if dir_:
                result.filedata = sorted(
                    sorted(result.filedata, key=lambda x: x.name),
                    key=lambda x: x.isdir,
                    reverse=True,
                )
            return result

    async def parse_list(
        self,
        surl: str = None,
        pwd: str = None,
        dir_: str = None,
    ) -> ParseList:
        """
        :param surl:
        :param pwd:
        :param dir_:
        :return:
        """
        return (
            await self.get_root_list(surl, pwd)
            if baidu_version == "3"
            else await self.get_list(surl, pwd, dir_)
        )

    # 获取下载地址 3.x 4.x
    @retry()
    async def get_dlurl(self, fs_id: str) -> DlUrl:
        """

        :param fs_id:
        :return:
        """
        data = {
            "fs_id": fs_id,
            "timestamp": self.B.timestamp,
            "sign": self.B.sign,
            "randsk": self.B.randsk,
            "shareid": self.B.shareid,
            "surl": self.B.surl,
            "pwd": self.B.pwd,
            "uk": self.B.uk,
            "password": baidu_password,
        }
        async with httpx.AsyncClient() as client:
            api = "/api.php?m=Download" if baidu_version == "3" else "/parse/link"
            result = await client.post(f"{baidu_url}{api}", data=data)
            return DlUrl(result.json())


if __name__ == "__main__":
    chat_data: dict[str, ParseData] = {}
    formats = {
        ".txt": "📄",
        ".docx": "📝",
        ".pdf": "📑",
        ".xlsx": "📊",
        ".pptx": "📑",
        ".jpg": "🖼️",
        ".png": "🖼️",
        ".mp3": "🎵",
        ".mp4": "🎥",
        ".flv": "🎥",
        ".avi": "🎥",
        ".wmv": "🎥",
        ".mov": "🎥",
        ".webm": "🎥",
        ".mkv": "🎥",
        ".zip": "📦",
        ".rar": "📦",
        ".7z": "📦",
        ".tar": "📦",
        ".gz": "📦",
        ".bz2": "📦",
        ".xz": "📦",
        ".tar.gz": "📦",
        ".tar.bz2": "📦",
        ".tar.xz": "📦",
        ".zipx": "📦",
        ".cab": "📦",
        ".iso": "📦",
        ".jar": "📦",
    }
    app.run()
