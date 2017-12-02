from os import environ

def env(key, type_, default=None):
    if key not in environ:
        return default

    val = environ[key]

    if type_ == str:
        return val
    elif type_ == bool:
        if val.lower() in ['1', 'true', 'yes', 'y']:
            return True
        if val.lower() in ['0', 'false', 'no', 'n']:
            return False
        raise ValueError("Invalid bool value for key '%s': '%s'" % (key, val))
    elif type_ == int:
        try:
            return int(val)
        except ValueError as e:
            raise ValueError("Invalid int value for key '%s': '%s'" % (key, val)) from e


LOGURU_AUTOINIT = env('LOGURU_AUTOINIT', bool, True)

LOGURU_FORMAT = env("LOGURU_FORMAT", str, "<green>{time}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>")
LOGURU_LEVEL = env("LOGURU_LEVEL", str, "DEBUG")
LOGURU_COLORED = env("LOGURU_COLORED", bool, None)
LOGURU_STRUCTURED = env("LOGURU_STRUCTURED", bool, False)
LOGURU_ENHANCED = env("LOGURU_ENHANCED", bool, True)
LOGURU_GUARDED = env("LOGURU_GUARDED", bool, False)

LOGURU_TRACE_NO = env("LOGURU_TRACE_NO", int, 5)
LOGURU_TRACE_COLOR = env("LOGURU_TRACE_COLOR", str, "<cyan><bold>")
LOGURU_TRACE_ICON = env("LOGURU_TRACE_ICON", str, "✏️")  # Pencil

LOGURU_DEBUG_NO = env("LOGURU_DEBUG_NO", int, 10)
LOGURU_DEBUG_COLOR = env("LOGURU_DEBUG_COLOR", str, "<blue><bold>")
LOGURU_DEBUG_ICON = env("LOGURU_DEBUG_ICON", str, "🐞")  # Lady Beetle

LOGURU_INFO_NO = env("LOGURU_INFO_NO", int, 20)
LOGURU_INFO_COLOR = env("LOGURU_INFO_COLOR", str, "<bold>")
LOGURU_INFO_ICON = env("LOGURU_INFO_ICON", str, "ℹ️")  # Information

LOGURU_SUCCESS_NO = env("LOGURU_SUCCESS_NO", int, 25)
LOGURU_SUCCESS_COLOR = env("LOGURU_SUCCESS_COLOR", str, "<green><bold>")
LOGURU_SUCCESS_ICON = env("LOGURU_SUCCESS_ICON", str, "✔️")  # Heavy Check Mark

LOGURU_WARNING_NO = env("LOGURU_WARNING_NO", int, 30)
LOGURU_WARNING_COLOR = env("LOGURU_WARNING_COLOR", str, "<yellow><bold>")
LOGURU_WARNING_ICON = env("LOGURU_WARNING_ICON", str, "⚠️")  # Warning

LOGURU_ERROR_NO = env("LOGURU_ERROR_NO", int, 40)
LOGURU_ERROR_COLOR = env("LOGURU_ERROR_COLOR", str, "<red><bold>")
LOGURU_ERROR_ICON = env("LOGURU_ERROR_ICON", str, "❌")  # Cross Mark

LOGURU_CRITICAL_NO = env("LOGURU_CRITICAL_NO", int, 50)
LOGURU_CRITICAL_COLOR = env("LOGURU_CRITICAL_COLOR", str, "<RED><bold>")
LOGURU_CRITICAL_ICON = env("LOGURU_CRITICAL_ICON", str, "☠️")  # Skull and Crossbones
