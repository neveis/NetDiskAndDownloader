# encoding: UTF-8
import os
import sys
import threading
import Queue


class MyThreadPool:

    def __init__(self, minThreadNum=5, maxThreadNum=16):
        self.minThreadNum = minThreadNum
        self.maxThreadNum = maxThreadNum
        self.curThreadNum = 0
        self._stop = False
        self._started = False
        self._valid = True
        self.threads = []
        self.q = Queue.Queue()

        # 正在工作的线程，只有在已创建线程数量小于最大线程数量时，该值才是有效的
        self._countLock = threading.Lock()
        self._workingNum = 0

        for i in range(self.minThreadNum):
            t = threading.Thread(target=self._work)
            self.threads.append(t)

        self.curThreadNum = self.minThreadNum

    def _workInc(self):
        # 只有在未达到最大线程数时有用
        if self.curThreadNum != self.maxThreadNum:
            self._countLock.acquire()
            self._workingNum += 1
            self._countLock.release()

    def _workDec(self):
        # 只有在未达到最大线程数时有用
        if self.curThreadNum != self.maxThreadNum:
            self._countLock.acquire()
            self._workingNum -= 1
            self._countLock.release()

    def start(self):
        """
        启动所有线程。
        根据启动时队列长度，最大线程数量，调整线程数
        线程数= min(启动时队列长度，最大线程数)
        """
        if self._started:
            return
        self._started = True

        qlen = self.q.qsize()
        if qlen > self.maxThreadNum:
            maxNum = self.maxThreadNum
        else:
            maxNum = qlen

        alen = maxNum - self.curThreadNum
        for i in range(alen):
            t = threading.Thread(target=self._work)
            self.threads.append(t)

        self.curThreadNum += alen

        for i in range(self.curThreadNum):
            self.threads[i].start()

    def put(self, target=None, name=None, args=(), kwargs=None):
        """
        参数仿照threading.Thread
        """
        self.q.put({
            'target': target,
            'name': name,
            'args': args,
            'kwargs': kwargs or {}
        })

        # 运行中加入任务，当前线程数小于最大线程数，并且所有线程都在工作中，那么添加新线程
        if self._started and self.curThreadNum < self.maxThreadNum and self.curThreadNum == self._workingNum:
            self.curThreadNum += 1
            t = threading.Thread(target=self._work)
            self.threads.append(t)
            t.start()

    def _work(self):
        while (not self._stop) or (not self.q.empty()):
            try:
                taskInfo = self.q.get(block=True, timeout=1)
                self._workInc()
                if taskInfo['target']:
                    taskInfo['target'](*taskInfo['args'], **taskInfo['kwargs'])
                self._workDec()
            except Queue.Empty:
                continue

    def close(self):
        """
        关闭所有线程，未完成的会等待完成，关闭后该线程池不能再使用
        """
        self._stop = True
        tlen = len(self.threads)
        for i in range(tlen):
            self.threads[i].join()
        self._valid = False
