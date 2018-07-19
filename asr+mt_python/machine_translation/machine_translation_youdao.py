#!/usr/bin/env python    
# -*- coding: utf-8 -*

"""
作者：易可可
注释：易可可
创建日期：2018年6月21日
最近更新：2018年6月26日 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
代码功能：
本文件是一段 python 3 代码，调用有道翻译api实现了多语言翻译，
有道翻译api将自动识别源语言是否支持，并自动输出相应的目标语言。

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import urllib.request
import json
import time
import hashlib

class YouDaoFanyi:
    # @description: 该类的主功能函数为translate()，可向有道翻译api发送GET请求，得到翻译的结果。
    def __init__(self, langTo):
        self.url = 'https://openapi.youdao.com/api/'
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.109 Safari/537.36",
        }
        self.appKey = '2de5d757cddcc6cb'  # 应用id
        self.appSecret = 'sbyMDDHj8FZF95twB6cBjzRSmaTrw5r0'  # 应用密钥
        self.langFrom = 'auto'   # 翻译前文字语言，auto为自动检查
        self.langTo = langTo     # 翻译后文字语言，auto为自动检查

    def getUrlEncodedData(self, queryText):
        # @description:将数据url编码
        # @param string queryText 待翻译的文字
        # @return: 返回url编码过的数据

        salt = str(int(round(time.time() * 1000)))  # 产生随机数 ,其实固定值也可以,不如"2"
        sign_str = self.appKey + queryText + salt + self.appSecret
        sign = hashlib.md5(sign_str.encode("utf8")).hexdigest()  
        # 要先对sign.str进行统一编码，否则报错：Unicode-objects must be encoded before hashing，参考：https://blog.csdn.net/haungrui/article/details/6959340
        payload = {
            'q': queryText,
            'from': self.langFrom,
            'to': self.langTo,
            'appKey': self.appKey,
            'salt': salt,
            'sign': sign
        }
        try:
            data = urllib.parse.urlencode(payload)
            return (data)
        except Exception as e:
            print("数据url编码失败！\n错误原因：{0}".format(e))
            return 0 

    def parseHtml(self, html):
        # @description:解析页面，输出翻译结果
        # @param html: 翻译返回的页面内容
        # @return: 解析页面成功时返回调用api的翻译结果；解析页面失败时返回0。
        try:
            data = json.loads(html.decode('utf-8'))
            translationResult = data['translation']
            if isinstance(translationResult, list):
                translationResult = translationResult[0]
                return translationResult   
        except Exception as e:
            print("解析页面失败！\n错误原因：{0}".format(e))
            return 0                 
        
    def translate(self, queryText):
        # @description:向api服务器发送请求，得到翻译结果。
        # @param string queryText 待翻译内容
        # @return: 请求服务器成功时调用parseHtml()函数解析页面，返回翻译结果；请求服务器失败时返回0。
        
        data = self.getUrlEncodedData(queryText)  # 获取url编码过的数据
        target_url = self.url + '?' + data    # 构造目标url
        try:
            request = urllib.request.Request(target_url, headers=self.headers)  # 构造请求
            response = urllib.request.urlopen(request)  # 发送请求
            return self.parseHtml(response.read())    # 解析，显示翻译结果
        except Exception as e:
            print("请求有道api服务器失败，未得到翻译结果！\n错误原因：{0}".format(e))
            return 0
        
'''测试该文件用
fanyi = YouDaoFanyi("en")
print(fanyi.translate("我是可可"))
'''