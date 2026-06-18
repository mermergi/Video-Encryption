import os
import configparser


class Config(object):
    def __init__(self, config_file='config.ini'):
        self._path = os.path.split(os.path.realpath(__file__))[0]+'\\'+config_file
        if not os.path.exists(self._path):
            raise FileNotFoundError("No such file: config.ini")
        self._config = configparser.ConfigParser()
        self._config.read(self._path, encoding='utf-8-sig')
        self._configRaw = configparser.RawConfigParser()
        self._configRaw.read(self._path, encoding='utf-8-sig')

    def get(self, section, name):
        return self._config.get(section, name)

    def getRaw(self, section, name):
        return self._configRaw.get(section, name)

    def getOpt(self, section, name, fallback=None):
        """带 fallback 的读取"""
        try:
            return self._config.get(section, name)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return fallback


global_config = Config()
