#!/usr/bin/env python    
# -*- coding: utf-8 -*

'''
作者：徐越方洲 易可可
注释：徐越方洲 易可可
创建日期：2018年6月21日
最近更新：2018年7月18日 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
代码功能：
本文件调用了语音识别模块和2个机器翻译（微软、有道）模块，主要实现以下四大功能：
1. 从麦克风输入语音（多语种）并转化为音频文件；
2. 将音频文件识别为文字；
3. 翻译文字，生成两种翻译结果（有道、必应）；
4. 用户可以选择有道、必应的翻译版本，或者自己润色后的版本，作为最终的翻译结果。
最终翻译结果将呈现在本文件夹的translation.txt文件中。

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''


import speech_recognize_to_text.recognize_to_text as rt #导入recognize_to_text文件夹下的recognize_to_text文件，即导入RecognizeToText类
import machine_translation.machine_translation_bing as mtbing
import machine_translation.machine_translation_youdao as mtyoudao


while True:
    
    print("注意：请先在cmd中运行“pip install pyaudio”，安装好pyaudio后，才能成功执行程序并从麦克风录入语音。") # 提示信息
    #输入语音语言
    in_language = input("请选择您即将输入语音的源语言代号（如简体中文'zh-CN'，英语（美国）'en-US'，法语（法国）'fr-FR'等）: ").strip()
    r = rt.RecognizeToText(in_language)
    
    #判断输入的语言是否正确
    in_lang = r.judge_languages()
    if (in_lang==0): #如果输入的语言代号不正确，则打印必应语音api可使用的语言列表
        print (r.print_supported_languages())
        continue
    elif (in_lang==1): #输入的语言代号正确
        r.get_audio_file() #从麦克风中输入语音，并生成wav格式的音频temp.wav，存放在audio文件夹下
        content = r.recognize() #识别temp.wav文件，音频转文字 
        print("您的语音识别结果为：\n" + content)
        
        while True:
            to_language = input("\n请输入待识别语音的译入语代号（如简体中文'zh-Hans'，英语'en'，法语'fr'等）：")
            bing = mtbing.BingFanyi(to_language) #调用必应翻译api进行翻译
            
            youdao = mtyoudao.YouDaoFanyi(to_language) #调用有道翻译api进行翻译
            to = bing.judge_to_languages()
            if (to==0): 
                print (bing.print_supported_languages())#如果输入语言无法识别，打印语言列表
                continue
            elif (to==1):
                translation_bing = bing.translate(content)
                translation_youdao = youdao.translate(content)
                print ("\n必应翻译结果：\n", translation_bing, "\n有道翻译结果：\n", translation_youdao)#打印两个翻译结果
                
                while True:   #用户选择翻译结果             
                    trans = input ("\n看上了哪个？\n（1.必应 2.有道 3.翻的什么玩意儿，让我来）：")
                    if (trans=="1"):
                        with open('translation.txt','w') as f: 
                            f.write(translation_bing)   # 写入必应翻译结果
                        print("写入完成！\n")
                        break
                    elif (trans=="2"):
                        with open('translation.txt','w') as f: 
                            f.write(translation_youdao) 
                        print("翻译结果已写入 translation.txt 文件！\n")
                        break
                    elif (trans=="3"): #用户自行翻译
                        translation_self = input("\n请输入您的译文：\n")
                        with open('translation.txt','w') as f: 
                            f.write(translation_self) 
                        print("翻译结果已写入 translation.txt 文件！\n")
                        break
                    else:
                        print("请输入1、2或3")
                        continue
                break
        #是否再次进行
        again=input("没玩够？（1.继续 2.不玩了）：")
        if (again=="1"): 
            continue
        elif (again=="2"):
            print ("\n谢谢使用，白白！")
            break
        else:
            print ("\n您输入出错，我们缘分已尽，白白！")        
            break
    
    