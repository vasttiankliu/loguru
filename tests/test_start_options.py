import json
import pytest
import multiprocessing
from loguru import logger
import ansimarkup

@pytest.mark.parametrize('level, function, should_output', [
    (0,              lambda x: x.trace,    True),
    ("TRACE",        lambda x: x.debug,    True),
    ("INFO",         lambda x: x.info,     True),
    (10,             lambda x: x.debug,    True),
    ("WARNING",      lambda x: x.success,  False),
    (50,             lambda x: x.error,    False),
])
def test_level(level, function, should_output, writer):
    message = "Test Level"
    logger.start(writer, level=level, format='{message}')
    function(logger)(message)
    assert writer.read() == (message + '\n') * should_output

@pytest.mark.parametrize('message, format, expected', [
    ('a', 'Message: {message}', 'Message: a'),
    ('b', 'Nope', 'Nope'),
    ('c', '{level} {message} {level}', 'DEBUG c DEBUG'),
    ('d', '{message} {level} {level.no} {level.name}', 'd DEBUG %d DEBUG' % 10)
])
def test_format(message, format, expected, writer):
    logger.start(writer, format=format)
    logger.debug(message)
    assert writer.read() == expected + '\n'

@pytest.mark.parametrize('filter, should_output', [
    (None, True),
    ('', True),
    ('tests', True),
    ('test', False),
    ('testss', False),
    ('tests.', False),
    ('tests.test_start_options', True),
    ('tests.test_start_options.', False),
    ('test_start_options', False),
    ('.', False),
    (lambda r: True, True),
    (lambda r: False, False),
    (lambda r: r['level'] == "DEBUG", True),
    (lambda r: r['level'].no != 10, False),
])
def test_filter(filter, should_output, writer):
    message = "Test Filter"
    logger.start(writer, filter=filter, format='{message}')
    logger.debug(message)
    assert writer.read() == (message + '\n') * should_output

@pytest.mark.parametrize('message, format, expected, colored', [
    ('a', '<red>{message}</red>', 'a', False),
    ('b', '<red>{message}</red>', ansimarkup.parse("<red>b</red>"), True),
])
def test_colored(message, format, expected, colored, writer):
    logger.start(writer, format=format, colored=colored)
    logger.debug(message)
    assert writer.read() == expected + '\n'

def test_enhanced(writer):
    logger.start(writer, format='{message}', enhanced=True)
    try:
        1 / 0
    except:
        logger.exception('')
    result_with = writer.read().strip()

    logger.stop()
    writer.clear()

    logger.start(writer, format='{message}', enhanced=False)
    try:
        1 / 0
    except:
        logger.exception('')
    result_without = writer.read().strip()

    assert len(result_with) > len(result_without)

@pytest.mark.parametrize('with_exception', [False, True])
def test_serialized(with_exception):
    record_dict = record_json = None

    def sink(message):
        nonlocal record_dict, record_json
        record_dict = message.record
        record_json = json.loads(message)['record']

    logger.configure(extra=dict(not_serializable=object()))
    logger.start(sink, format="{message}", wrapped=False, serialized=True)
    if not with_exception:
        logger.debug("Test")
    else:
        try:
            1 / 0
        except:
            logger.exception("Test")

    assert set(record_dict.keys()) == set(record_json.keys())

@pytest.mark.parametrize('with_exception', [False, True])
def test_queued(with_exception):
    import time
    x = []
    def sink(message):
        time.sleep(0.1)
        x.append(message)
    logger.start(sink, format='{message}', queued=True)
    if not with_exception:
        logger.debug("Test")
    else:
        try:
            1 / 0
        except:
            logger.exception("Test")
    assert len(x) == 0
    time.sleep(0.2)
    lines = x[0].strip().splitlines()
    assert lines[0] == "Test"
    if with_exception:
        assert lines[-1] == "ZeroDivisionError: division by zero"
        assert sum(line.startswith('> ') for line in lines) == 1

def test_wrapped():
    def sink(msg):
        raise 1 / 0
    logger.start(sink, wrapped=False)
    with pytest.raises(ZeroDivisionError):
        logger.debug("fail")

@pytest.mark.parametrize('sink_type', ['function', 'class', 'file_object', 'str_a', 'str_w'])
@pytest.mark.parametrize('test_invalid', [False, True])
def test_kwargs(sink_type, test_invalid, tmpdir, capsys):
    msg = 'msg'
    kwargs = {'kw1': '1', 'kw2': '2'}

    if sink_type == 'function':
        out = []
        def function(message, kw2, kw1):
            out.append(message + kw1 + 'a' + kw2)

        writer = function
        validator = lambda: out == [msg + '\n1a2']

        if test_invalid:
            writer = lambda m: None
    elif sink_type == 'class':
        out = []
        class Writer:
            def __init__(self, kw2, kw1):
                self.end = kw1 + 'b' + kw2
            def write(self, m):
                out.append(m + self.end)

        writer = Writer
        validator = lambda: out == [msg + '\n1b2']

        if test_invalid:
            writer.__init__ = lambda s: None
    elif sink_type == 'file_object':
        class Writer:
            def __init__(self):
                self.out = ''
            def write(self, m, kw2, kw1):
                self.out += m + kw1 + 'c' + kw2

        writer = Writer()
        validator = lambda: writer.out == msg + '\n1c2'

        if test_invalid:
            writer.write = lambda m: None
    elif sink_type == 'str_a':
        kwargs = {'mode': 'a', 'encoding': 'ascii'}
        file = tmpdir.join('test.log')
        with file.open(mode='w', encoding='ascii') as f:
            f.write("This shouldn't be overwritten.")

        writer = file.realpath()
        validator = lambda: file.read() == "This shouldn't be overwritten." + msg + "\n"

        if test_invalid:
            kwargs = {"foo": 1, "bar": 2}
    elif sink_type == 'str_w':
        kwargs = {'mode': 'w', 'encoding': 'ascii'}
        file = tmpdir.join('test.log')
        with file.open(mode='w', encoding='ascii') as f:
            f.write("This should be overwritten.")

        writer = file.realpath()
        validator = lambda: file.read() == msg + "\n"

        if test_invalid:
            kwargs = {"foo": 1, "bar": 2}

    def test():
        logger.start(writer, format='{message}', **kwargs)
        logger.debug(msg)

    if test_invalid:
        if sink_type in ('function', 'file_object'):
            test()
            out, err = capsys.readouterr()
            assert out == ""
            assert err.startswith("--- Logging error in Loguru ---")
        else:
            with pytest.raises(TypeError):
                test()
    else:
        test()
        assert validator()

@pytest.mark.parametrize("level", ["foo", -1, 3.4, object()])
def test_invalid_level(writer, level):
    with pytest.raises(ValueError):
        logger.start(writer, level=level)

@pytest.mark.parametrize("format", [-1, 3.4, object()])
def test_invalid_format(writer, format):
    with pytest.raises(ValueError):
        logger.start(writer, format=format)

@pytest.mark.parametrize("filter", [-1, 3.4, object()])
def test_invalid_filter(writer, filter):
    with pytest.raises(ValueError):
        logger.start(writer, filter=filter)
