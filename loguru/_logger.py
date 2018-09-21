import functools
import itertools
import logging
import os
import threading
from collections import namedtuple
from inspect import isclass
from multiprocessing import current_process
from os import PathLike
from os.path import basename, normcase, splitext
from threading import current_thread

import pendulum
from colorama import AnsiToWin32

from . import _defaults
from ._catcher import Catcher
from ._fast_now import fast_now
from ._file_sink import FileSink
from ._get_frame import get_frame
from ._handler import Handler
from ._recattrs import LevelRecattr, FileRecattr, ThreadRecattr, ProcessRecattr, ExceptionRecattr

Level = namedtuple('Level', ['no', 'color', 'icon'])

start_time = fast_now()


class Logger:

    _levels = {
        "TRACE": Level(_defaults.LOGURU_TRACE_NO, _defaults.LOGURU_TRACE_COLOR, _defaults.LOGURU_TRACE_ICON),
        "DEBUG": Level(_defaults.LOGURU_DEBUG_NO, _defaults.LOGURU_DEBUG_COLOR, _defaults.LOGURU_DEBUG_ICON),
        "INFO": Level(_defaults.LOGURU_INFO_NO, _defaults.LOGURU_INFO_COLOR, _defaults.LOGURU_INFO_ICON),
        "SUCCESS": Level(_defaults.LOGURU_SUCCESS_NO, _defaults.LOGURU_SUCCESS_COLOR, _defaults.LOGURU_SUCCESS_ICON),
        "WARNING": Level(_defaults.LOGURU_WARNING_NO, _defaults.LOGURU_WARNING_COLOR, _defaults.LOGURU_WARNING_ICON),
        "ERROR": Level(_defaults.LOGURU_ERROR_NO, _defaults.LOGURU_ERROR_COLOR, _defaults.LOGURU_ERROR_ICON),
        "CRITICAL": Level(_defaults.LOGURU_CRITICAL_NO, _defaults.LOGURU_CRITICAL_COLOR, _defaults.LOGURU_CRITICAL_ICON),
    }

    _handlers_count = itertools.count()
    _handlers = {}

    _extra_class = {}

    _min_level = float("inf")
    _enabled = {}
    _activation_list = []

    _lock = threading.Lock()

    def __init__(self, extra, exception, record, lazy, ansi, depth):
        self.catch = Catcher(self)
        self._extra = extra
        self._record = record
        self._exception = exception
        self._lazy = lazy
        self._ansi = ansi
        self._depth = depth

    def opt(self, *, exception=None, record=False, lazy=False, ansi=False, depth=0):
        return Logger(self._extra, exception, record, lazy, ansi, depth)

    def bind(_self, **kwargs):
        return Logger({**_self._extra, **kwargs}, _self._exception, _self._record,
                      _self._lazy, _self._ansi, _self._depth)

    def level(self, name, no=None, color=None, icon=None):
        if not isinstance(name, str):
            raise ValueError("Invalid level name, it should be a string, not: '%s'" % type(name).__name__)

        if no is color is icon is None:
            try:
                return self._levels[name]
            except KeyError:
                raise ValueError("Level '%s' does not exist" % name)

        if name not in self._levels:
            if no is None:
                raise ValueError("Level '%s' does not exist, you have to create it by specifying a level no" % name)
            else:
                old_no, old_color, old_icon = None, '', ' '
        else:
            old_no, old_color, old_icon = self.level(name)

        if no is None:
            no = old_no

        if color is None:
            color = old_color

        if icon is None:
            icon = old_icon

        if not isinstance(no, int):
            raise ValueError("Invalid level no, it should be an integer, not: '%s'" % type(no).__name__)

        if no < 0:
            raise ValueError("Invalid level no, it should be a positive integer, not: %d" % no)

        self._levels[name] = Level(no, color, icon)

        with self._lock:
            for handler in self._handlers.values():
                handler.update_format(color)

        return self.level(name)

    def configure(self, *, sinks=None, levels=None, extra=None):
        if sinks is not None:
            self.stop()
        else:
            sinks = []

        if levels is not None:
            for params in levels:
                self.level(**params)

        if extra is not None:
            with self._lock:
                self._extra_class.clear()
                self._extra_class.update(extra)

        return [self.start(**params) for params in sinks]

    def _change_activation(self, name, status):
        if not isinstance(name, str):
            raise ValueError("Invalid name, it should be a string, not: '%s'" % type(name).__name__)

        if name != '':
            name += '.'

        with self._lock:
            activation_list = [(n, s) for n, s in self._activation_list if n[:len(name)] != name]

        parent_status = next((s for n, s in activation_list if name[:len(n)] == n), None)
        if parent_status != status and not (name == '' and status == True):
            activation_list.append((name, status))
            activation_list.sort(key=lambda x: x[0].count('.'), reverse=True)

        with self._lock:
            for n in self._enabled:
                if (n + '.')[:len(name)] == name:
                    self._enabled[n] = status

            self._activation_list[:] = activation_list

    def enable(self, name):
        self._change_activation(name, True)

    def disable(self, name):
        self._change_activation(name, False)

    def start(self, sink, *, level=_defaults.LOGURU_LEVEL, format=_defaults.LOGURU_FORMAT,
                    filter=_defaults.LOGURU_FILTER, colorize=_defaults.LOGURU_COLORIZE,
                    serialize=_defaults.LOGURU_SERIALIZE, enhance=_defaults.LOGURU_ENHANCE,
                    enqueue=_defaults.LOGURU_ENQUEUE, catch=_defaults.LOGURU_CATCH, **kwargs):
        if colorize is None and serialize:
            colorize = False

        if isclass(sink):
            sink = sink(**kwargs)
            return self.start(sink, level=level, format=format, filter=filter, colorize=colorize,
                              serialize=serialize, enhance=enhance, enqueue=enqueue,
                              catch=catch)
        elif isinstance(sink, (str, PathLike)):
            path = sink
            sink = FileSink(path, **kwargs)
            return self.start(sink, level=level, format=format, filter=filter, colorize=colorize,
                              serialize=serialize, enhance=enhance, enqueue=enqueue,
                              catch=catch)
        elif hasattr(sink, 'write') and callable(sink.write):
            if colorize is None:
                try:
                    colorize = sink.isatty()
                except Exception:
                    colorize = False

            stream = AnsiToWin32(sink).stream if (colorize and os.name == 'nt') else sink

            stream_write = stream.write
            if kwargs:
                write = lambda m: stream_write(m, **kwargs)
            else:
                write = stream_write

            if hasattr(stream, 'flush') and callable(stream.flush):
                stream_flush = stream.flush
                def writer(m):
                    write(m)
                    stream_flush()
            else:
                writer = write

            if hasattr(stream, 'stop') and callable(stream.stop):
                stopper = stream.stop
            else:
                stopper = lambda: None
        elif isinstance(sink, logging.Handler):
            def writer(m):
                r = m.record
                exc = r['exception']
                record = logging.root.makeRecord(
                    r['name'], r['level'].no, r['file'].path, r['line'], r['message'], (),
                    (exc.type, exc.value, exc.traceback) if exc else None, r['function'], r['extra']
                )
                sink.handle(record)
            stopper = sink.close
            if colorize is None:
                colorize = False
        elif callable(sink):
            if kwargs:
                writer = lambda m: sink(m, **kwargs)
            else:
                writer = sink
            stopper = lambda: None
            if colorize is None:
                colorize = False
        else:
            raise ValueError("Cannot log to objects of type '%s'." % type(sink).__name__)

        if filter is None or filter == '':
            filter_func = None
        elif isinstance(filter, str):
            parent = filter + '.'
            length = len(parent)
            def filter_func(r):
                return (r['name'] + '.')[:length] == parent
        elif callable(filter):
            filter_func = filter
        else:
            raise ValueError("Invalid filter, it should be a function or a string, not: '%s'" % type(filter).__name__)

        if isinstance(level, str):
            levelno = self.level(level).no
        elif isinstance(level, int):
            levelno = level
        else:
            raise ValueError("Invalid level, it should be an integer or a string, not: '%s'" % type(level).__name__)

        if levelno < 0:
            raise ValueError("Invalid level value, it should be a positive integer, not: %d" % levelno)

        if isinstance(format, str):
            formatter = format + '\n{exception}'
            is_formatter_dynamic = False
        elif callable(format):
            formatter = format
            is_formatter_dynamic = True
        else:
            raise ValueError("Invalid format, it should be a string or a function, not: '%s'" % type(format).__name__)

        with self._lock:
            colors = [lvl.color for lvl in self._levels.values()] + ['']

            handler = Handler(
                writer=writer,
                stopper=stopper,
                levelno=levelno,
                formatter=formatter,
                is_formatter_dynamic=is_formatter_dynamic,
                filter_=filter_func,
                colorize=colorize,
                serialize=serialize,
                enhance=enhance,
                catch=catch,
                enqueue=enqueue,
                colors=colors,
            )

            handler_id = next(self._handlers_count)
            self._handlers[handler_id] = handler
            self.__class__._min_level = min(self.__class__._min_level, levelno)

        return handler_id

    def stop(self, handler_id=None):
        with self._lock:
            if handler_id is None:
                for handler in self._handlers.values():
                    handler.stop()
                self._handlers.clear()
            else:
                try:
                    handler = self._handlers.pop(handler_id)
                except KeyError:
                    raise ValueError("There is no started handler with id '%s'" % handler_id)
                handler.stop()

            levelnos = (h.levelno for h in self._handlers.values())
            self.__class__._min_level = min(levelnos, default=float("inf"))

    @staticmethod
    @functools.lru_cache()
    def _make_log_function(level, decorated=False):

        if isinstance(level, str):
            level_id = level_name = level
        elif isinstance(level, int):
            if level < 0:
                raise ValueError("Invalid level value, it should be a positive integer, not: %d" % level)
            level_id = None
            level_name = 'Level %d' % level
        else:
            raise ValueError("Invalid level, it should be an integer or a string, not: '%s'" % type(level).__name__)

        def log_function(_self, _message, *args, **kwargs):
            if not _self._handlers:
                return

            frame = get_frame(_self._depth + 1)
            name = frame.f_globals['__name__']

            try:
                if not _self._enabled[name]:
                    return
            except KeyError:
                dotted_name = name + '.'
                for dotted_module_name, status in _self._activation_list:
                    if dotted_name[:len(dotted_module_name)] == dotted_module_name:
                        if status:
                            break
                        _self._enabled[name] = False
                        return
                _self._enabled[name] = True

            now = fast_now()

            if level_id is None:
                level_no, level_color, level_icon = level, '', ' '
            else:
                try:
                    level_no, level_color, level_icon = _self._levels[level_name]
                except KeyError:
                    raise ValueError("Level '%s' does not exist" % level_name)

            if level_no < _self._min_level:
                return

            code = frame.f_code
            file_path = normcase(code.co_filename)
            file_name = basename(file_path)
            thread = current_thread()
            process = current_process()
            diff = now - start_time
            elapsed = pendulum.Duration(microseconds=diff.microseconds)

            level_recattr = LevelRecattr(level_name)
            level_recattr.no, level_recattr.name, level_recattr.icon = level_no, level_name, level_icon

            file_recattr = FileRecattr(file_name)
            file_recattr.name, file_recattr.path = file_name, file_path

            thread_recattr = ThreadRecattr(thread.ident)
            thread_recattr.id, thread_recattr.name = thread.ident, thread.name

            process_recattr = ProcessRecattr(process.ident)
            process_recattr.id, process_recattr.name = process.ident, process.name

            if _self._exception:
                exception = ExceptionRecattr(_self._exception, decorated)
            else:
                exception = None

            record = {
                'elapsed': elapsed,
                'exception': exception,
                'extra': {**_self._extra_class, **_self._extra},
                'file': file_recattr,
                'function': code.co_name,
                'level': level_recattr,
                'line': frame.f_lineno,
                'message': _message,
                'module': splitext(file_name)[0],
                'name': name,
                'process': process_recattr,
                'thread': thread_recattr,
                'time': now,
            }

            if _self._lazy:
                args = [arg() for arg in args]
                kwargs = {key: value() for key, value in kwargs.items()}

            if _self._record:
                record['message'] = _message.format(*args, **kwargs, record=record)
            elif args or kwargs:
                record['message'] = _message.format(*args, **kwargs)

            for handler in _self._handlers.values():
                handler.emit(record, level_color, _self._ansi)

        doc = "Log 'message.format(*args, **kwargs)' with severity '%s'." % level_name
        log_function.__doc__ = doc

        return log_function

    trace = _make_log_function.__func__("TRACE")
    debug = _make_log_function.__func__("DEBUG")
    info = _make_log_function.__func__("INFO")
    success = _make_log_function.__func__("SUCCESS")
    warning = _make_log_function.__func__("WARNING")
    error = _make_log_function.__func__("ERROR")
    critical = _make_log_function.__func__("CRITICAL")

    def exception(_self, _message, *args, **kwargs):
        """Convenience method for logging an 'ERROR' with exception information."""
        logger = _self.opt(exception=True, record=_self._record,
                           lazy=_self._lazy, depth=_self._depth + 1)
        logger._make_log_function("ERROR")(logger, _message, *args, **kwargs)

    def log(_self, _level, _message, *args, **kwargs):
        """Log 'message.format(*args, **kwargs)' with severity _level."""
        logger = _self.opt(exception=_self._exception, record=_self._record,
                           lazy=_self._lazy, depth=_self._depth + 1)
        logger._make_log_function(_level)(logger, _message, *args, **kwargs)
