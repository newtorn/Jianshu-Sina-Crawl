import itchat
import config
from gevent.queue import Queue

@itchat.msg_register(itchat.content.TEXT)
def text_reply(msg):
    if msg['ToUserName'] == 'filehelper':
        itchat.send('backend received it', toUserName='filehelper')



if __name__ == "__main__":
    itchat.auto_login(hotReload=True)
    itchat.send('Hello, filehelper', toUserName='filehelper')
    itchat.send_image(config.CAPTCHA_FILE, toUserName='filehelper')
    itchat.run()