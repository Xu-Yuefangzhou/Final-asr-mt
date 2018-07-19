#!/usr/bin/env python3
# -*- coding: utf-8 -*-

'''
作者：徐越方洲 崔冰
创建日期：2018年6月21日
最近更新：2018年7月17日 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
代码功能：
该模块包含两个主要功能：
1.从麦克风输入语音（多个语种），同时生成音频文件
2.调用必应语音api进行语音识别（多个语种），转化成文字

该模块只包含一个类 RecognizeToText。
与speech_recognize.py模块分离的原因主要是因为该模块由小组成员自主撰写，而speech_recognize.py为参考的网络代码。
speech_recognize.py位于同文件夹下
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

'''

from os import path
from . import speech_recognize as sr #从同文件下导入speech_recognize.py

class RecognizeToText(object):
    #这个类的功能主要包括从麦克风输入语音和识别多语种音频文件并将其转换成文字
    def __init__(self,in_language):
        # @description: 类的初始化
        # @param string in_language: 从麦克风输入的音频语种
        self.BING_KEY="b7989012bb924e538c349b5814e94b72" # 密钥，用在各识别、输出方法中
        self.in_language=in_language #从麦克风输入的音频语种
        self.supported_languages = {         #必应语音api支持语言，可参考：https://docs.microsoft.com/zh-cn/azure/cognitive-services/speech/api-reference-rest/supportedlanguages#interactive-and-dictation-mode
            'ar-EG' : '阿拉伯语（埃及）',
            'ca-ES' : '加泰罗尼亚语（西班牙）',
            'da-DK' : '丹麦语（丹麦）',
            'de-DE' : '德语（德国）',
            'en-AU' : '英语（澳大利亚）',
            'en-CA' : '英语（加拿大）',
            'en-GB' : '英语（英国）',
            'en-IN' : '英语（印度）',
            'en-NZ' : '英语（新西兰）',
            'en-US' : '英语（美国）',
            'es-ES' : '西班牙语（西班牙）',
            'es-MX' : '西班牙语（墨西哥）',
            'fi-FI' : '芬兰语（芬兰）',
            'fr-CA' : '法语（加拿大）',
            'fr-FR' : '法语（法国）',
            'hi-IN' : '印度语（印度）',
            'it-IT' : '意大利语（意大利）',
            'ja-JP' : '日语（日本）',
            'ko-KR' : '韩语（韩国）',
            'nb-NO' : '挪威语（挪威）',
            'nl-NL' : '荷兰语（荷兰）',
            'pl-PL' : '波兰语（波兰）',
            'pt-BR' : '葡萄牙语（巴西）',
            'pt-PT' : '葡萄牙语（葡萄牙）',
            'ru-RU' : '俄语（俄罗斯）',
            'sv-SE' : '瑞典语（瑞典）',
            'zh-CN' : '简体中文（中国）',
            'zh-HK' : '繁体中文（中国香港）',
            'zh-TW' : '繁体中文（中国台湾）',
        }
        
    def print_supported_languages (self):
        # @description:打印出api支持语言代码及相应意义的列表。
        # @return:必应语音api支持语言代码及相应意义的列表。
        codes = []
        for k,v in self.supported_languages.items():
            codes.append('\t'.join([k, '=', v]))
        return '\n'.join(codes)
        
    def judge_languages (self):
        # @description:检验语音语言是否支持。
        # @return:支持时返回结果1，不支持时返回结果0。
        if self.in_language not in self.supported_languages.keys():
            print ('对不起，此API无法识别该种语言：', self.in_language)
            print ('请在下列的这些语言中选择语音语言：')
            return 0
        else:
            return 1
    
    def get_audio_file(self):
        # @description:从麦克风输入语音，识别语音，生成语音文件temp.wav，放在audio文件夹下
        r = sr.Recognizer() #创建Recognizer类的实例
        m = sr.Microphone() #创建Microphone类的实例
        try:
            print("请保持安静，正在打开麦克风……")
            with m as source: r.adjust_for_ambient_noise(source)
            print("请开始录音，停顿后结束录音……")
            with m as source: audio = r.listen(source)
            print("已检测到音频，正在生成音频文件，请稍等……")
            #写入并生成WAV文件
            with open("./audio/temp.wav", "wb") as f: 
                f.write(audio.get_wav_data())           
            print ("音频文件 temp.wav 已生成！\n") 	
        		 
        except Exception as e:
            pass
        
    def recognize(self):
        # @description: 对音频文件进行语音识别，返回语音文字
        # @return writetext：语音识别结果，即语音文字
        try:        
            r = sr.Recognizer()       #创建Recognizer类的实例
            audio_file = path.join(path.dirname(path.dirname(path.realpath(__file__))),'audio','temp.wav')        
            with sr.AudioFile(audio_file) as source: # 创建AudioFile实例
                audio = r.record(source)   #调用record方法返回AudioData，这里的audio是AudioData的实例，即语音数据信息（包括声波频率等）
            writetext = r.recognize_bing(audio,language=self.in_language, key=self.BING_KEY) #语音识别结果  
            return writetext #返回识别结果
        except sr.UnknownValueError: #识别过程中出现“无法识别音频内容”的差错
            print ("抱歉，音频内容无法识别。")
        except sr.RequestError as e: #识别过程中出现“无法获取语音识别服务”的差错，并打印具体差错内容
            print ("抱歉，语音识别服务获取失败。; {0}".format(e))
        

