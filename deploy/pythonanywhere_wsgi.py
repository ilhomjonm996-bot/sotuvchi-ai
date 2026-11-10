# PythonAnywhere uchun WSGI fayli.
# Web sahifasidagi "WSGI configuration file" ichidagi HAMMA matnni o'chirib, shu matnni qo'ying.
import os
import sys

PROJECT = os.path.expanduser("~/sotuvchi_ai")
if PROJECT not in sys.path:
    sys.path.insert(0, PROJECT)

# Ochiq demo: haqiqiy do'konga hech qachon ulanmaydi, kalitlar ishlatilmaydi.
os.environ["DEMO_MODE"] = "1"
os.environ["UZUM_API_TOKEN"] = ""
os.environ["TELEGRAM_BOT_TOKEN"] = ""

from web import app as application  # noqa: E402
