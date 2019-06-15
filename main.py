"""
简书爬虫
任务：
- 爬取简书推荐作者主页链接并存入数据库
- 每天定时从数据库取一条链接数据
- 爬取链接页作者最新文章
- 以作者头像为背景将文章做成词云图并将其发表到微博
"""

import sqlite3
import os
import time
import urllib
import logging
import schedule
import threading
from PIL import Image
import gevent
from gevent import monkey; monkey.patch_all()
from gevent.queue import Queue
import requests
import itchat
from bs4 import BeautifulSoup
import util
import config
from weibo import SinaWeibo, WeiboMessage

# 验证码消息队列
MSG_REC = False
CAP_QUEUE = Queue()

@itchat.msg_register(itchat.content.TEXT)
def captcha_reply(msg):
    global MSG_REC
    if MSG_REC:
        if msg['ToUserName'] == 'filehelper':
            CAP_QUEUE.put(msg.text)
            MSG_REC = False
            itchat.send('后台收到验证码消息, 正在处理请稍后...', toUserName='filehelper')
    else:
        itchat.send('非任务时间段，请不要发送消息哦～～～', toUserName='filehelper')

def captcha_handler():
    global MSG_REC
    while not CAP_QUEUE.empty():
        CAP_QUEUE.get()
    logging.warning('正在发送验证码')
    MSG_REC = True
    itchat.send('请回复你看到的验证码', toUserName='filehelper')
    itchat.send_image(config.CAPTCHA_FILE, toUserName='filehelper')
    logging.warning('成功发送验证码到文件助手，请回复收到的验证码')
    return CAP_QUEUE.get()

def get_page_urls(max_page):
    """获取所有页面链接"""
    page_urls = []
    for page in range(1, max_page+1):
        page_urls.append('https://www.jianshu.com/recommendations/users?page=%d' % page)
    return page_urls

def page_task(url_queue, page_url, base_url):
    """获取每个页面推荐作者链接任务"""
    logging.warning('正在抓取链接 url:%s' % page_url)
    head = {
        'accept' : 'text/html, */*; q=0.01',
        'accept-encoding' : 'gzip, deflate, br',
        'accept-language' : 'en,zh-CN;q=0.9,zh;q=0.8',
        'referer' : 'https://www.jianshu.com/recommendations/users?utm_source=desktop&utm_medium=index-users',
        'user-agent' : util.get_rand_ua(),
        'x-csrf-token' : 'yPSNc1P7wSbV/l7jdoJUT8l9o5HDOGs573SPIUROq7bIBF+v5sLBDtNrNZaAi3xohjIdKU/mjbc3ztLN1F8Y0A==',
        'x-pjax' : 'true',
        'x-requested-with' : 'XMLHttpRequest',
    }
    resp = requests.get(page_url, headers=head, timeout=3)
    content = resp.content.decode('utf-8')
    soup = BeautifulSoup(content, features='html.parser')
    items = soup.find_all('div', class_="col-xs-8")
    author_urls = []
    for item in items:
        author_urls.append(urllib.parse.urljoin(base_url, item.div.a.attrs.get('href')))
    url_queue.put_nowait(author_urls)


def data_save(url_queue, max_page):
    """链接存入数据库"""
    connect = sqlite3.connect(config.SQLITE3_PATH)
    cursor = connect.cursor()
    try:
        cursor.execute("create table urls (id integer primary key autoincrement,"\
            " url text not null, used tinyint)")
    except sqlite3.OperationalError:
        logging.warning('urls表已经存在')
    try:
        for i in range(max_page):
            author_urls = url_queue.get()
            for author_url in author_urls:
                logging.warning('正在存入链接 url:%s' % author_url)
                sql = "insert into urls (url, used) values ('%s', '0')" % author_url
                cursor.execute(sql)
                connect.commit()
                logging.warning('成功存入链接')
        logging.warning('抓取完毕')
    finally:
        connect.commit()
        connect.close()


def article_detail(article_url):
    """文章详情"""
    head = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en,zh-CN;q=0.9,zh;q=0.8',
        'cache-control': 'max-age=0',
        'referer': 'https://www.jianshu.com/',
        'upgrade-insecure-requests': '1',
        'user-agent': util.get_rand_ua(),
    }
    resp = requests.get(article_url, headers=head, timeout=3)
    content = resp.content.decode('utf-8')
    soup = BeautifulSoup(content, features='html.parser')
    note = soup.find('div', class_='note')
    article_info = {
        'title' : note.find('h1', class_='title').get_text(),
        'content' : '\n'.join([p.get_text() for p in soup.find('div', class_="show-content").find_all('p')])
    }
    return article_info

def author_detail(base_url, author_url):
    """作者详情页爬取"""
    head = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'en,zh-CN;q=0.9,zh;q=0.8',
        'cache-control': 'max-age=0',
        'referer': 'https://www.jianshu.com/',
        'upgrade-insecure-requests': '1',
        'user-agent': util.get_rand_ua(),
    }
    resp = requests.get(author_url, headers=head, timeout=3)
    content = resp.content.decode('utf-8')
    soup = BeautifulSoup(content, features='html.parser')
    p_tags = soup.find('div', class_='info').find_all('p')
    author_info = {
        'name' : soup.find('div', class_='title').a.get_text(),
        'avatar' : soup.find('a', class_='avatar').img.attrs.get('src'),
        'follow' : p_tags[0].get_text(),
        'fans' : p_tags[1].get_text(),
        'article_count' : p_tags[2].get_text(),
        'words' : p_tags[3].get_text(),
        'lovers' : p_tags[4].get_text(),
        'diamonds' : p_tags[5].get_text(),
        'articles' : [],
    }
    note_list = soup.find('ul', class_='note-list').find_all('li')
    for idx, note in enumerate(note_list):
        if idx == config.ARTICLE_COUNT:
            break
        article_url = urllib.parse.urljoin(base_url, note.find_all('a')[1].attrs.get('href'))
        author_info['articles'].append(article_detail(article_url))
    return author_info


def download_avatar(base_url, avatar_url):
    """下载头像并转换为黑白色"""
    resp = requests.get(urllib.parse.urljoin(base_url, avatar_url))
    with open(config.AVATAR_FILE, 'wb') as f:
        f.write(resp.content)
    return Image.open(config.AVATAR_FILE)


def send_task(base_url):
    """发表微博任务"""

    def send_weibo():
        logging.warning("[%s]准备发送一条微博.." % config.SEND_TIME)
        connect = sqlite3.connect('author_urls.sqlite3')
        cursor = connect.cursor()
        sql = 'select * from urls where used=0'
        cursor.execute(sql)
        data = cursor.fetchone()
        if data:
            author_info = author_detail(base_url, data[1])
            download_avatar(base_url, author_info['avatar'])
            images = [config.AVATAR_FILE]
            content = '简书作者: {name}\n关注: {follow}\n粉丝数: {fans}\n发表文章数: {article_count}\n'\
                '发表文字: {words}\n被喜欢收藏: {lovers}\n简书钻石数: {diamonds}\n'.format(**author_info)
            content += '最新发表:\n'
            for idx, article in enumerate(author_info['articles']):
                content += '- %s\n' % article['title']
                wcpath = os.path.join(config.TEMP_DIR, 'wc%d.jpg' % idx)
                util.create_wordcloud(article['content'], config.WL_FONT_FILE, config.WL_BG_FILE).save(wcpath)
                images.append(wcpath)
            wbmsg = WeiboMessage(content, images=images)
            sw = SinaWeibo(config.USERNAME, config.PASSWORD)
            for idx in range(3):
                if sw.login(captcha_handler):
                    sw.send_weibo(wbmsg)
                    logging.warning("发送微博成功")
                    itchat.send('发送微博成功', toUserName='filehelper')
                    sql = 'update urls set used=1 where id=%s' % data[0]
                    cursor.execute(sql)
                    connect.commit()
                    break
                if idx == 2:
                    logging.warning("发送微博失败")
                    itchat.send('发送微博失败', toUserName='filehelper')
        connect.close()

    logging.warning('开始定时发送任务')
    # 计划时间发送
    schedule.every().day.at(config.SEND_TIME).do(send_weibo)
    while True:
        schedule.run_pending()
        gevent.sleep(2)
    logging.warning('结束定时发送任务')


def main():
    """任务入口"""

    # 目前推荐页最大页数为100
    max_page = 100

    # # 主链接
    base_url = 'https://www.jianshu.com/'

    # 获取所有页面链接
    page_urls = get_page_urls(max_page)

    # url队列
    url_queue = Queue()

    # 创建greenlets并加入页面爬取任务
    greenlets = [gevent.spawn(page_task, url_queue, page_url, base_url) for page_url in page_urls]

    # 微信登陆
    itchat.auto_login(hotReload=True)

    # 开启微博发送任务
    threading.Thread(target=send_task, args=[base_url]).start()

    # 开启微信消息循环
    threading.Thread(target=itchat.run).start()

    # 加入数据存储任务
    greenlets.append(gevent.spawn(data_save, url_queue, max_page))

    # 等待所有greenlets完成
    gevent.joinall(greenlets)

if __name__ == '__main__':
    main()
