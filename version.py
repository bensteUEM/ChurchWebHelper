import os

VERSION = '1.6.1'
__version__ = VERSION

if __name__ == '__main__':
    os.environ['VERSION'] = VERSION
    print(VERSION)
