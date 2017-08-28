# encoding: UTF-8
import math
import threading
import re
import os
from urllib import unquote
from contextlib import closing
import requests
from MyThreadPool import MyThreadPool

# 1.不一定支持HEAD，可能有多次重定向
#   stream=True，使用GET


class GetError(Exception):
    """
    """


class DownloadTask:

    def __init__(self, url, connectionNum=16, callback=None, filename=None, filePath=None, headers=None, cookies=None):
        self.fileSize = 0
        self.filename = filename or ''
        self.filePath = filePath or './'
        if not os.path.exists(self.filePath):
            os.mkdir(self.filePath)
            
        self._cdname = None
        self._urlname = None
        self.url = url
        self._connectionNum = connectionNum
        self._supportContinue = None
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.101 Safari/537.36'}
        self.cookies = cookies or {}
        self._callback = callback
        self._chunkSize = []
        self._chunkNum = 0
        self._init = False

    def setPath(self,filePath):
        self.filePath = filePath
        if not os.path.exists(self.filePath):
            os.mkdir(self.filePath)

    def getFilePath(self):
        return self.filePath

    def getChunkNum(self):
        return self._chunkNum

    def getChunkSize(self, index=-1):
        """
        返回第index个块的大小(块大小，已下载大小)
        index=-1表示返回所有块
        """
        if index >= 0 and index < self._chunkNum:
            return tuple(self._chunkSize[index])
        elif index == -1:
            return [tuple(x) for x in self._chunkSize]
        else:
            return []

    def setCallback(self, callback):
        """
        用于下载时的回调函数，以块序号以及块大小作为参数
        callback(chunkIndex,chunkSize)
        """
        self._callback = callback

    def supportContinue(self):
        return self._supportContinue

    def preProcess(self):
        """
        对链接预处理，可以获得的信息有文件名，文件大小，以及是否支持续传
        """
        isSupport = False
        headers = self.headers.copy()

        headers['Range'] = 'bytes=0-4'
        try:
            with closing(requests.get(self.url, headers=headers,
                                      stream=True, cookies=self.cookies, timeout=10)) as response:
                # response = requests.get(self.url, headers=headers,
                # stream=True, cookies=self.cookies, timeout=10)
                if not self.filename:
                    if 'Content-Disposition' in response.headers.keys():
                        cd = response.headers['Content-Disposition']
                    elif 'content-disposition' in response.headers.keys():
                        cd = response.headers['content-disposition']
                    else:
                        cd = ''
                    filenamePattern = re.compile(r'filename="?(.*?)"?$')
                    r = re.findall(filenamePattern, cd)
                    if len(r):
                        if r[0]:
                            # 转换成Unicode，编码是utf-8
                            self._cdname = unquote(r[0]).decode('utf-8')

                if response.status_code == 206:
                    isSupport = True
                    lengthPattern = re.compile(r'bytes 0-4/(\d+)')
                    r = re.findall(
                        lengthPattern, response.headers['Content-Range'])
                    if len(r):
                        self.fileSize = int(r[0])
                    else:
                        self.fileSize = 0
                elif response.status_code == 200:
                    self.fileSize = int(response.headers['Content-Length'])
        except requests.exceptions.Timeout:
            self.supportContinue()

        r = self.url.split('?')
        if len(r):
            self._urlname = r[0].split('/')[-1]

        self.setFilename(self.filename or self._cdname or self._urlname)

        print self.filename
        # print self.fileSize

        self._supportContinue = isSupport
        self._init = True

    def setFilename(self, filename):
        self.filename = filename

    def getFilename(self):
        return self.filename

    def downloadThread(self, chunkIndex, start, end, threadPool=None):
        headers = self.headers.copy()
        headers['Range'] = 'bytes=%d-%d' % (start, end)

        try:
            with closing(requests.get(self.url, headers=headers,
                                      stream=True, cookies=self.cookies, timeout=5)) as res:
                # res = requests.get(url, headers=headers,
                # stream=True, cookies=self.cookies, timeout=5)
                count = 0

                if int(res.headers['Content-Length']) != (end - start + 1):
                    raise GetError()

                # 要以读写方式打开
                with open(os.path.join(self.filePath,self.filename), 'rb+') as f:
                    f.seek(start, 0)
                    # f.write(res.content)
                    for data in res.iter_content(chunk_size=1024 * 1):
                        self._chunkSize[chunkIndex][1] += len(data)
                        if self._callback:
                            self._callback(
                                chunkIndex, tuple(self._chunkSize[chunkIndex]))
                        count += len(data)
                        f.write(data)

                if __name__ == '__main__':
                    lock.acquire()
                    if count != (end - start + 1):
                        print start, '-', end, ' count ', count, ' download error'

                    else:
                        print start, '-', end, ' count ', count, ' done'
                    lock.release()

        except requests.exceptions.Timeout:
            self._chunkSize[chunkIndex][1] = 0
            if threadPool:
                threadPool.put(target=self.downloadThread,
                               args=(chunkIndex, start, end, threadPool))
            else:
                self.downloadThread(chunkIndex, start, end, threadPool=None)
        except GetError:
            # print res.text
            self._chunkSize[chunkIndex][1] = 0
            if threadPool:
                threadPool.put(target=self.downloadThread,
                               args=(chunkIndex, start, end, threadPool))
            else:
                self.downloadThread(chunkIndex, start, end, threadPool=None)

    def multiDownload(self):
        conNum = self._connectionNum

        # 先创建一个文件
        f = open(os.path.join(self.filePath,self.filename), 'w')
        f.close()

        # 每个线程下载的内容不能太小，否者HTTP头可能比实际数据还大
        minPreSize = 2 * 1000  # 2kB
        if minPreSize * conNum > self.fileSize:
            conNum = int(math.ceil(self.fileSize / float(minPreSize)))

        # 向上取整，保证n线程能下载完
        preSize = int(math.ceil(self.fileSize / float(conNum)))

        self._chunkNum = conNum
        self._chunkSize = [0] * conNum

        threadPool = MyThreadPool()

        for i in range(conNum):
            start = i * preSize
            end = (i + 1) * preSize - 1
            if end > self.fileSize - 1:
                end = self.fileSize - 1

            self._chunkSize[i] = [end - start + 1, 0]
            threadPool.put(target=self.downloadThread,
                           args=(i, start, end, threadPool))

        threadPool.start()
        threadPool.close()

    def download(self):
        self._chunkNum = 1
        self._chunkSize = [[self.fileSize, 0]]
        try:
            with closing(requests.get(self.url, headers=self.headers,
                                      stream=True, cookies=self.cookies, timeout=10)) as res:
                # res = requests.get(self.url, headers=self.headers,
                # stream=True, cookies=self.cookies, timeout=10)
                count = 0

                with open(os.path.join(self.filePath,self.filename), 'wb') as f:
                    for data in res.iter_content(chunk_size=1024 * 20):
                        self._chunkSize[0][1] += self._chunkSize[0][1]
                        if self._callback:
                            self._callback(0, self._chunkSize[0])
                        count += len(data)
                        f.write(data)

        except requests.exceptions.Timeout:
            self.download()

    def run(self):
        if not self._init:
            self.preProcess()
        if self._supportContinue:
            self.multiDownload()
        else:
            self.download()


if __name__ == '__main__':
    lock = threading.Lock()

    def cb(i, s):
        # lock.acquire()
        print i, s
        # lock.release()
    turl = ''

    dl = DownloadTask(turl)
    dl.setCallback(cb)
    dl.run()
