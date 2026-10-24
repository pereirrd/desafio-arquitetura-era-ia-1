import urllib.request

urllib.request.urlopen("http://127.0.0.1:4000/health/liveliness", timeout=3).read()
open("/tmp/keys-ready", encoding="utf-8").read()
