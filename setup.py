from distutils.core import setup

setup(
    name = 'loguru',
    packages = ['loguru'],
    version = '0.0.1',
    description = 'Logging as an automatism',
    author = 'Delgan',
    author_email = 'delgan.py@gmail.com',
    url = 'https://github.com/Delgan/loguru',
    download_url = 'https://github.com/Delgan/loguru/archive/0.0.1.tar.gz',
    keywords = ['logging'],
    classifiers = [],
    install_requires = [
        'ansimarkup>=1.3.0',
        'better_exceptions_fork>=0.1.8.post0',
        'pendulum>=1.3.0',
    ],
)
