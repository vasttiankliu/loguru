import io

import pytest

from loguru import logger


def test_file_mode_a(tmp_path):
    file = tmp_path / "test.log"
    file.write_text("base\n")
    logger.add(file, format="{message}", mode="a")
    logger.debug("msg")
    assert file.read_text() == "base\nmsg\n"


def test_file_mode_w(tmp_path):
    file = tmp_path / "test.log"
    file.write_text("base\n")
    logger.add(file, format="{message}", mode="w")
    logger.debug("msg")
    assert file.read_text() == "msg\n"


def test_file_buffering(tmp_path):
    file = tmp_path / "test.log"
    logger.add(file, format="{message}", buffering=-1)
    logger.debug("x" * (io.DEFAULT_BUFFER_SIZE // 2))
    assert file.read_text() == ""
    logger.debug("x" * (io.DEFAULT_BUFFER_SIZE * 2))
    assert file.read_text() != ""


def test_invalid_function_kwargs():
    def function(message):
        pass

    with pytest.raises(TypeError, match=r"add\(\) got an unexpected keyword argument"):
        logger.add(function, b="X")


def test_invalid_file_object_kwargs():
    class Writer:
        def __init__(self):
            self.out = ""

        def write(self, m):
            pass

    writer = Writer()

    with pytest.raises(TypeError, match=r"add\(\) got an unexpected keyword argument"):
        logger.add(writer, format="{message}", kw1="1", kw2="2")


def test_invalid_file_kwargs():
    with pytest.raises(TypeError, match=r".*keyword argument;*"):
        logger.add("file.log", nope=123)


def test_invalid_coroutine_kwargs():
    async def foo():
        pass

    with pytest.raises(TypeError, match=r"add\(\) got an unexpected keyword argument"):
        logger.add(foo, nope=123)
