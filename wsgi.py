# -*- coding: utf-8 -*-
from __future__ import absolute_import
import os

from main_runner import main


if __name__ == '__main__':
    token = os.environ['TOKEN']
    lang = os.environ['LANG']
    main(token, lang)
