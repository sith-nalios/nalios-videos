#!/usr/bin/env python3
"""
Serveur FTP local pour tester nalios_edi_connector.
Port 2121, user=edi / pass=edi, dossiers /in et /done dans /tmp/ftp_root/
Usage : python3 mock_ftp_server.py
"""
import os, sys
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer
from pyftpdlib.authorizers import DummyAuthorizer

ROOT = '/tmp/ftp_root'
os.makedirs(f'{ROOT}/in', exist_ok=True)
os.makedirs(f'{ROOT}/done', exist_ok=True)

auth = DummyAuthorizer()
auth.add_user('edi', 'edi', ROOT, perm='elradfmwMT')

handler = FTPHandler
handler.authorizer = auth
handler.passive_ports = range(60000, 60100)

server = FTPServer(('127.0.0.1', 2121), handler)
print(f"FTP server on ftp://edi:edi@127.0.0.1:2121 — root={ROOT}")
print(f"  /in   → dossier entrant  ({ROOT}/in)")
print(f"  /done → dossier archives ({ROOT}/done)")
server.serve_forever()
