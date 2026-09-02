# -*- coding: utf-8 -*-
"""لایه سازگاری Bale — Bot API بله تقریبا یکسان با تلگرام است

استفاده:
    from bale_compat import BaleApplication
    app = BaleApplication.builder().token(TOKEN).build()

تمام متدهای python-telegram-bot کار می‌کنند ولی درخواست‌ها به tapi.bale.ai می‌روند.
"""
import os

import telegram


def create_bale_app():
    """اپلیکیشن بات بله با همان API تلگرام"""
    from telegram.ext import Application, ApplicationBuilder

    class BaleApplicationBuilder(ApplicationBuilder):
        def __init__(self):
            super().__init__()
            self._base_url = "https://tapi.bale.ai/bot"
            self._base_file_url = "https://tapi.bale.ai/file/bot"

    class BaleApplication(Application):
        pass

    BaleApplication.Builder = BaleApplicationBuilder
    return BaleApplicationBuilder()


def bale_bot(token: str, **kwargs):
    """میان‌بر: ساختن اپ بات بله"""
    builder = create_bale_app()
    builder.token(token)
    return builder.build(**kwargs)
