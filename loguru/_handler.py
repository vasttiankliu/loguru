import json
import multiprocessing
import sys
import threading
import traceback

import ansimarkup


class StrRecord(str):
    __slots__ = ('record', )


class Handler:

    def __init__(self, *, writer, stopper, levelno, format_, filter_, colored, serialized, enhanced, wrapped, queued, colors=[]):
        self.writer = writer
        self.stopper = stopper
        self.levelno = levelno
        self.format = format_
        self.filter = filter_
        self.colored = colored
        self.serialized = serialized
        self.enhanced = enhanced
        self.wrapped = wrapped
        self.queued = queued
        self.decolorized_format = self.decolorize(format_)
        self.precolorized_formats = {}
        self.lock = threading.Lock()
        self.queue = None
        self.thread = None

        if colored:
            for color in colors:
                self.update_format(color)

        if queued:
            self.queue = multiprocessing.SimpleQueue()
            self.thread = threading.Thread(target=self.queued_writer, daemon=True)
            self.thread.start()

    @staticmethod
    def serialize(text, record, exception):
        serializable = {
            'text': text,
            'record': {
                'elapsed': dict(repr=record['elapsed'], seconds=record['elapsed'].total_seconds()),
                'exception': exception,
                'extra': record['extra'],
                'file': dict(name=record['file'].name, path=record['file'].path),
                'function': record['function'],
                'level': dict(icon=record['level'].icon, name=record['level'].name, no=record['level'].no),
                'line': record['line'],
                'message': record['message'],
                'module': record['module'],
                'name': record['name'],
                'process': dict(id=record['process'].id, name=record['process'].name),
                'thread': dict(id=record['thread'].id, name=record['thread'].name),
                'time': dict(repr=record['time'], timestamp=record['time'].float_timestamp),
            }
        }

        return json.dumps(serializable, default=str)

    @staticmethod
    def make_ansimarkup(color):
        color = ansimarkup.parse(color)
        custom_markup = dict(level=color, lvl=color)
        am = ansimarkup.AnsiMarkup(tags=custom_markup)
        return am

    @staticmethod
    def decolorize(format_):
        am = Handler.make_ansimarkup('')
        return am.strip(format_)

    @staticmethod
    def colorize(format_, color):
        am = Handler.make_ansimarkup(color)
        return am.parse(format_)

    def update_format(self, color):
        if not self.colored or color in self.precolorized_formats:
            return
        self.precolorized_formats[color] = self.colorize(self.format, color)

    def handle_error(self, record=None):
        if not self.wrapped:
            raise

        if not sys.stderr:
            return

        ex_type, ex, tb = sys.exc_info()

        try:
            sys.stderr.write('--- Logging error in Loguru ---\n')
            sys.stderr.write('Record was: ')
            try:
                sys.stderr.write(str(record))
            except Exception:
                sys.stderr.write('/!\\ Unprintable record /!\\')
            sys.stderr.write('\n')
            traceback.print_exception(ex_type, ex, tb, None, sys.stderr)
            sys.stderr.write('--- End of logging error ---\n')
        except OSError:
            pass
        finally:
            del ex_type, ex, tb

    def emit(self, record, level_color=None, ansi_message=False):
        try:
            if self.levelno > record['level'].no:
                return

            if self.filter is not None:
                if not self.filter(record):
                    return

            if ansi_message:
                preformatted_message = self.format.format_map(record)

                if self.colored:
                    formatted = self.colorize(preformatted_message, level_color)
                else:
                    formatted = self.decolorize(preformatted_message)
            else:
                if self.colored:
                    precomputed_format = self.precolorized_formats[level_color]
                else:
                    precomputed_format = self.decolorized_format

                formatted = precomputed_format.format_map(record)

            formatted += '\n'

            exception = record['exception']

            if exception:
                with exception._formatting(colored=self.colored, enhanced=self.enhanced):
                    error = "{}".format(exception)

                if not self.serialized:
                    formatted += error
            else:
                error = None

            if self.serialized:
                formatted = self.serialize(formatted, record, error) + '\n'

            message = StrRecord(formatted)
            message.record = record

            with self.lock:
                if self.queued:
                    self.queue.put(message)
                else:
                    self.writer(message)

        except Exception:
            self.handle_error(record)

    def queued_writer(self):
        message = None
        queue = self.queue
        try:
            while 1:
                message = queue.get()
                if message is None:
                    break
                self.writer(message)
        except Exception:
            if message and hasattr(message, 'record'):
                message = message.record
            self.handle_error(message)

    def stop(self):
        if self.queued:
            self.queue.put(None)
            self.thread.join()
        self.stopper()
