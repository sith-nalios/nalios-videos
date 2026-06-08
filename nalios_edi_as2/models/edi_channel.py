import base64
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class EdiChannel(models.Model):
    _inherit = 'edi.channel'

    channel_type = fields.Selection(
        selection_add=[('as2', 'AS2 (HTTPS + S/MIME)')],
        ondelete={'as2': 'cascade'},
    )
    as2_own_id = fields.Char(string='Notre AS2 ID', help="Ex: NALIOS")
    as2_partner_as2_id = fields.Char(string='AS2 ID Partenaire', help="Ex: PARTNER")
    as2_sign = fields.Boolean(string='Signer les messages', default=True)
    as2_encrypt = fields.Boolean(string='Chiffrer les messages', default=True)
    as2_mdn_mode = fields.Selection([
        ('SYNC', 'Synchrone'),
        ('ASYNC', 'Asynchrone'),
        ('NONE', 'Sans MDN'),
    ], string='Mode MDN', default='SYNC')
    as2_own_cert = fields.Binary(string='Notre certificat (PEM)', attachment=False)
    as2_own_key = fields.Binary(string='Notre clé privée (PEM)', attachment=False)
    as2_own_key_pass = fields.Char(string='Mot de passe clé privée')
    as2_partner_cert = fields.Binary(string='Certificat partenaire (PEM)', attachment=False)
    as2_validate_certs = fields.Boolean(string='Valider la chaîne de certificats', default=False, help="Désactiver pour les certificats auto-signés")
    as2_mdn_url = fields.Char(compute='_compute_as2_mdn_url', string='URL MDN async')

    def _compute_as2_mdn_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.as2_mdn_url = f"{base}/edi/as2/mdn/{rec.token}" if rec.channel_type == 'as2' else False

    def _as2_org(self):
        try:
            from pyas2lib import as2
        except ImportError:
            raise ImportError("Le module 'pyas2lib' est requis pour AS2 (pip install pyas2lib)")
        key_pass = (self.as2_own_key_pass or '').encode()
        own_key = base64.b64decode(self.as2_own_key) if self.as2_own_key else b''
        own_cert = base64.b64decode(self.as2_own_cert) if self.as2_own_cert else b''
        combined = own_key + own_cert
        return as2.Organization(
            as2_name=self.as2_own_id,
            sign_key=combined or None,
            sign_key_pass=key_pass,
            decrypt_key=combined or None,
            decrypt_key_pass=key_pass,
        )

    def _as2_partner(self, mdn_mode=None):
        try:
            from pyas2lib import as2
        except ImportError:
            raise ImportError("Le module 'pyas2lib' est requis pour AS2 (pip install pyas2lib)")
        partner_cert = base64.b64decode(self.as2_partner_cert) if self.as2_partner_cert else None
        mode = mdn_mode or (self.as2_mdn_mode if self.as2_mdn_mode != 'NONE' else None)
        return as2.Partner(
            as2_name=self.as2_partner_as2_id,
            verify_cert=partner_cert,
            encrypt_cert=partner_cert if self.as2_encrypt else None,
            sign=self.as2_sign,
            encrypt=self.as2_encrypt,
            mdn_mode=mode,
            validate_certs=self.as2_validate_certs,
            ignore_self_signed=not self.as2_validate_certs,
        )

    def _use_openssl_backend(self):
        try:
            import oscrypto
            import os
            paths = [
                '/opt/homebrew/opt/openssl@3/lib',
                '/opt/homebrew/opt/openssl/lib',
                '/usr/local/opt/openssl@3/lib',
                '/usr/lib',
            ]
            for p in paths:
                ssl = os.path.join(p, 'libssl.dylib')
                crypto = os.path.join(p, 'libcrypto.dylib')
                if os.path.exists(ssl) and os.path.exists(crypto):
                    oscrypto.use_openssl(libssl_path=ssl, libcrypto_path=crypto)
                    return
        except Exception:
            pass

    def _send_as2(self, exchange):
        self._use_openssl_backend()
        import requests
        from pyas2lib import as2

        if not self.as2_own_id or not self.as2_partner_as2_id:
            raise ValueError("Les identifiants AS2 (propre + partenaire) sont obligatoires")
        if not self.remote_url:
            raise ValueError("L'URL AS2 du partenaire n'est pas configurée")

        org = self._as2_org()
        partner = self._as2_partner()

        msg = as2.Message(sender=org, receiver=partner)
        msg.build(
            data=(exchange.raw_content or '').encode('utf-8'),
            filename=self._get_filename(exchange),
        )

        resp = requests.post(
            self.remote_url,
            data=msg.content,
            headers=dict(msg.headers),
            timeout=self.timeout or 30,
        )
        resp.raise_for_status()

        if self.as2_mdn_mode == 'SYNC' and resp.content:
            mdn = as2.Mdn()
            # Reconstituer headers + body pour le parser MDN
            raw_headers = ''.join(f"{k}: {v}\r\n" for k, v in resp.headers.items()).encode()
            raw_mdn = raw_headers + b'\r\n' + resp.content
            status, detail = mdn.parse(raw_mdn, find_message_cb=lambda mid, rid: msg)
            if status != 'processed':
                raise ValueError(f"MDN partenaire : '{status}' — {detail or ''}")
