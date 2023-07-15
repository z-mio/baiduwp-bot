# baiduwp-bot
一个基于baiduwp-php API的百度网盘解析bot

体验一下：[@getletbot](https://t.me/getletbot)

<details>
<summary><b>功能预览</b></summary>

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/1.png)

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/2.png)

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/3.png)

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/4.png)

### 获取单个文件链接

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/5.png)

### 获取当前文件夹下所有文件链接

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/6.png)

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/7.png)

![enter description here](https://github.com/z-mio/baiduwp-bot/blob/f56f9b9912227d523942e0c732111759a7c7b7a0/image/8.png)

</details>


## 1.安装


**1.安装 python3-pip**

```
apt install python3-pip
```


**2.将项目克隆到本地**
``` 
git clone https://github.com/z-mio/baiduwp-bot.git && cd baiduwp-bot && pip3 install -r requirements.txt
```

**3.修改 bot.py 里的配置信息**

``` python
#########################################
# bot

api_id = ''  # 在 https://my.telegram.org/apps 获取

api_hash = ''  # 在 https://my.telegram.org/apps 获取

bot_token = ''  # 在 https://t.me/BotFather 获取

admin = '123456789'  # 管理员用户id,可通过 https://t.me/get_id_bot 获取id

members = [123456789, 987654321]  # 允许使用解析的 用户、群组、频道 id获取方式同上（群组和频道id需要加上-100）

baidu_url = ''  # 你的百度解析地址

baidu_password = ''  # 解析密码(不是后台密码)
#########################################
# 代理支持“socks4”、“socks5”和“http”
scheme = ''  # 'http'
hostname = ''  # '127.0.0.1'
port = ''  # '7890'
#########################################
```

## 2.运行

**前台启动bot**

``` 
python3 bot.py
```


**后台启动bot**

``` 
nohup python3 bot.py > botlog.log 2>&1 &
```

## 3.使用

发送`/menu`自动设置菜单

指令：

``` 
/bd - 百度网盘解析
```