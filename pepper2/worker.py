import logging
import traceback

import gevent
import gevent.event
import gevent.socket

import proto

def spawn(fn, *args, **kwargs):
    worker = Worker(work=fn, *args, **kwargs)
    worker.start()
    return worker

class StopWork(Exception):
    pass

class Worker(gevent.Greenlet):
    running = False
    worker_name = None
    worker_interval = 1
    count = 0

    def __init__(self, work=None, interval=None, name=None, *args, **kwargs):
        super(Worker, self).__init__(*args, **kwargs)
        self.__class__.count += 1

        if work:
            self.work = work

        if name:
            self.worker_name = name

        if not self.worker_name:
            if work:
                self.worker_name = work.__name__
            else:
                self.worker_name = self.__class__.__name__.lower()

        if interval is not None:
            self.worker_interval = interval

        self.log = logging.getLogger(self.worker_name)
        self.link(self.do_stopped)

    def stop(self):
        self.running = False
        self.kill()

    def do_started(self):
        self.log.info('Started %s worker %d', self.worker_name, self.__class__.count)
        self.running = True
        self.started()

    def started(self):
        pass

    def do_stopped(self, source):
        self.running = False
        msg = 'Stopped %s worker' % self.worker_name
        logger = self.log.info
        if not self.successful():
            msg += ': ' + str(self._exception)
            logger = self.log.error

        logger(msg)
        self.stopped()

    def stopped(self):
        pass

    def do_work(self):
        self.work()

    def work(self):
        pass

    def work_wait(self):
        if self.worker_interval:
            gevent.sleep(self.worker_interval)

    def _run(self):
        try:
            self.do_started()
            while self.running:
                self.work_wait()
                if self.running:
                    self.do_work()
        except (KeyboardInterrupt, StopWork), e:
            raise gevent.GreenletExit()

class FileWorkerBase(Worker):
    def __init__(self, file=None, *args, **kwargs):
        super(FileWorkerBase, self).__init__(*args, **kwargs)
        self._set_event = gevent.event.Event()
        self.file = file

    @property
    def file(self):
        return self._file

    @file.setter
    def file(self, f):
        self._file = f
        if f:
            self._set_event.set()
        else:
            self._set_event.clear()

    def wait_read(self):
        self._set_event.wait()
        gevent.socket.wait_read(self._file.fileno())

    def wait_write(self):
        self._set_event.wait()
        gevent.socket.wait_write(self._file.fileno())

    def read(self, size=-1):
        self.wait_read()
        return self._file.read(size)

    def write(self, str):
        self.wait_write()
        self._file.write(str)

class FileReadWorker(FileWorkerBase):
    def __init__(self, *args, **kwargs):
        super(FileReadWorker, self).__init__(*args, **kwargs)
        self.work_wait = self.wait_read

class FileWriteWorker(FileWorkerBase):
    def __init__(self, *args, **kwargs):
        super(FileWriteWorker, self).__init__(*args, **kwargs)
        self.work_wait = self.wait_write

class FileReadLineWorker(FileReadWorker):
    line = None

    def do_work(self):
        self.line = self._file.readline()
        if self.line:
            self.work()

class ProtoMsgWorker(FileReadWorker):
    msg = None

    def __init__(self, *args, **kwargs):
        super(ProtoMsgWorker, self).__init__(*args, **kwargs)

    def do_work(self):
        try:
            self.msg = proto.MsgReader().read(self._file)
            if self.msg:
                self.work()
        except (proto.BadMarker, proto.BadChecksum, proto.BadMsgType) as e:
            # These are logged in proto for now
            pass
