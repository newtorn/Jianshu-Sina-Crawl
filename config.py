"""
配置文件
"""

# 微博账户设置
USERNAME = "xxxxxxxxxxx"                    # 微博账号
PASSWORD = "xxxxxxxxxxx"                    # 微博密码


# 发送设置
SEND_TIME = "21:04"                         # 发送微博时间（24小时格式，不能省略前导0，比如`07:31`不能写成`7:31`）
MAX_IMAGES = 9                              # 允许上传图片的最大数量。如果设置为0，则不上传图片。
ADD_WATERMARK = False                       # 是否添加图片水印，为True时，应设置以下两项
WATERMARK_NIKE = "@娜娜姐"                   # 水印名称
WATERMARK_URL = "www.nana.com"              # 水印链接


# 文章设置
ARTICLE_COUNT = 3                           # 爬取每个作者文章数，一篇文章生成一个词云图


# 文件设置
CAPTCHA_FILE = './temp/captcha.png'         # 微博验证码保存路径
AVATAR_FILE = './temp/avatar.jpeg'          # 简书作者头像保存路径
WL_FONT_FILE = './assets/MSYH.TTF'          # 词云字体路径
WL_BG_FILE = './assets/wordcloud_bg.png'    # 词云背景图路径
TEMP_DIR = './temp/'                        # 临时文件目录


# 系统设置
WBCLIENT = 'ssologin.js(v1.4.19)'           # 微博版本
SQLITE3_PATH = './author_urls.sqlite3'      # sqlite3数据库文件路径