#!/usr/bin/env python    
# -*- coding: utf-8 -*

"""
作者：易可可
注释：易可可
创建日期：2018年6月21日
最近更新：2018年6月26日 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
代码功能：
本文件是一段 python 3 代码，调用微软必应翻译api实现了多语言翻译，
必应翻译api将自动识别源语言是否支持，并输出相应的中文翻译。
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import http.client, urllib.parse, uuid, json

class BingFanyi:
    # @description: 该类的主功能函数为translate()，可向必应翻译api发送POST请求，得到翻译的结果。
     def __init__(self, ToLanguage):
        # @param string ToLanguage 目标语言相应代码
        self.host = 'api.cognitive.microsofttranslator.com'
        self.path = '/translate?api-version=3.0'
        self.subscriptionKey = '28e9da06f8934771acf00c01029d2f9d'   #应用subscriptionKey，失效请自行申请更换
        self.headers = {
            'Ocp-Apim-Subscription-Key': self.subscriptionKey,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        self.ToLanguage = ToLanguage  
        self.supported_languages = { 
        #必应翻译api支持语言，可参考：http://msdn.microsoft.com/en-us/library/hh456380.aspx
            'ar' : ' Arabic',
            'bg' : 'Bulgarian',
            'ca' : 'Catalan',
            'zh-CHS' : 'Chinese (Simplified)',
            'zh-CHT' : 'Chinese (Simplified)',
            'zh-Hans': 'Chinese (Simplified)',
            'cs' : 'Czech',
            'da' : 'Danish',
            'nl' : 'Dutch',
            'en' : 'English',
            'et' : 'Estonian',
            'fi' : 'Finnish',
            'fr' : 'French',
            'de' : 'German',
            'el' : 'Greek',
            'ht' : 'Haitian Creole',
            'he' : 'Hebrew',
            'hi' : 'Hindi',
            'hu' : 'Hungarian',
            'id' : 'Indonesian',
            'it' : 'Italian',
            'ja' : 'Japanese',
            'ko' : 'Korean',
            'lv' : 'Latvian',
            'lt' : 'Lithuanian',
            'mww' : 'Hmong Daw',
            'no' : 'Norwegian',
            'pl' : 'Polish',
            'pt' : 'Portuguese',
            'ro' : 'Romanian',
            'ru' : 'Russian',
            'sk' : 'Slovak',
            'sl' : 'Slovenian',
            'es' : 'Spanish',
            'sv' : 'Swedish',
            'th' : 'Thai',
            'tr' : 'Turkish',
            'uk' : 'Ukrainian',
            'vi' : 'Vietnamese',
         }
     
     def print_supported_languages (self):
        # @description:用户输入的目标语言不支持时，打印出api支持语言代码及相应意义的列表。
        # @return:必应翻译api支持语言代码及相应意义的列表。
        codes = []
        for k,v in self.supported_languages.items():
            codes.append('\t'.join([k, '=', v]))
        return '\n'.join(codes)
    
     def judge_to_languages (self):
        # @description:检验译语是否支持。
        # @return:译语支持时返回结果1，不支持时返回结果0。
        if self.ToLanguage not in self.supported_languages.keys():
            print ('对不起，此API无法翻译成该种语言：', self.ToLanguage)
            print ('请在下列的这些语言中选择您想要的译语：')
            return 0
        else:
            return 1
            
    
     def translate (self, queryText):
        # @description:向api服务器发送请求，得到翻译结果。
        # @param string queryText 待翻译内容
        # @return:若请求微软api服务器失败，则返回0。
        requestBody = [{
            'Text' : queryText,
        }]
        queryText = json.dumps(requestBody, ensure_ascii=False).encode('utf-8')
        try:
            conn = http.client.HTTPSConnection(self.host)
            conn.request ("POST", self.path + "&to=" + self.ToLanguage, queryText, self.headers)
            response = conn.getresponse ()
            result = response.read () 
            output = json.dumps(json.loads(result.decode('utf-8')), indent=4, ensure_ascii=False)
            d=eval(output)                  #eval()函数用来执行一个字符串表达式，并返回表达式的值。
            translationResult = d[0]['translations'][0]['text']
            if isinstance(translationResult, str):
                return translationResult
        except Exception as e:
            print("请求微软api服务器失败，未得到翻译结果！\n错误原因：{0}".format(e))
            return 0