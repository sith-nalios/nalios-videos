#!/usr/bin/env python3
"""
Test EDI FTP — entrant et sortant
- FTP IN  : dépose un XML sur le FTP, déclenche le poll, vérifie le record Odoo
- FTP OUT : exporte un SO via canal FTP, vérifie le fichier sur le FTP
Pré-requis : mock_ftp_server.py doit tourner (python3 scripts/mock_ftp_server.py &)
"""
import ftplib, io, os, time, xmlrpc.client, json, sys

URL = 'http://localhost:8069'
DB = 'test_v19_migration'
FTP_HOST = '127.0.0.1'
FTP_PORT = 2121
FTP_USER = 'edi'
FTP_PASS = 'edi'
FTP_IN   = '/in'
FTP_DONE = '/done'
FTP_OUT  = '/out'
FTP_ROOT = '/tmp/ftp_root'

common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, 'admin', 'admin', {})
m = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

def rpc(model, method, args, kw=None):
    return m.execute_kw(DB, uid, 'admin', model, method, args, kw or {})

def ftp_connect():
    ftp = ftplib.FTP()
    ftp.connect(FTP_HOST, FTP_PORT)
    ftp.login(FTP_USER, FTP_PASS)
    return ftp

def ftp_list(path):
    with ftp_connect() as ftp:
        try:
            return ftp.nlst(path)
        except ftplib.error_perm:
            return []

def ftp_put(path, content):
    with ftp_connect() as ftp:
        ftp.storbinary(f'STOR {path}', io.BytesIO(content.encode('utf-8')))

def ftp_get(path):
    buf = io.BytesIO()
    with ftp_connect() as ftp:
        ftp.retrbinary(f'RETR {path}', buf.write)
    return buf.getvalue().decode('utf-8')

# ─────────────────────────────────────────────────────────
print("=" * 60)
print("SETUP — Canal FTP dans Odoo")
print("=" * 60)

# Créer ou récupérer le canal FTP
existing = rpc('edi.channel', 'search', [[['name', '=', 'FTP Local Test']]])
if existing:
    channel_id = existing[0]
    rpc('edi.channel', 'write', [[channel_id], {
        'host': FTP_HOST, 'port': FTP_PORT,
        'username': FTP_USER, 'password': FTP_PASS,
        'remote_path': FTP_IN, 'done_path': FTP_DONE,
    }])
    print(f"Canal existant mis à jour (id={channel_id})")
else:
    channel_id = rpc('edi.channel', 'create', [{
        'name': 'FTP Local Test',
        'channel_type': 'ftp',
        'host': FTP_HOST,
        'port': FTP_PORT,
        'username': FTP_USER,
        'password': FTP_PASS,
        'remote_path': FTP_IN,
        'done_path': FTP_DONE,
    }])
    print(f"Canal créé (id={channel_id})")

# Vérifier modèle res.partner pour FTP IN
partner_model_id = rpc('ir.model', 'search', [[['model', '=', 'res.partner']]])[0]

# Créer ou récupérer profil entrant partenaires sur ce canal FTP
existing_prof = rpc('edi.profile', 'search', [[['name', '=', 'Import Partenaires FTP']]])
if existing_prof:
    profile_in_id = existing_prof[0]
    print(f"Profil IN existant (id={profile_in_id})")
else:
    profile_in_id = rpc('edi.profile', 'create', [{
        'name': 'Import Partenaires FTP',
        'direction': 'in',
        'format': 'xml',
        'model_id': partner_model_id,
        'xml_root_tag': 'Partners',
        'xml_record_tag': 'Partner',
        'channel_id': channel_id,
    }])
    print(f"Profil IN créé (id={profile_in_id})")

    # Mappings
    for seq, (src, fname, transformer, is_key) in enumerate([
        ('Name', 'name', 'none', True),
        ('Email', 'email', 'none', False),
        ('Phone', 'phone', 'none', False),
    ], 10):
        fid = rpc('ir.model.fields', 'search', [[['model_id', '=', partner_model_id], ['name', '=', fname]]])[0]
        rpc('edi.field.mapping', 'create', [{
            'profile_id': profile_in_id,
            'source_path': src,
            'odoo_field_id': fid,
            'transformer': transformer,
            'is_key': is_key,
            'sequence': seq,
        }])

    # Règle upsert
    rpc('edi.action.rule', 'create', [{
        'profile_id': profile_in_id,
        'name': 'Upsert partenaire',
        'action_type': 'upsert',
        'sequence': 10,
    }])
    print("Profil IN + mappings + règle créés")

# ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("CAS FTP IN — dépôt XML sur FTP → polling → record Odoo")
print("=" * 60)

# S'assurer que /in et /done existent sur le FTP
os.makedirs(f'{FTP_ROOT}/in', exist_ok=True)
os.makedirs(f'{FTP_ROOT}/done', exist_ok=True)

xml_partners = """<?xml version="1.0" encoding="UTF-8"?>
<Partners>
    <Partner>
        <Name>FTP Test Partner</Name>
        <Email>ftp-test@example.com</Email>
        <Phone>+41 22 000 00 01</Phone>
    </Partner>
    <Partner>
        <Name>FTP Test Partner 2</Name>
        <Email>ftp-test2@example.com</Email>
        <Phone>+41 22 000 00 02</Phone>
    </Partner>
</Partners>"""

# Déposer le fichier sur le FTP
ftp_put(f'{FTP_IN}/partners_test.xml', xml_partners)
print(f"Fichier déposé sur FTP: {FTP_IN}/partners_test.xml")
print(f"Fichiers dans /in: {ftp_list(FTP_IN)}")

# Compter les partenaires avant
partners_before = rpc('res.partner', 'search_count', [[['email', 'like', 'ftp-test']]])
print(f"Partenaires FTP avant poll: {partners_before}")

# Déclencher le poll via RPC
rpc('edi.channel', 'write', [[channel_id], {}])  # dummy write pour forcer contexte
rpc('edi.channel', 'action_poll', [[channel_id]])
time.sleep(1)

# Vérifier les résultats
partners_after = rpc('res.partner', 'search_read',
    [[['email', 'like', 'ftp-test']]], {'fields': ['name', 'email', 'phone']})
print(f"Partenaires FTP après poll: {partners_after}")

files_in_after = ftp_list(FTP_IN)
files_done = ftp_list(FTP_DONE)
print(f"Fichiers dans /in après:  {files_in_after}")
print(f"Fichiers dans /done:      {files_done}")

ok_in = len(partners_after) >= 2 and not any('partners_test.xml' in f for f in files_in_after)
print(f"{'✓ FTP IN OK' if ok_in else '✗ FTP IN KO'} — {len(partners_after)} partenaires créés/mis à jour, fichier archivé={bool(files_done)}")

# ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("CAS FTP OUT — export SO → fichier XML sur FTP")
print("=" * 60)

# Créer un canal FTP sortant (même serveur, dossier /out)
os.makedirs(f'{FTP_ROOT}/out', exist_ok=True)
with ftp_connect() as ftp:
    try:
        ftp.mkd(FTP_OUT)
    except ftplib.error_perm:
        pass

existing_out = rpc('edi.channel', 'search', [[['name', '=', 'FTP Local Test OUT']]])
if existing_out:
    ch_out_id = existing_out[0]
else:
    ch_out_id = rpc('edi.channel', 'create', [{
        'name': 'FTP Local Test OUT',
        'channel_type': 'ftp',
        'host': FTP_HOST,
        'port': FTP_PORT,
        'username': FTP_USER,
        'password': FTP_PASS,
        'remote_path': FTP_OUT,
    }])
print(f"Canal FTP OUT id={ch_out_id}")

# Créer profil outbound SO sur FTP
so_model_id = rpc('ir.model', 'search', [[['model', '=', 'sale.order']]])[0]
existing_out_prof = rpc('edi.profile', 'search', [[['name', '=', 'Export SO FTP']]])
if existing_out_prof:
    prof_out_id = existing_out_prof[0]
    print(f"Profil OUT existant (id={prof_out_id})")
else:
    prof_out_id = rpc('edi.profile', 'create', [{
        'name': 'Export SO FTP',
        'direction': 'out',
        'format': 'xml',
        'model_id': so_model_id,
        'xml_root_tag': 'SalesOrders',
        'xml_record_tag': 'Order',
        'channel_id': ch_out_id,
    }])
    for seq, (src, fname) in enumerate([
        ('Reference', 'name'),
        ('Customer', 'partner_id'),
        ('Amount', 'amount_total'),
        ('Status', 'state'),
    ], 10):
        fid = rpc('ir.model.fields', 'search', [[['model_id', '=', so_model_id], ['name', '=', fname]]])[0]
        rpc('edi.field.mapping', 'create', [{
            'profile_id': prof_out_id,
            'source_path': src,
            'odoo_field_id': fid,
            'transformer': 'none',
            'is_key': False,
            'sequence': seq,
        }])
    print(f"Profil OUT créé (id={prof_out_id})")

# Déclencher l'export manuellement sur S00002
so_id = rpc('sale.order', 'search', [[['name', '=', 'S00002']]])[0]
rpc('edi.profile', 'send_for_record', [[prof_out_id], so_id])
time.sleep(1)

# Vérifier le fichier sur FTP
out_files = ftp_list(FTP_OUT)
print(f"Fichiers dans /out: {out_files}")

if out_files:
    latest = sorted(out_files)[-1]
    content = ftp_get(f"{FTP_OUT}/{latest.split('/')[-1]}")
    print(f"Contenu XML exporté ({latest}):\n{content}")
    ok_out = '<SalesOrders>' in content and 'S00002' in content
else:
    ok_out = False

print(f"{'✓ FTP OUT OK' if ok_out else '✗ FTP OUT KO'}")

# ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("RÉSUMÉ")
print("=" * 60)
print(f"FTP IN  (partenaires): {'✓ OK' if ok_in else '✗ KO'}")
print(f"FTP OUT (export SO):   {'✓ OK' if ok_out else '✗ KO'}")
