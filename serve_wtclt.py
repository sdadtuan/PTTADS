import os, sys
os.chdir("/Users/quoctuan/Documents/KHANGTHINHLAND/Dự Án/TheCollector/WTCLT")
sys.argv = [sys.argv[0], "3456"]
import http.server, socketserver
handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", 3456), handler) as httpd:
    httpd.serve_forever()
