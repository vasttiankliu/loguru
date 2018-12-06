# coding: utf-8

import pathlib
import sys

import loguru

import pytest

MESSAGES = ['ASCII test', '色 ᚠ ȝ î ರ 😄']
PARAMS = [(message, message + '\n') for message in MESSAGES]

messages = pytest.mark.parametrize('message, expected', PARAMS)
repetitions = pytest.mark.parametrize('rep', [0, 1, 2])


def log(sink, message, rep=1):
    logger = loguru.Logger()
    logger.debug("This shouldn't be printed.")
    logger.log_to(sink, format='{message}')
    for i in range(rep):
        logger.debug(message)

@messages
@repetitions
def test_stdout_sink(message, expected, rep, capsys):
    log(sys.stdout, message, rep)
    out, err = capsys.readouterr()
    assert out == expected * rep
    assert err == ''

@messages
@repetitions
def test_stderr_sink(message, expected, rep, capsys):
    log(sys.stderr, message, rep)
    out, err = capsys.readouterr()
    assert out == ''
    assert err == expected * rep

@messages
@repetitions
@pytest.mark.parametrize("sink_from_path", [
    lambda path: str(path),
    lambda path: open(path, 'a'),
    lambda path: pathlib.Path(path),
    lambda path: pathlib.Path(path).open('a'),
])
def test_file_sink(message, expected, rep, sink_from_path, tmpdir):
    file = tmpdir.join('test.log')
    path = file.realpath()
    sink = sink_from_path(path)
    log(sink, message, rep)
    assert file.read() == expected * rep

@messages
@repetitions
def test_function_sink(message, expected, rep):
    a = []
    func = lambda log_message: a.append(log_message)
    log(func, message, rep)
    assert a == [expected] * rep

@pytest.mark.parametrize('sink', [123, object(), sys])
def test_invalid_sink(sink):
    with pytest.raises(TypeError):
        log(sink, "")
