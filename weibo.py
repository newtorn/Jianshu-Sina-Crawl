"""新浪微博爬虫
为了实现能够发表文章，需要模拟登陆
模拟登陆中，需要提取到加密算法
验证码通过itchat发送至微信文件助手，收到验证码后回复
反爬机制是通过加密实现，需要完整模拟浏览器行为
"""

import os
import re
import rsa
import time
import json
import base64
import random
import logging
import requests
import config
import urllib.parse
import util
from binascii import b2a_hex

'''JS加密用户密码，需转换为Python代码加密
if ((me.loginType & rsa) && me.servertime && sinaSSOEncoder && sinaSSOEncoder.RSAKey) {
    request.servertime = me.servertime;
    request.nonce = me.nonce;
    request.pwencode = "rsa2";
    request.rsakv = me.rsakv;
    var RSAKey = new sinaSSOEncoder.RSAKey();
    RSAKey.setPublic(me.rsaPubkey, "10001");
    password = RSAKey.encrypt([me.servertime, me.nonce].join("\t") + "\n" + password)
} else {
    if ((me.loginType & wsse) && me.servertime && sinaSSOEncoder && sinaSSOEncoder.hex_sha1) {
        request.servertime = me.servertime;
        request.nonce = me.nonce;
        request.pwencode = "wsse";
        password = sinaSSOEncoder.hex_sha1("" + sinaSSOEncoder.hex_sha1(sinaSSOEncoder.hex_sha1(password)) + me.servertime + me.nonce)
    }
}'''

# 图片最大数量为9张
if config.MAX_IMAGES < 0 or config.MAX_IMAGES > 9:
    config.MAX_IMAGES = 9

class SinaWeibo:
    """新浪微博类"""
    def __init__(self, username, password):
        """初始化
        @ param :username: 用户账号
        @ param :password: 用户密码
        """
        self.username = username
        self.password = password
        self._session = requests.session()
        self._session.headers['user-agent'] = util.get_rand_ua()
        self._session.get('https://login.sina.com.cn/signup/signin.php')

    def _pre_login(self):
        """预登录"""
        url = 'https://login.sina.com.cn/sso/prelogin.php?entry=weibo&callback=sinaSSOController.preloginCallBack&su={}'\
            '&rsakt=mod&checkpin=1&client=ssologin.js(v1.4.19)&_={}'.format(urllib.parse.quote(self._get_su()), int(time.time()*1000))
        try:
            res = self._session.get(url).text
            res = re.findall(r"({.*})", res)[0]
            self._res = json.loads(res)
            self._nonce = self._res["nonce"]
            self._pubkey = self._res["pubkey"]
            self._rsakv = self._res["rsakv"]
            self._servertime = self._res["servertime"]
            # print(self.nonce,'\n',self.pubkey,'\n',self.rsakv,'\n',self.servertime)
        except Exception as error:
            logging.error("WeiBoLogin pre_log error: %s", error)

    def _get_su(self):
        """加密用户账号"""
        return base64.b64encode(self.username.encode()).decode()

    def _get_sp(self):
        """加密用户密码"""
        publickey = rsa.PublicKey(int(self._pubkey, 16), int('10001', 16))
        message = str(self._servertime) + '\t' + str(self._nonce) + '\n' + str(self.password)
        return b2a_hex(rsa.encrypt(message.encode(), publickey))

    def _login(self, captcha_handler=None):
        """内部调用登陆"""
        data = {
            'entry': 'account',
            'gateway': '1',
            'from': 'null',
            'savestate': '30',
            'useticket': '0',
            'vsnf': '1',
            'su': self._get_su(),
            'service': 'account',
            'servertime': self._servertime,
            'nonce': self._nonce,
            'pwencode': 'rsa2',
            'rsakv': self._rsakv,
            'sp': self._get_sp(),
            'sr': '1920*1080',
            'encoding': 'UTF-8',
            'prelt': random.randint(1, 100),
            'url': 'https://weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
            'returntype': 'TEXT'
        }

        # 验证码
        if self._res["showpin"] == 1:
            url = "http://login.sina.com.cn/cgi/pin.php?r=%d&s=0&p=%s" % (int(time.time()), self._res["pcid"])
            with open("./temp/captcha.png", "wb") as file_out:
                file_out.write(self._session.get(url).content)
            if captcha_handler is not None:
                captcha = captcha_handler()
            else:
                captcha = input("请输入微博登陆验证码: ")
            data["pcid"] = self._res["pcid"]
            data["door"] = captcha


        url = 'https://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.19)'
        json_data = self._session.post(url, data=data).json()

        #判断post登录是否成功
        if json_data['retcode'] == '0':
            params = {
                'ticket': json_data['ticket'],
                'ssosavestate': int(time.time()),
                'callback': 'sinaSSOController.doCrossDomainCallBack',
                'scriptId': 'ssoscript0',
                'client': 'ssologin.js(v1.4.19)',
                '_': int(time.time()*1000)
            }
            #二次登录网页验证
            url = 'https://passport.weibo.com/wbsso/login'
            res = self._session.get(url, params=params)
            # print(res.text)
            json_data = json.loads(re.search(r'({"result":.*})', res.text).group())
            #判断是否登录成功
            if json_data['result'] is True:
                # print(res.cookies.get('userinfo'))
                logging.warning('微博登陆成功: %s', json_data)
            else:
                logging.warning('微博登陆失败: %s', json_data)
        else:
            logging.warning('微博登陆成功: %s', json_data)
        try:
            self.uid = json_data['userinfo']['uniqueid']
            return True
        except:
            return False

    def login(self, captcha_handler=None):
        """登陆"""
        self._pre_login()
        return self._login(captcha_handler)

    def send_weibo(self, wbmsg):
        """发表微博"""
        if not isinstance(wbmsg, WeiboMessage):
            raise ValueError('wbmsg must WeiboMessage class type')
            logging.warning('wbmsg must WeiboMessage class type')
        if wbmsg.is_empty():
            logging.warning('空消息不能发表')
            return
        pids = ''
        if wbmsg.has_image():
            pids = self.upload_images(wbmsg.images)
        data = wbmsg.get_send_data(pids)
        self._session.headers["Referer"] = "http://www.weibo.com/u/%s/home?wvr=5" % self.uid
        try:
            self._session.post("https://www.weibo.com/aj/mblog/add?ajwvr=6&__rnd=%d" 
                % int(time.time() * 1000), data=data)
            logging.warning('成功发送微博 [%s] !' % str(wbmsg))
        except Exception as e:
            logging.warning('失败发送微博 [%s] !' % str(wbmsg))

    def upload_images(self, images):
        """获取上传图片的pid"""
        pids = ""
        if len(images) > config.MAX_IMAGES:
            images = images[0: config.MAX_IMAGES]
        for image in images:
            pid = self._upload_image(image)
            if pid:
                pids += " " + pid
            time.sleep(10)
        return pids.strip()

    def _upload_image(self, image_file):
        """长传图片至新浪后台"""
        if config.ADD_WATERMARK:
            url = "http://picupload.service.weibo.com/interface/pic_upload.php?\
            app=miniblog&data=1&url=" \
                + config.WATERMARK_URL + "&markpos=1&logo=1&nick=" \
                + config.WATERMARK_NIKE + \
                "&marks=1&mime=image/jpeg&ct=0.5079312645830214"
        else:
            url = "http://picupload.service.weibo.com/interface/pic_upload.php?\
            rotate=0&app=miniblog&s=json&mime=image/jpeg&data=1&wm="

        def upload():
            # self.http.headers["Content-Type"] = "application/octet-stream"
            try:
                with open(image_file, 'rb') as f:
                    img = f.read()
                resp = self._session.post(url, data=img)
                upload_json = re.search('{.*}}', resp.text).group(0)
                result = json.loads(upload_json)
                code = result["code"]
                if code == "A00006":
                    pid = result["data"]["pics"]["pic_1"]["pid"]
                    logging.warning("上传图片成功: %s" % image_file)
                    return True, pid
            except Exception as e:
                logging.warning("上传图片失败: %s" % image_file)
                return False, None
            return False, None
        cnt = 0
        while cnt != 3:
            suc, pid = upload()
            if suc:
                return pid
        return None

class WeiboMessage:
    """微博消息类"""
    def __init__(self, text, images=None):
        self.text = text if text is not None else ""
        self.images = images
    def has_image(self):
        """是否有图片"""
        return self.images is not None and len(self.images) > 0
    def is_empty(self):
        """消息是否为空"""
        return len(self.text) == 0 and not self.has_image()
    def get_send_data(self, pids=''):
        """获取发送数据"""
        data = {
            "location": "v6_content_home",
            "appkey": "",
            "style_type": "1",
            "pic_id": pids,
            "text": self.text,
            "pdetail": "",
            "rank": "0",
            "rankid": "",
            "module": "stissue",
            "pub_type": "dialog",
            "_t": "0",
        }
        return data

    def __str__(self):
        return "text: " + self.text + os.linesep + "images: " + str(self.images)


if __name__ == '__main__':
    sw = SinaWeibo(config.USERNAME, config.PASSWORD)
    sw.login()
    # sw.send_weibo(WeiboMessage('Helo, World!', [config.CAPTCHA_FILE]))
