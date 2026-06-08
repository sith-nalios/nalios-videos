#!/usr/bin/env python3
"""Test EDI Connector — 3 cas complets v2"""
import xmlrpc.client, urllib.request, json, time, sys

URL = 'http://localhost:8069'
DB = 'test_v19_migration'
MOCK_LOG = '/tmp/mock_receiver.log'

common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common')
uid = common.authenticate(DB, 'admin', 'admin', {})
m = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object')

def rpc(model, method, args, kw=None):
    return m.execute_kw(DB, uid, 'admin', model, method, args, kw or {})

def mock_count():
    try:
        return open(MOCK_LOG).read().count('XML reçu sur /edi')
    except:
        return 0

def mock_last():
    try:
        content = open(MOCK_LOG).read()
        return content.split('XML reçu sur /edi')[-1][:500]
    except:
        return ""

# ─────────────────────────────────────────────────────────
print("=" * 60)
print("CAS 1 : Inbound PO — upsert via webhook")
print("=" * 60)

# Canal 'test' (id=1) → profil 'Import Commandes Fournisseur'
# xml_root_tag=PurchaseOrders, xml_record_tag=PurchaseOrder
token = rpc('edi.channel', 'read', [[1]], {'fields': ['token']})[0]['token']
webhook_url = f"{URL}/edi/receive/{token}"

pos_before = rpc('purchase.order', 'search_read', [[]], {'fields': ['name', 'partner_id', 'date_order']})
print(f"POs avant envoi: {[p['name'] for p in pos_before]}")

xml_po = """<?xml version="1.0" encoding="UTF-8"?>
<PurchaseOrders>
    <PurchaseOrder>
        <VendorRef>PO-EDI-TEST-001</VendorRef>
        <Vendor>Acme SA (via EDI)</Vendor>
        <OrderDate>2026-06-30 09:00:00</OrderDate>
    </PurchaseOrder>
    <PurchaseOrder>
        <VendorRef>PO-EDI-TEST-002</VendorRef>
        <Vendor>Acme SA (via EDI)</Vendor>
        <OrderDate>2026-07-15 14:00:00</OrderDate>
    </PurchaseOrder>
</PurchaseOrders>"""

req = urllib.request.Request(
    webhook_url,
    data=xml_po.encode('utf-8'),
    headers={'Content-Type': 'application/xml'},
    method='POST'
)
resp = urllib.request.urlopen(req, timeout=10)
result = json.loads(resp.read())
print(f"Réponse: {json.dumps(result, indent=2)}")
time.sleep(1)

pos_after = rpc('purchase.order', 'search_read', [[]], {'fields': ['name', 'partner_id', 'date_order']})
print(f"POs après envoi: {[(p['name'], p['date_order']) for p in pos_after]}")

ok1 = result.get('records_processed', 0) == 2
print(f"{'✓ CAS 1 OK' if ok1 else '✗ CAS 1 KO'} — {result.get('records_processed')} records traités, {len(pos_after)} POs en base")

# ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("CAS 2 : Outbound SO — confirmation → XML vers mock server")
print("=" * 60)

cnt_before = mock_count()
print(f"Messages mock avant: {cnt_before}")

# Créer un nouveau SO avec produit service (pas de route stock)
partner_id = rpc('res.partner', 'search', [[['name', 'like', 'Acme']]])[0]
product_id = 3  # Standard delivery (service)
uom_id = rpc('uom.uom', 'search', [[['name', '=', 'Units']]])[0] if rpc('uom.uom', 'search', [[['name', '=', 'Units']]]) else 1

so_id = rpc('sale.order', 'create', [{
    'partner_id': partner_id,
    'order_line': [(0, 0, {
        'product_id': product_id,
        'product_uom_qty': 2,
        'price_unit': 150.0,
    })],
}])
so_name = rpc('sale.order', 'read', [[so_id]], {'fields': ['name']})[0]['name']
print(f"SO créé: {so_name} (id={so_id})")

rpc('sale.order', 'action_confirm', [[so_id]])
print(f"SO {so_name} confirmée")
time.sleep(2)

cnt_after = mock_count()
ok2 = cnt_after > cnt_before
print(f"{'✓ CAS 2 OK' if ok2 else '✗ CAS 2 KO'} — {cnt_after - cnt_before} message(s) envoyé(s) au mock")
if ok2:
    print(f"Contenu XML reçu:\n{mock_last()}")

# ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("CAS 3 : Outbound Picking — validation → XML vers mock server")
print("=" * 60)

picking_model_id = rpc('ir.model', 'search', [[['model', '=', 'stock.picking']]])[0]
channel_id = 3  # Mock Webhook SO

# Créer ou retrouver le profil picking
existing = rpc('edi.profile', 'search', [[['name', '=', 'Export Bons de Livraison']]])
if existing:
    picking_profile_id = existing[0]
    print(f"Profil existant (id={picking_profile_id})")
else:
    picking_profile_id = rpc('edi.profile', 'create', [{
        'name': 'Export Bons de Livraison',
        'direction': 'out',
        'format': 'xml',
        'model_id': picking_model_id,
        'xml_root_tag': 'Deliveries',
        'xml_record_tag': 'Delivery',
        'channel_id': channel_id,
    }])
    print(f"Profil créé (id={picking_profile_id})")

    for seq, (src, fname) in enumerate([('Reference', 'name'), ('State', 'state'), ('Partner', 'partner_id')], 10):
        fid = rpc('ir.model.fields', 'search', [[['model_id', '=', picking_model_id], ['name', '=', fname]]])
        if fid:
            rpc('edi.field.mapping', 'create', [{
                'profile_id': picking_profile_id,
                'source_path': src,
                'odoo_field_id': fid[0],
                'transformer': 'none',
                'is_key': False,
                'sequence': seq,
            }])
    print("Mappings créés")

# Créer ou retrouver le trigger
existing_trig = rpc('edi.trigger', 'search', [[['profile_id', '=', picking_profile_id]]])
if existing_trig:
    trig_id = existing_trig[0]
    print(f"Trigger existant (id={trig_id})")
else:
    trig_id = rpc('edi.trigger', 'create', [{
        'name': 'Export BL validé',
        'profile_id': picking_profile_id,
        'trigger_type': 'on_create_or_write',
        'filter_domain': "[('state', '=', 'done')]",
        'filter_pre_domain': "[('state', '!=', 'done')]",
    }])
    print(f"Trigger créé (id={trig_id})")
    time.sleep(1)

cnt_before_3 = mock_count()
print(f"Messages mock avant validation: {cnt_before_3}")

# Valider WH/OUT/00001
picking = rpc('stock.picking', 'search_read', [[['name', '=', 'WH/OUT/00001']]], {'fields': ['id', 'state']})[0]
print(f"Picking: {picking}")

if picking['state'] == 'done':
    print("Picking déjà validé — impossible de retester dans cette session")
    ok3 = None
else:
    # S'assurer que les quantités sont remplies
    moves = rpc('stock.move', 'search_read', [[['picking_id', '=', picking['id']]]], {'fields': ['id', 'product_uom_qty']})
    for mv in moves:
        rpc('stock.move', 'write', [[mv['id']], {'quantity': mv['product_uom_qty']}])

    try:
        rpc('stock.picking', 'button_validate', [[picking['id']]])
        print("button_validate OK")
    except Exception as e:
        err = str(e)
        if 'wizard' in err.lower() or 'immediate' in err.lower():
            # Wizard de confirmation requis — forcer via SQL ou write direct
            print(f"Wizard requis, on tente write direct: {err[:80]}")
            try:
                # Créer le wizard de validation immédiate si dispo
                wiz_id = rpc('stock.immediate.transfer', 'create', [{'pick_ids': [(4, picking['id'])]}])
                rpc('stock.immediate.transfer', 'process', [[wiz_id]])
                print("Immediate transfer wizard OK")
            except Exception as e2:
                print(f"Wizard échoué: {e2}")
        else:
            print(f"Erreur button_validate: {err[:200]}")

    time.sleep(2)
    cnt_after_3 = mock_count()
    picking_state_final = rpc('stock.picking', 'read', [[picking['id']]], {'fields': ['state']})[0]['state']
    print(f"État picking final: {picking_state_final}")
    ok3 = cnt_after_3 > cnt_before_3 and picking_state_final == 'done'
    print(f"{'✓ CAS 3 OK' if ok3 else '✗ CAS 3 KO'} — {cnt_after_3 - cnt_before_3} message(s), état={picking_state_final}")
    if ok3:
        print(f"Contenu XML reçu:\n{mock_last()}")

# ─────────────────────────────────────────────────────────
print()
print("=" * 60)
print("RÉSUMÉ")
print("=" * 60)
print(f"CAS 1 Inbound PO:       {'✓ OK' if ok1 else '✗ KO'}")
print(f"CAS 2 Outbound SO:      {'✓ OK' if ok2 else '✗ KO'}")
print(f"CAS 3 Outbound Picking: {'✓ OK' if ok3 else ('✗ KO' if ok3 is False else '~ SKIP (déjà validé)')}")
print(f"\nTotal mock messages: {mock_count()}")
