# encoding: UTF-8
import sys
import functools
import time
import threading
from DownloadTask import DownloadTask


class Downloader:
    """
    下载器，用于交互以及调用下载任务。
    """
    consoleLock = threading.Lock()
    taskList = []
    connectionNum = 16

    def createAndStart(self, url, filename=None, filePath=None,headers=None, cookies=None):
        task = DownloadTask(url, connectionNum=self.connectionNum,
                            filename=filename,filePath=filePath, headers=headers, cookies=cookies)
        task.preProcess()
        taskInfo = {
            'filename': task.getFilename(),
            'filePaht':task.getFilePath(),
            'fileSize': task.fileSize,
            'task': task,
            'startTime': time.time()
        }
        i = len(self.taskList)
        self.taskList.append(taskInfo)
        cb = functools.partial(self.cb, i)
        task.setCallback(cb)

        self.startTask(task)

    def startTask(self, task):
        p = threading.Thread(target=task.run)
        p.start()
        p.join()

    def cb(self, i, chunkIndex, chunkSize):
        task = self.taskList[i]['task']
        chunkNum = task.getChunkNum()
        chunkList = task.getChunkSize()
        fileSize = task.fileSize
        doneSize = 0
        for size in chunkList:
            doneSize += size[1]

        self.consoleLock.acquire()
        print '\r%.2f%% %.2fkB/S' % (doneSize / float(fileSize) * 100, doneSize / 1024 / (time.time() - self.taskList[i]['startTime'])),
        self.consoleLock.release()


if __name__ == '__main__':
    #url = ''
    url = raw_input(u'输入下载地址:'.encode(sys.stdout.encoding))
    dler = Downloader()
    dler.createAndStart(url,filePath='./download')
