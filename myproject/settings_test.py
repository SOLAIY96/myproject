from .settings import *

DEBUG = False

INSTALLED_APPS.remove("debug_toolbar")

MIDDLEWARE = [m for m in MIDDLEWARE if "debug_toolbar" not in m]
