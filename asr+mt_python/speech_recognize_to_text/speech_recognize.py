#!/usr/bin/env python3

'''
作者：Anthony Zhang (Uberi)
注释：徐越方洲 崔冰 余扬名
最近更新：2018年7月16日 
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
代码功能：
该模块包含语音识别功能相关各类、各方法。
主要功能有：获取语音数据、调用bing api、降噪处理、音频长度截取等。
源代码参见：https://github.com/Uberi/speech_recognition/blob/master/speech_recognition/__init__.py

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

'''

import io
import os
import sys
import subprocess
import wave
import aifc
import math
import audioop
import collections
import json
import base64
import threading
import platform
import stat
import hashlib
import hmac
import time
import uuid

__author__ = "Anthony Zhang (Uberi)"
__noter__ = "Xu Yuefangzhou, Cui Bing, Yu Yangming"
__version__ = "3.8.1"
__license__ = "BSD"

try:  # 尝试使用Python 2模块
    from urllib import urlencode
    from urllib2 import Request, urlopen, URLError, HTTPError
except ImportError:  # 使用Python 3模块
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError


class WaitTimeoutError(Exception): pass
'''
自定义异常类，继承自Exception，识别过程中出现超时差错时使用
'''
class RequestError(Exception): pass
'''
自定义异常类，继承自Exception，识别过程中出现“无法获取音频”的差错时使用，并打印具体差错内容
'''
class UnknownValueError(Exception): pass
'''
自定义异常类，继承自Exception，识别过程中出现“无法识别音频内容”的差错时使用
'''

class AudioSource(object):
    '''
    下述某些类的父类
    '''
    def __init__(self): 
        raise NotImplementedError("this is an abstract class") 

    def __enter__(self):
        raise NotImplementedError("this is an abstract class")

    def __exit__(self, exc_type, exc_value, traceback):
        raise NotImplementedError("this is an abstract class")

class Microphone(AudioSource):
    """
    Creates a new ``Microphone`` instance, which represents a physical microphone on the computer. Subclass of ``AudioSource``.

    This will throw an ``AttributeError`` if you don't have PyAudio 0.2.11 or later installed.

    If ``device_index`` is unspecified or ``None``, the default microphone is used as the audio source. Otherwise, ``device_index`` should be the index of the device to use for audio input.

    A device index is an integer between 0 and ``pyaudio.get_device_count() - 1`` (assume we have used ``import pyaudio`` beforehand) inclusive. It represents an audio device such as a microphone or speaker. See the `PyAudio documentation <http://people.csail.mit.edu/hubert/pyaudio/docs/>`__ for more details.

    The microphone audio is recorded in chunks of ``chunk_size`` samples, at a rate of ``sample_rate`` samples per second (Hertz). If not specified, the value of ``sample_rate`` is determined automatically from the system's microphone settings.

    Higher ``sample_rate`` values result in better audio quality, but also more bandwidth (and therefore, slower recognition). Additionally, some CPUs, such as those in older Raspberry Pi models, can't keep up if this value is too high.

    Higher ``chunk_size`` values help avoid triggering on rapidly changing ambient noise, but also makes detection less sensitive. This value, generally, should be left at its default.
    """
    def __init__(self, device_index=None, sample_rate=None, chunk_size=1024):
        assert device_index is None or isinstance(device_index, int), "Device index must be None or an integer"
        assert sample_rate is None or (isinstance(sample_rate, int) and sample_rate > 0), "Sample rate must be None or a positive integer"
        assert isinstance(chunk_size, int) and chunk_size > 0, "Chunk size must be a positive integer"

        # set up PyAudio
        self.pyaudio_module = self.get_pyaudio()
        audio = self.pyaudio_module.PyAudio()
        try:
            count = audio.get_device_count()  # obtain device count
            if device_index is not None:  # ensure device index is in range
                assert 0 <= device_index < count, "Device index out of range ({} devices available; device index should be between 0 and {} inclusive)".format(count, count - 1)
            if sample_rate is None:  # automatically set the sample rate to the hardware's default sample rate if not specified
                device_info = audio.get_device_info_by_index(device_index) if device_index is not None else audio.get_default_input_device_info()
                assert isinstance(device_info.get("defaultSampleRate"), (float, int)) and device_info["defaultSampleRate"] > 0, "Invalid device info returned from PyAudio: {}".format(device_info)
                sample_rate = int(device_info["defaultSampleRate"])
        except Exception:
            audio.terminate()
            raise
        self.device_index = device_index
        self.format = self.pyaudio_module.paInt16  # 16-bit int sampling
        self.SAMPLE_WIDTH = self.pyaudio_module.get_sample_size(self.format)  # size of each sample
        self.SAMPLE_RATE = sample_rate  # sampling rate in Hertz
        self.CHUNK = chunk_size  # number of frames stored in each buffer

        self.audio = None
        self.stream = None

    @staticmethod
    def get_pyaudio():
        """
        Imports the pyaudio module and checks its version. Throws exceptions if pyaudio can't be found or a wrong version is installed
        """
        try:
            import pyaudio
        except ImportError:
            raise AttributeError("Could not find PyAudio; check installation")
        from distutils.version import LooseVersion
        if LooseVersion(pyaudio.__version__) < LooseVersion("0.2.11"):
            raise AttributeError("PyAudio 0.2.11 or later is required (found version {})".format(pyaudio.__version__))
        return pyaudio

    @staticmethod
    def list_microphone_names():
        """
        Returns a list of the names of all available microphones. For microphones where the name can't be retrieved, the list entry contains ``None`` instead.

        The index of each microphone's name is the same as its device index when creating a ``Microphone`` instance - if you want to use the microphone at index 3 in the returned list, use ``Microphone(device_index=3)``.
        """
        audio = Microphone.get_pyaudio().PyAudio()
        try:
            result = []
            for i in range(audio.get_device_count()):
                device_info = audio.get_device_info_by_index(i)
                result.append(device_info.get("name"))
        finally:
            audio.terminate()
        return result
		
    def __enter__(self):
        assert self.stream is None, "This audio source is already inside a context manager"
        self.audio = self.pyaudio_module.PyAudio()
        try:
            self.stream = Microphone.MicrophoneStream(
                self.audio.open(
                    input_device_index=self.device_index, channels=1, format=self.format,
                    rate=self.SAMPLE_RATE, frames_per_buffer=self.CHUNK, input=True,
                )
            )
        except Exception:
            self.audio.terminate()
            raise
        return self


    def __exit__(self, exc_type, exc_value, traceback):
        try:
            self.stream.close()
        finally:
            self.stream = None
            self.audio.terminate()

    class MicrophoneStream(object):
        def __init__(self, pyaudio_stream):
            self.pyaudio_stream = pyaudio_stream

        def read(self, size):
            return self.pyaudio_stream.read(size, exception_on_overflow=False)

        def close(self):
            try:
                # sometimes, if the stream isn't stopped, closing the stream throws an exception
                if not self.pyaudio_stream.is_stopped():
                    self.pyaudio_stream.stop_stream()
            finally:
                self.pyaudio_stream.close()


class AudioFile(AudioSource):
    """
    创建新的``filename_or_fileobject``是WAV/AIFF/FLAC格式的``AudioFile``实例. 是``AudioSource``的子类。
    若``filename_or_fileobject``是string, 则是文件系统上音频文件的路径. 否则``filename_or_fileobject`` 应该是一个类似文件的对象，例如 ``io.BytesIO``。
    WAV文件必须是 PCM/LPCM格式; 不支持WAVE_FORMAT_EXTENSIBLE 和压缩过的WAV，可能导致“未定义”等错误。
    支持AIFF和AIFF-C (压缩过的AIFF)格式。
    FLAC文件必须是原生FLAC格式; 不支持OGG-FLAC，可能导致“未定义”等错误。
    """
    def __init__(self, filename_or_fileobject):
        #@noter：崔冰 徐越方洲
        #@description:类的初始化
        #@param string filename_or_fileobject：文件名或类似文件的对象
        assert isinstance(filename_or_fileobject, (type(""), type(u""))) or hasattr(filename_or_fileobject, "read"), "Given audio file must be a filename string or a file-like object" #AudioSource必须是string或类似文件的对象
        self.filename_or_fileobject = filename_or_fileobject
        self.stream = None #数据流
        self.DURATION = None #音频时长

        self.audio_reader = None #读音频
        self.little_endian = False #大字节序 字节序：大于一个字节类型的数据在内存中的存放顺序
        self.SAMPLE_RATE = None # 波频
        self.CHUNK = None 
        self.FRAME_COUNT = None #帧数

    def __enter__(self):
        #@noter：崔冰
        #@description: 读WAV/AIFF/FLAC格式的音频文件时进行的相关配置，及互相转换格式
        assert self.stream is None, "This audio source is already inside a context manager"
        try:
            # 读wav格式音频
            self.audio_reader = wave.open(self.filename_or_fileobject, "rb")
            self.little_endian = True  # WAV是小端字节序格式
        except (wave.Error, EOFError):
            try:
                # 读aiff格式音频
                self.audio_reader = aifc.open(self.filename_or_fileobject, "rb")
                self.little_endian = False  # AIFF是大端字节序格式
            except (aifc.Error, EOFError):
                # 读FLAC格式音频
                if hasattr(self.filename_or_fileobject, "read"): #判断有无有read属性
                    flac_data = self.filename_or_fileobject.read()
                else:
                    with open(self.filename_or_fileobject, "rb") as f: flac_data = f.read()

                # 运行FLAC转换器，把FLAC数据转换成AIFF数据
                flac_converter = get_flac_converter()
                if os.name == "nt":  # 在Windows中, 指定该进程将在不显示控制台窗口的情况下启动
                    startup_info = subprocess.STARTUPINFO()
                    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # 指定`startup_info`的wShowWindow字段包含一个值
                    startup_info.wShowWindow = subprocess.SW_HIDE  # 指定隐藏控制台窗口
                else:
                    startup_info = None  # 默认启动信息
                process = subprocess.Popen([
                    flac_converter,
                    "--stdout", "--totally-silent",  #将生成的AIFF文件放入标准输出中，并确保它不与任何程序输出混合
                    "--decode", "--force-aiff-format",  #将FLAC文件解码为AIFF 文件
                    "-",  # 输入的FLAC 文件内容将在标准输入中给出
                ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, startupinfo=startup_info)
                aiff_data, _ = process.communicate(flac_data)
                aiff_file = io.BytesIO(aiff_data)
                try:
                    self.audio_reader = aifc.open(aiff_file, "rb")
                except (aifc.Error, EOFError):
                    raise ValueError("Audio file could not be read as PCM WAV, AIFF/AIFF-C, or Native FLAC; check if file is corrupted or in another format")
                self.little_endian = False  # AIFF是大端字节序格式
        assert 1 <= self.audio_reader.getnchannels() <= 2, "Audio must be mono or stereo"
        self.SAMPLE_WIDTH = self.audio_reader.getsampwidth()

        # 对于旧的Python版本，24位音频需要一些特殊处理 (应变方法：https://bugs.python.org/issue12866)
        samples_24_bit_pretending_to_be_32_bit = False
        if self.SAMPLE_WIDTH == 3:  # 24位音频
            try: audioop.bias(b"", self.SAMPLE_WIDTH, 0)  # 测试是否支持此示例宽度 
            except audioop.error:  # 此版本的audioop不支持24位音频 (可能低于Python 3.3)
                samples_24_bit_pretending_to_be_32_bit = True  # 当``AudioFile`` 实例显示是 32位, 它其实是24位
                self.SAMPLE_WIDTH = 4  # “AudioFile”实例现在应该呈现为32位数据流，因为我们将在读取时转换为32位

        self.SAMPLE_RATE = self.audio_reader.getframerate()
        self.CHUNK = 4096
        self.FRAME_COUNT = self.audio_reader.getnframes()
        self.DURATION = self.FRAME_COUNT / float(self.SAMPLE_RATE)
        self.stream = AudioFile.AudioFileStream(self.audio_reader, self.little_endian, samples_24_bit_pretending_to_be_32_bit)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        #@noter：崔冰
        #@description:关闭音频文件
        if not hasattr(self.filename_or_fileobject, "read"):  # 只有在这个类首先打开文件的时候的时候才关闭文件 (如果该文件最初是作为路径给出的)
            self.audio_reader.close()
        self.stream = None
        self.DURATION = None

    class AudioFileStream(object):
        '''
        创建``AudioFileStream``实例.将待处理的音频文件的字节序和位数进行相应处理
        '''
        def __init__(self, audio_reader, little_endian, samples_24_bit_pretending_to_be_32_bit):
        #@noter：崔冰
        #@description:类的初始化
        #@param string audio_reader 音频文件
        #@param string little_endian 小端字节序
        #@ param string samples_24_bit_pretending_to_be_32_bit 音频位数24位转换成32位
            self.audio_reader = audio_reader  # 音频文件对象 
            self.little_endian = little_endian  # 音频数据是否为小端字节序 (,处理音频之前需要把大端字节序转换成小端字节序)
            self.samples_24_bit_pretending_to_be_32_bit = samples_24_bit_pretending_to_be_32_bit  #如果音频是24位音频，但不支持24位音频，因此我们必须假装这是32位音频，并且将其即时转换

        def read(self, size=-1):
        #@noter：崔冰
        #@description: 将待处理的音频文件的字节序和位数进行相应处理
            buffer = self.audio_reader.readframes(self.audio_reader.getnframes() if size == -1 else size)
            if not isinstance(buffer, bytes): buffer = b""  # 解决方法 https://bugs.python.org/issue24608

            sample_width = self.audio_reader.getsampwidth()
            if not self.little_endian:  # 大端字节序格式转换成小端字节序
                if hasattr(audioop, "byteswap"):  # ``audioop.byteswap``只在Python 3.4 中有(python3.4+ 支持24位)
                    buffer = audioop.byteswap(buffer, sample_width)
                else:  # 手动反转每个样本的字节数，但速度较慢
                    buffer = buffer[sample_width - 1::-1] + b"".join(buffer[i + sample_width:i:-1] for i in range(sample_width - 1, len(buffer), sample_width))

            # 解决方法 https://bugs.python.org/issue12866
            if self.samples_24_bit_pretending_to_be_32_bit:  # 我们需要将样本从24位转换为32位，然后才能使用“audioop”功能处理
                buffer = b"".join(b"\x00" + buffer[i:i + sample_width] for i in range(0, len(buffer), sample_width))  # 由于我们处于小端字节序，因此我们在每个24位采样前添加一个零字节以获取32位采样
                sample_width = 4  # 确保我们将缓冲区转换为32位音频，然后将其转换为24位音频
            if self.audio_reader.getnchannels() != 1:  # 立体声音频
                buffer = audioop.tomono(buffer, sample_width, 1, 1)  # 将立体声音频转换成单声道
            return buffer


class AudioData(object):
    """
    创建一个新的``AudioData``实例，它表示单声道音频数据。
    原始音频数据由“frame_data”指定，它是代表音频采样的字节序列。 这是由PCM WAV格式使用的帧数据结构。
    每个采样的宽度（以字节为单位）由``sample_width``指定。每个“sample_width”字节组代表一个音频样本。
    假定音频数据具有“sample_rate”样本/秒（赫兹）的采样率。
    通常，这个类的实例可以从``recognizer_instance.record``或``recognizer_instance.listen``获得，或者在``recognizer_instance.listen_in_background``的回调中获得，而不是直接实例化它们。
    """
    def __init__(self, frame_data, sample_rate, sample_width):
        #@noter：崔冰 徐越方洲
        #@description:类的初始化
        #@param string frame_data 代表音频采样的字节序列
        #@param string sample_rate 采样率
        #@param string sample_width 采样宽度
        assert sample_rate > 0, "Sample rate must be a positive integer" #采样率必须是正整数
        assert sample_width % 1 == 0 and 1 <= sample_width <= 4, "Sample width must be between 1 and 4 inclusive"#采样宽度必须1——4（8bit-24bit）之间（包括1和4）
        self.frame_data = frame_data
        self.sample_rate = sample_rate
        self.sample_width = int(sample_width)

    def get_segment(self, start_ms=None, end_ms=None):
        """
        返回一个新的 ``AudioData``实例, 调整到给定的时间长度. 换句话说，返回的``AudioData``实例，具有相同的音频数据，除了从``start_ms``毫秒开始和以``end_ms``毫秒结束之外。
        如果未指定，则“start_ms”默认为音频的开头，“end_ms”默认为结尾。
        """
        #@noter：崔冰
        #@description:切割音频文件到一定的时间长度内
        #@param string start_ms：音频开始时的毫秒数
        #@param string end_ms：音频结束时的毫秒数 
        #@return 返回一个新的 ``AudioData``实例，把原音频调整到给定的时间长度
        assert start_ms is None or start_ms >= 0, "``start_ms`` must be a non-negative number"#非负数
        assert end_ms is None or end_ms >= (0 if start_ms is None else start_ms), "``end_ms`` must be a non-negative number greater or equal to ``start_ms``"#非负数，等于或大于start_ms
        if start_ms is None:
            start_byte = 0 #默认为音频的开头
        else:
            start_byte = int((start_ms * self.sample_rate * self.sample_width) // 1000)#计算start_byte
        if end_ms is None:
            end_byte = len(self.frame_data)#默认为音频的结尾
        else:
            end_byte = int((end_ms * self.sample_rate * self.sample_width) // 1000)#计算end_byte
        return AudioData(self.frame_data[start_byte:end_byte], self.sample_rate, self.sample_width)

    def get_raw_data(self, convert_rate=None, convert_width=None):
        """
        返回一个字节字符串，表示AudioData实例音频的原始帧数据。
        如果``convert_rate``已经被指定并且音频采样率不是指定的``convert_rate`` Hz，则重新采样生成的音频以达到匹配。
        如果``convert_width``已经被指定并且音频采样不是指定的``convert_width``字节，则转换生成的音频以达到匹配。
        将这些字节直接写入文件会生成有效的RAW / PCM音频文件 <https://en.wikipedia.org/wiki/Raw_audio_format>`__.
        """
        #@noter：崔冰
        #@description:将采样率和样本宽度都转换成指定数值，获得原始音频数据
        #@param string convert_rate：需转换成的采样率
        #@param string convert_width：需转换成的样本宽度
        #@return 返回一个字节字符串，表示AudioData实例音频的原始帧数据
        assert convert_rate is None or convert_rate > 0, "Sample rate to convert to must be a positive integer"#需要转换成的采样率必须是正整数
        assert convert_width is None or (convert_width % 1 == 0 and 1 <= convert_width <= 4), "Sample width to convert to must be between 1 and 4 inclusive"#需要转换成的采样宽度必须在1——4之间（包括1和4）

        raw_data = self.frame_data

        # 确保无符号的8位音频(使用无符号样本) 被处理为更高采样宽度的音频 (使用有符号样本)
        if self.sample_width == 1:
            raw_data = audioop.bias(raw_data, 1, -128)  # 从每个样本中减去128，使它们像有符号样本一样

        # 若指定了所需采样率，就重采样音频
        if convert_rate is not None and self.sample_rate != convert_rate:
            raw_data, _ = audioop.ratecv(raw_data, self.sample_width, 1, self.sample_rate, convert_rate, None)

        # 若指定了样本宽度，将样本转换成所需样本宽度，
        if convert_width is not None and self.sample_width != convert_width:
            if convert_width == 3:  # 将音频转换成24位 (解决方法 https://bugs.python.org/issue12866)
                raw_data = audioop.lin2lin(raw_data, self.sample_width, 4)  # 先把音频转换成32位
                try: audioop.bias(b"", 3, 0)  # 测试一下支不支持24位音频 (例如，Python 3.3及以下的``audioop`` 不支持样本宽度3, 但 Python 3.4+ 可以)
                except audioop.error:  # 这个版本的audioop d不支持24位音频 (可能是Python 3.3 及以下的版本)
                    raw_data = b"".join(raw_data[i + 1:i + 4] for i in range(0, len(raw_data), 4))  # 由于我们处于小端，因此我们丢弃每个32位采样的第一个字节以获得24位采样
                else:  # 24位音频完全支持，我们不需要填充任何东西
                    raw_data = audioop.lin2lin(raw_data, self.sample_width, convert_width)
            else:
                raw_data = audioop.lin2lin(raw_data, self.sample_width, convert_width)

        # 如果输出是无符号样本的8位音频，则将我们以前当作有符号样本处理的样本转换为无符号样本
        if convert_width == 1:
            raw_data = audioop.bias(raw_data, 1, 128)  # 为每个样本添加128，使其再次像无符号样本一样

        return raw_data


    def get_wav_data(self, convert_rate=None, convert_width=None):
        """
		description：该方法可以返回WAV文件内容的字节字符串，该文件包含由“AudioDATA”实例表示的音频。如果指定了’所需转换成宽度’，每个音频样本都不在‘所需转换成宽度’中，得到的音频转换为匹配宽度。如果指定“‘转换速率’”，音频采样率不是“‘转换速率’”Hz，则将所得音频重新采样以匹配。这些字节写入文件会形成一个有效的“wav”文件。
        """
		# @noter：余扬名
		# @description：得到wav数据，写入wav文件中，形成新的wav文件
		# @param string convert_rate(转换率）
		# @param string covert_width(转换宽度）
		# return wav_data 所得到的wav文件中的数据
        raw_data = self.get_raw_data(convert_rate, convert_width) #传递get_raw_data中的数据
        sample_rate = self.sample_rate if convert_rate is None else convert_rate
        sample_width = self.sample_width if convert_width is None else convert_width

        # 初始化wav文件数据
        with io.BytesIO() as wav_file:
            wav_writer = wave.open(wav_file, "wb")
            try:  # 注意无法使用内容管理器，只有python 3.4 版本置入了此功能
                wav_writer.setframerate(sample_rate) #音频采样率为样本采样率
                wav_writer.setsampwidth(sample_width) #音频宽度为样本宽度
                wav_writer.setnchannels(1)# 声道数是1
                wav_writer.writeframes(raw_data)#采样字节序列
                wav_data = wav_file.getvalue()# 获取wav数据
            finally:  # 确保resource数据清除
                wav_writer.close()
        return wav_data

    def get_aiff_data(self, convert_rate=None, convert_width=None):
        """
        返回一个字节字符串，表示包含由“AudioDATA”实例表示的音频的AIFF-C文件的内容。
        如果指定了“转角宽度”，每个音频样本都不为‘转换宽度’，则将得到的音频转换为匹配。
        如果指定“转换速率”，音频采样率不是“转换速率”Hz，则将所得音频重新采样以匹配。
        这些字节直接写入文件会形成有效的“AIFF-C文件”
        """
        # @noter：余扬名 徐越方洲
        # @description：得到aiff数据，写入AIFF文件中，形成新的AIFF文件
        # @param string convert_rate(转换率）
        # @param string covert_width(转换宽度）
        # return aiff_data 所得到的AIFF文件中的数据
        raw_data = self.get_raw_data(convert_rate, convert_width) #传递get_raw_data中的数据
        sample_rate = self.sample_rate if convert_rate is None else convert_rate
        sample_width = self.sample_width if convert_width is None else convert_width

        # AIFF 文件格式的储存方式是大端，我们需要做转化
        if hasattr(audioop, "byteswap"):  # ``audioop.byteswap`` 只适用于Python 3.4
            raw_data = audioop.byteswap(raw_data, sample_width)
        else:  #手动反转每个样本的字节，虽然效率低，但效果很好
            raw_data = raw_data[sample_width - 1::-1] + b"".join(raw_data[i + sample_width:i:-1] for i in range(sample_width - 1, len(raw_data), sample_width))

        # 初始化 AIFF-C 文件内容
        with io.BytesIO() as aiff_file:
            aiff_writer = aifc.open(aiff_file, "wb")
            try:  # 注意无法使用内容管理器，只有python 3.4 版本置入了此功能
                aiff_writer.setframerate(sample_rate)#音频采样率为样本采样率
                aiff_writer.setsampwidth(sample_width)#音频宽度为样本宽度
                aiff_writer.setnchannels(1)#声道数是1
                aiff_writer.writeframes(raw_data)#采样字节序列
                aiff_data = aiff_file.getvalue()#获取AIFF数据
            finally:  # 确保resource清除
                aiff_writer.close()
        return aiff_data

    def get_flac_data(self, convert_rate=None, convert_width=None):
        """
        返回一个字节字符串，表示包含由“AudioDATA”实例表示的音频的FLAC文件的内容。
        请注意，32位FLAC不受支持。如果音频数据是32位的，并且未指定‘转换宽度’”，则所得的FLAC将是一个24位FLAC。
        如果指定“转换速率”，音频采样率不是“转换速率”Hz，则将所得音频重新采样以匹配。
        如果指定了“转角宽度”，每个音频样本都不为“转换宽度”，则将得到的音频转换为匹配。
        将这些字节直接写入文件会形成一个FLAC文件
        """
		# @noter：余扬名
		# @description：得到flac数据，写入flac文件中，形成新的flac文件
		# @param string convert_rate(转换率）
		# @param string covert_width(转换宽度）
		# return flac_data 所得到的flac文件中的数据
        assert convert_width is None or (convert_width % 1 == 0 and 1 <= convert_width <= 3), "Sample width to convert to must be between 1 and 3 inclusive" #采样宽度必须1——3之间（包括1和3）

        if self.sample_width > 3 and convert_width is None:  # 所得的WAV数据是32位，我们的编码器不可转换到FLAC
            convert_width = 3  # 最大支持样本宽度为24位，因此我们将样本宽度限制为3

        # 运行FLAC转换器将wav数据转换为FLAC数据
        wav_data = self.get_wav_data(convert_rate, convert_width)
        flac_converter = get_flac_converter()
        if os.name == "nt":  # 在Windows上，指定该进程要在不显示控制台窗口的情况下启动。
            startup_info = subprocess.STARTUPINFO()
            startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW  # 指定 `startup_info` 中的wShowWindow 包含一个值
            startup_info.wShowWindow = subprocess.SW_HIDE  # 指定隐藏控制台窗口
        else:
            startup_info = None  #默认值
        process = subprocess.Popen([
            flac_converter,
            "--stdout", "--totally-silent",  # 将生成的FLAC文件放在STDUT中，并确保它不与任何程序输出混合。
            "--best",  # 可用的最高压缩级别
            "-",  # 输入的FLAC文件内容将在STDIN中给出。
        ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, startupinfo=startup_info)
        flac_data, stderr = process.communicate(wav_data)
        return flac_data


class Recognizer(AudioSource):
    
    def __init__(self):
        """
        创建一个新的“识别器”实例，它代表语音识别功能的集合。
        """
		 # @noter：余扬名
        # @description：类的初始化
	      
        self.energy_threshold = 300  #录音时需要考虑的最小音频能量
        self.dynamic_energy_threshold = True #动态音频能量阈值
        self.dynamic_energy_adjustment_damping = 0.15 #动态音频能量调整减幅
        self.dynamic_energy_ratio = 1.5  #动态音频能量比率
        self.pause_threshold = 0.8  #（暂停阈值） 在一个短语被认为完整之前的非语音音频秒数
        self.operation_timeout = None  # （操作间隔）在内部操作（例如，API请求）超时之前开始的秒数，或者“没有”不超时。

        self.phrase_threshold = 0.3  # 开始说话前的最小秒数，下面的值被忽略（用于过滤出点击和POP）
        self.non_speaking_duration = 0.5  # 在录音起止时保持非说话声音的秒数

        
    def record(self, source, duration=None, offset=None):
        
        # @noter：余扬名 徐越方洲
        # @description：录音的起止时间及开始的节点
        # @param string duration（录音持续的时间）
        # @param string offset（偏移量）
        # @return AudioData 返回语音数据信息
        assert isinstance(source, AudioSource),"Source must be an audio source" #必须是音频数据
        assert source.stream is not None,"Audio source must be entered before recording, see documentation for ``AudioSource``; are you using ``source`` outside of a ``with`` statement?" #录音前需有数据
        #初始化数据
        frames = io.BytesIO() #读取写入内存
        seconds_per_buffer = (source.CHUNK + 0.0) / source.SAMPLE_RATE
        elapsed_time = 0 #录音用时
        offset_time = 0
        offset_reached = False
        while True:  #  需要的块总数的循环 
            if offset and not offset_reached:
                offset_time += seconds_per_buffer #确定是否偏移
                if offset_time > offset:
                    offset_reached = True

            buffer = source.stream.read(source.CHUNK)#二进制模式读取
            if len(buffer) == 0: break
            if offset_reached or not offset:
                elapsed_time += seconds_per_buffer
                if duration and elapsed_time > duration: break

                frames.write(buffer)
        #获取帧数
        frame_data = frames.getvalue()
        frames.close()
        return AudioData(frame_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
    
    def adjust_for_ambient_noise(self, source, duration=1):
        """
        使用“source”（“AudioSource”实例）的音频动态调整能量阈值，以考虑环境噪声。旨在用环境能级校准能量阈值。应该在没有语音的音频期间使用——如果检测到任何语音，将停止早。
		“持续时间”参数是在返回之前动态调整阈值的最大秒数。该值应至少为0.5，以获得环境噪声的代表性样本。
        """
        # @noter：余扬名
        # @description：录音前检测噪音，以调整录音时的音频能量阈值
        # @param string source（在Audiosource中获取）
        # @param string duration（持续时间初始值为1）
        assert isinstance(source, AudioSource), "Source must be an audio source" #必须是音频数据
        assert source.stream is not None, "Audio source must be entered before adjusting, see documentation for ``AudioSource``; are you using ``source`` outside of a ``with`` statement?" #录音前需有数据
        assert self.pause_threshold >= self.non_speaking_duration >= 0 #暂停阈值必须大于或等于无语音输入的持续时间且二者必须大于或等于0

        seconds_per_buffer = (source.CHUNK + 0.0) / source.SAMPLE_RATE
        elapsed_time = 0

        # 直到短语开始录入前，不断调试能量阈值
        while True:
            elapsed_time += seconds_per_buffer #用时为采样用时
            if elapsed_time > duration: break
            buffer = source.stream.read(source.CHUNK)
            energy = audioop.rms(buffer, source.SAMPLE_WIDTH)  # 音频信号的能量

            # 利用非对称加权平均动态调整能量阈值
            damping = self.dynamic_energy_adjustment_damping ** seconds_per_buffer  # 说明不同块的大小和比率
            target_energy = energy * self.dynamic_energy_ratio
            self.energy_threshold = self.energy_threshold * damping + target_energy * (1 - damping)

    def snowboy_wait_for_hot_word(self, snowboy_location, snowboy_hot_word_files, source, timeout=None):
        # @noter：余扬名
        # @description：利用snowboy模型检测热词开始读取数据
        # @param string snowboy_location（检测热词文件的位置）
        # @param string snowboy_hot_word_file（用来对比数据中的词是否为热词）
        # @param string source（AudioSource中的文件数据）
        # @param string timeout（间隔时间）
        # return b"".join(frames) （探测器检测后利用join函数形成的字符串）
        # return elapsed_time（操作用时）
        # 载入热词文件(非线程安全)
        sys.path.append(snowboy_location)
        import snowboydetect #引入snowboy探测器
        sys.path.pop()#函数用于移除列表中的一个元素（默认最后一个元素），并且返回该元素的值。 
        #设置探测器
        detector = snowboydetect.SnowboyDetect(
            resource_filename=os.path.join(snowboy_location, "resources", "common.res").encode(), #将多个路径组合后返回
            model_str=",".join(snowboy_hot_word_files).encode()#将snowboy_hot_word_files中的元素组合成新的字符串
        )
        detector.SetAudioGain(1.0)
        detector.SetSensitivity(",".join(["0.4"] * len(snowboy_hot_word_files)).encode())
        snowboy_sample_rate = detector.SampleRate()

        elapsed_time = 0
        seconds_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE
        resampling_state = None

        #能够保持5秒的原始和重采样音频的buffer
        five_seconds_buffer_count = int(math.ceil(5 / seconds_per_buffer))
        frames = collections.deque(maxlen=five_seconds_buffer_count)#deque函数限制长度，超过该长度的数据会被删除
        resampled_frames = collections.deque(maxlen=five_seconds_buffer_count)#音频重采样
        while True:
            elapsed_time += seconds_per_buffer
            if timeout and elapsed_time > timeout: #操作时间和间隔时间大于预设的间隔时间时，报错
                raise WaitTimeoutError("listening timed out while waiting for hotword to be said")

            buffer = source.stream.read(source.CHUNK)
            if len(buffer) == 0: break  # 到达流的终端
            frames.append(buffer)

            # 将音频重新采样到所需采样率
            resampled_buffer, resampling_state = audioop.ratecv(buffer, source.SAMPLE_WIDTH, 1, source.SAMPLE_RATE, snowboy_sample_rate, resampling_state)
            resampled_frames.append(resampled_buffer)

            # 在重采样的音频文件上运行snowboy
            snowboy_result = detector.RunDetection(b"".join(resampled_frames))
            assert snowboy_result != -1, "Error initializing streams or reading audio data"
            if snowboy_result > 0: break  # 找到唤醒词

        return b"".join(frames), elapsed_time
		
    def listen(self, source, timeout=None, phrase_time_limit=None, snowboy_configuration=None):
        """
        Records a single phrase from ``source`` (an ``AudioSource`` instance) into an ``AudioData`` instance, which it returns.

        This is done by waiting until the audio has an energy above ``recognizer_instance.energy_threshold`` (the user has started speaking), and then recording until it encounters ``recognizer_instance.pause_threshold`` seconds of non-speaking or there is no more audio input. The ending silence is not included.

        The ``timeout`` parameter is the maximum number of seconds that this will wait for a phrase to start before giving up and throwing an ``speech_recognition.WaitTimeoutError`` exception. If ``timeout`` is ``None``, there will be no wait timeout.

        The ``phrase_time_limit`` parameter is the maximum number of seconds that this will allow a phrase to continue before stopping and returning the part of the phrase processed before the time limit was reached. The resulting audio will be the phrase cut off at the time limit. If ``phrase_timeout`` is ``None``, there will be no phrase time limit.

        The ``snowboy_configuration`` parameter allows integration with `Snowboy <https://snowboy.kitt.ai/>`__, an offline, high-accuracy, power-efficient hotword recognition engine. When used, this function will pause until Snowboy detects a hotword, after which it will unpause. This parameter should either be ``None`` to turn off Snowboy support, or a tuple of the form ``(SNOWBOY_LOCATION, LIST_OF_HOT_WORD_FILES)``, where ``SNOWBOY_LOCATION`` is the path to the Snowboy root directory, and ``LIST_OF_HOT_WORD_FILES`` is a list of paths to Snowboy hotword configuration files (`*.pmdl` or `*.umdl` format).

        This operation will always complete within ``timeout + phrase_timeout`` seconds if both are numbers, either by returning the audio data, or by raising a ``speech_recognition.WaitTimeoutError`` exception.
        """
        assert isinstance(source, AudioSource), "Source must be an audio source"
        assert source.stream is not None, "Audio source must be entered before listening, see documentation for ``AudioSource``; are you using ``source`` outside of a ``with`` statement?"
        assert self.pause_threshold >= self.non_speaking_duration >= 0
        if snowboy_configuration is not None:
            assert os.path.isfile(os.path.join(snowboy_configuration[0], "snowboydetect.py")), "``snowboy_configuration[0]`` must be a Snowboy root directory containing ``snowboydetect.py``"
            for hot_word_file in snowboy_configuration[1]:
                assert os.path.isfile(hot_word_file), "``snowboy_configuration[1]`` must be a list of Snowboy hot word configuration files"

        seconds_per_buffer = float(source.CHUNK) / source.SAMPLE_RATE
        pause_buffer_count = int(math.ceil(self.pause_threshold / seconds_per_buffer))  # number of buffers of non-speaking audio during a phrase, before the phrase should be considered complete
        phrase_buffer_count = int(math.ceil(self.phrase_threshold / seconds_per_buffer))  # minimum number of buffers of speaking audio before we consider the speaking audio a phrase
        non_speaking_buffer_count = int(math.ceil(self.non_speaking_duration / seconds_per_buffer))  # maximum number of buffers of non-speaking audio to retain before and after a phrase

        # read audio input for phrases until there is a phrase that is long enough
        elapsed_time = 0  # number of seconds of audio read
        buffer = b""  # an empty buffer means that the stream has ended and there is no data left to read
        while True:
            frames = collections.deque()

            if snowboy_configuration is None:
                # store audio input until the phrase starts
                while True:
                    # handle waiting too long for phrase by raising an exception
                    elapsed_time += seconds_per_buffer
                    if timeout and elapsed_time > timeout:
                        raise WaitTimeoutError("listening timed out while waiting for phrase to start")

                    buffer = source.stream.read(source.CHUNK)
                    if len(buffer) == 0: break  # reached end of the stream
                    frames.append(buffer)
                    if len(frames) > non_speaking_buffer_count:  # ensure we only keep the needed amount of non-speaking buffers
                        frames.popleft()

                    # detect whether speaking has started on audio input
                    energy = audioop.rms(buffer, source.SAMPLE_WIDTH)  # energy of the audio signal
                    if energy > self.energy_threshold: break

                    # dynamically adjust the energy threshold using asymmetric weighted average
                    if self.dynamic_energy_threshold:
                        damping = self.dynamic_energy_adjustment_damping ** seconds_per_buffer  # account for different chunk sizes and rates
                        target_energy = energy * self.dynamic_energy_ratio
                        self.energy_threshold = self.energy_threshold * damping + target_energy * (1 - damping)
            else:
                # read audio input until the hotword is said
                snowboy_location, snowboy_hot_word_files = snowboy_configuration
                buffer, delta_time = self.snowboy_wait_for_hot_word(snowboy_location, snowboy_hot_word_files, source, timeout)
                elapsed_time += delta_time
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)

            # read audio input until the phrase ends
            pause_count, phrase_count = 0, 0
            phrase_start_time = elapsed_time
            while True:
                # handle phrase being too long by cutting off the audio
                elapsed_time += seconds_per_buffer
                if phrase_time_limit and elapsed_time - phrase_start_time > phrase_time_limit:
                    break

                buffer = source.stream.read(source.CHUNK)
                if len(buffer) == 0: break  # reached end of the stream
                frames.append(buffer)
                phrase_count += 1

                # check if speaking has stopped for longer than the pause threshold on the audio input
                energy = audioop.rms(buffer, source.SAMPLE_WIDTH)  # unit energy of the audio signal within the buffer
                if energy > self.energy_threshold:
                    pause_count = 0
                else:
                    pause_count += 1
                if pause_count > pause_buffer_count:  # end of the phrase
                    break

            # check how long the detected phrase is, and retry listening if the phrase is too short
            phrase_count -= pause_count  # exclude the buffers for the pause before the phrase
            if phrase_count >= phrase_buffer_count or len(buffer) == 0: break  # phrase is long enough or we've reached the end of the stream, so stop listening

        # obtain frame data
        for i in range(pause_count - non_speaking_buffer_count): frames.pop()  # remove extra non-speaking frames at the end
        frame_data = b"".join(frames)

        return AudioData(frame_data, source.SAMPLE_RATE, source.SAMPLE_WIDTH)
   

    def recognize_bing(self, audio_data, key, language, show_all=False):
        # @ noter：徐越方洲
        # @ description：调用必应语音api，识别对应语种的语音数据（audio_data），并返回一种最恰当的结果
        # @ param AudioData audio_data： “audio_data”是“AudioData”的一个实例
        # @ param string key：必应语音api密钥
        # @ param language：处理的语言；以BCP-47语言标签作为值，比如“en-US”（英文）、“zh-CN”（中文）、“fr-FR”（法文），本项目中仅使用英文和中文
        # @ param show_all：show_all默认值为False，表示返回最有可能正确的语音识别内容
        # @ return result["DisplayText"]：返回最终呈现的结果（即参数中show_all=False所要求的最恰当的结果）
        """
        如果音频难识别，抛出``speech_recognition.UnknownValueError``错误；
        如果识别失败，或者未联网，抛出``speech_recognition.RequestError``错误
        """
		# assert：断言函数是声明布尔值必须为真的判定，如果发生异常就说明表达式为假
        assert isinstance(audio_data, AudioData), "Data must be audio data"  # 数据必须是语音数据（“audio_data”必须是“AudioData”的实例）
        assert isinstance(key, str), "``key`` must be a string" # key必须是string
        assert isinstance(language, str), "``language`` must be a string" # language必须是string
        
		# 获取access_token和expire_time
        access_token, expire_time = getattr(self, "bing_cached_access_token", None), getattr(self, "bing_cached_access_token_expiry", None) 
        allow_caching = True # 缓存数据
        try:
            from time import monotonic  # monotonic time 单调时间，指系统启动以后流逝的时间，使用这个是为了不被系统时钟时间变化影响
        except ImportError: # 差错处理：如果导入出错则从monotonic中导入
            try:
                from monotonic import monotonic
            except (ImportError, RuntimeError): # 差错处理：如果还是有导入错误和时间运行错误，说明monotonic time不可用，禁用缓存
                expire_time = None  
                allow_caching = False  
        if expire_time is None or monotonic() > expire_time:  # 不能缓存，credential request超时或access token过期
            # 用OAuth获取access token
            credential_url = "https://api.cognitive.microsoft.com/sts/v1.0/issueToken"
            credential_request = Request(credential_url, data=b"", headers={
                "Content-type": "application/x-www-form-urlencoded",
                "Content-Length": "0",
                "Ocp-Apim-Subscription-Key": key,
            })

            if allow_caching:#如果能缓存了则开始使用monotonic
                start_time = monotonic()

            try:
                credential_response = urlopen(credential_request, timeout=60)  # credential response时间可以更长
            except HTTPError as e: # 服务器无法完成请求
                raise RequestError("credential request failed: {}".format(e))
            except URLError as e: #没有网络连接（即没有连接到指定的服务器），或者是指定的服务器不存在
                raise RequestError("credential connection failed: {}".format(e))
            access_token = credential_response.read().decode("utf-8") 

            if allow_caching:
                self.bing_cached_access_token = access_token # access_token可获取的话，赋值给该类自己的属性变量bing_cached_access_token
                self.bing_cached_access_token_expiry = start_time + 600  # 根据 https://docs.microsoft.com/en-us/azure/cognitive-services/speech/api-reference-rest/bingvoicerecognition, token有效时长600s
        
		# 获取声波数据
        wav_data = audio_data.get_wav_data( 
            convert_rate=16000,  # 声波频率16000Hz
            convert_width=2  # 音频文件16-bit
        )

        url = "https://speech.platform.bing.com/speech/recognition/interactive/cognitiveservices/v1?{}".format(urlencode({
            "language": language,
            "locale": language,
            "requestid": uuid.uuid4(),
        }))

        if sys.version_info >= (3, 6):  # 分块传输请求（chunked-transfer requests）
            request = Request(url, data=io.BytesIO(wav_data), headers={
                "Authorization": "Bearer {}".format(access_token),
                "Content-type": "audio/wav; codec=\"audio/pcm\"; samplerate=16000", #格式：wav，编码：pcm
                "Transfer-Encoding": "chunked",
            })
        else:  # 行不通就换一种格式
            ascii_hex_data_length = "{:X}".format(len(wav_data)).encode("utf-8")
            chunked_transfer_encoding_data = ascii_hex_data_length + b"\r\n" + wav_data + b"\r\n0\r\n\r\n"
            request = Request(url, data=chunked_transfer_encoding_data, headers={
                "Authorization": "Bearer {}".format(access_token),
                "Content-type": "audio/wav; codec=\"audio/pcm\"; samplerate=16000",
                "Transfer-Encoding": "chunked",
            })

        try:
            response = urlopen(request, timeout=self.operation_timeout) #urlopen：实现对目标url的访问
        except HTTPError as e:
            raise RequestError("recognition request failed: {}".format(e))
        except URLError as e:
            raise RequestError("recognition connection failed: {}".format(e))
        response_text = response.read().decode("utf-8")
        result = json.loads(response_text)

        # 返回结果
        if show_all: return result # 如果返回所有的语音识别结果
        if "RecognitionStatus" not in result or result["RecognitionStatus"] != "Success" or "DisplayText" not in result: raise UnknownValueError() # 如果识别没成功，显示UnknownValueError()差错
        return result["DisplayText"] # 返回最终呈现的结果（即参数中show_all=False所要求的）
    

def get_flac_converter():
    
    # @ noter：徐越方洲
    # @ description：获取FLAC（即Free Lossless Audio Codec，无损音频压缩编码）转换器
    # @ return flac_converter：FLAC converter（FLAC转换器）的绝对路径（如果没有找到，报错OSError）
    
    flac_converter = shutil_which("flac")  # 查找有没有已安装的flac converter
    if flac_converter is None:  # 如果之前没有安装
        base_path = os.path.dirname(os.path.abspath(__file__))  # 本文件的绝对路径的父目录
        system, machine = platform.system(), platform.machine() # 获取操作系统类型、环境
        # 根据系统找flac_converter的绝对路径
        if system == "Windows" and machine in {"i686", "i786", "x86", "x86_64", "AMD64"}:
            flac_converter = os.path.join(base_path, "flac-win32.exe") 
        
        #下面这一段内容是指不同系统中flac_converter的绝对路径，鉴于现在是在windows上运行的，这些可以省去
        #elif system == "Darwin" and machine in {"i686", "i786", "x86", "x86_64", "AMD64"}:
        #    flac_converter = os.path.join(base_path, "flac-mac")
        #elif system == "Linux" and machine in {"i686", "i786", "x86"}:
        #    flac_converter = os.path.join(base_path, "flac-linux-x86")
        #elif system == "Linux" and machine in {"x86_64", "AMD64"}:
        #    flac_converter = os.path.join(base_path, "flac-linux-x86_64")
        
        else:  # 没有找到可用的FLAC conversion
            raise OSError("FLAC conversion utility not available - consider installing the FLAC command line application by running `apt-get install flac` or your operating system's equivalent")
        
    # mark FLAC converter as executable if possible
    try:
        # handle known issue when running on docker:
        # run executable right after chmod() may result in OSError "Text file busy"
        # fix: flush FS with sync
        if not os.access(flac_converter, os.X_OK):
            stat_info = os.stat(flac_converter)
            os.chmod(flac_converter, stat_info.st_mode | stat.S_IEXEC)
            if 'Linux' in platform.system():
                os.sync() if sys.version_info >= (3, 3) else os.system('sync')

    except OSError: pass
	
    return flac_converter # FLAC converter（FLAC转换器）的绝对路径


def shutil_which(pgm):
    
    # @ noter：徐越方洲
    # @ description：查找某一个文件pgm的路径
    # @ param pgm：文件
    # @ return p：返回pgm所在的路径p（如果存在）

    """Python 2 compatibility: backport of ``shutil.which()`` from Python 3"""
    path = os.getenv('PATH') # os.getenv获取一个环境变量,如果没有返回none 
    for p in path.split(os.path.pathsep): # 分割各个环境变量路径（os.path.pathsep：路径分隔符）
        p = os.path.join(p, pgm) # 与pgm组合
        if os.path.exists(p) and os.access(p, os.X_OK): # 如果存在，就返回路径p
            return p


# ===============================
#  backwards compatibility shims
# ===============================

WavFile = AudioFile  # WavFile was renamed to AudioFile in 3.4.1
def recognize_api(self, audio_data, client_access_token, language="en", session_id=None, show_all=False):
    wav_data = audio_data.get_wav_data(convert_rate=16000, convert_width=2)
    url = "https://api.api.ai/v1/query"
    while True:
        boundary = uuid.uuid4().hex
        if boundary.encode("utf-8") not in wav_data: break
    if session_id is None: session_id = uuid.uuid4().hex
    data = b"--" + boundary.encode("utf-8") + b"\r\n" + b"Content-Disposition: form-data; name=\"request\"\r\n" + b"Content-Type: application/json\r\n" + b"\r\n" + b"{\"v\": \"20150910\", \"sessionId\": \"" + session_id.encode("utf-8") + b"\", \"lang\": \"" + language.encode("utf-8") + b"\"}\r\n" + b"--" + boundary.encode("utf-8") + b"\r\n" + b"Content-Disposition: form-data; name=\"voiceData\"; filename=\"audio.wav\"\r\n" + b"Content-Type: audio/wav\r\n" + b"\r\n" + wav_data + b"\r\n" + b"--" + boundary.encode("utf-8") + b"--\r\n"
    request = Request(url, data=data, headers={"Authorization": "Bearer {}".format(client_access_token), "Content-Length": str(len(data)), "Expect": "100-continue", "Content-Type": "multipart/form-data; boundary={}".format(boundary)})
    try: response = urlopen(request, timeout=10)
    except HTTPError as e: raise RequestError("recognition request failed: {}".format(e.reason))
    except URLError as e: raise RequestError("recognition connection failed: {}".format(e.reason))
    response_text = response.read().decode("utf-8")
    result = json.loads(response_text)
    if show_all: return result
    if "status" not in result or "errorType" not in result["status"] or result["status"]["errorType"] != "success":
        raise UnknownValueError()
    return result["result"]["resolvedQuery"]


Recognizer.recognize_api = classmethod(recognize_api)  # API.AI Speech Recognition is deprecated/not recommended as of 3.5.0, and currently is only optionally available for paid plans
