import io
import logging
import uuid

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class EdiChannel(models.Model):
    _name = 'edi.channel'
    _description = 'EDI Channel'
    _rec_name = 'name'

    name = fields.Char(required=True)
    channel_type = fields.Selection([
        ('webhook', 'Webhook (REST)'),
        ('ftp', 'FTP'),
        ('sftp', 'SFTP'),
        ('manual', 'Manuel'),
    ], required=True, default='webhook')
    active = fields.Boolean(default=True)
    token = fields.Char(default=lambda self: str(uuid.uuid4()), copy=False, readonly=True)
    webhook_url = fields.Char(compute='_compute_webhook_url', string='URL Webhook')
    remote_url = fields.Char(string='URL distante', help="URL de l'endpoint externe pour l'envoi sortant (webhook OUT)")
    timeout = fields.Integer(default=30, string='Timeout (s)', help="Timeout en secondes pour les appels webhook et FTP")
    host = fields.Char()
    port = fields.Integer(default=21)
    username = fields.Char()
    password = fields.Char()
    remote_path = fields.Char(default='/')
    done_path = fields.Char(default='/done', string='Dossier archives', help="Dossier FTP/SFTP où déplacer les fichiers traités")
    filename_template = fields.Char(
        default='{sequence}',
        string='Template nom de fichier',
        help="Variables: {sequence}, {date}, {model}, {direction}. Exemple: {date}_{sequence}",
    )

    def _compute_webhook_url(self):
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for rec in self:
            rec.webhook_url = f"{base}/edi/receive/{rec.token}" if rec.channel_type == 'webhook' else False

    def _get_filename(self, exchange):
        from datetime import date
        tpl = (self.filename_template or '{sequence}').strip()
        name = tpl.format(
            sequence=exchange.name.replace('/', '_'),
            date=date.today().strftime('%Y%m%d'),
            model=exchange.profile_id.model_name.replace('.', '_') if exchange.profile_id else 'edi',
            direction=exchange.direction or 'out',
        )
        ext = 'json' if exchange.profile_id.format == 'json' else 'xml'
        if not name.endswith(f'.{ext}'):
            name = f"{name}.{ext}"
        return name

    def _find_profile_for_content(self, content):
        profiles = self.env['edi.profile'].search([
            ('channel_id', '=', self.id), ('direction', 'in', ('in', 'both')),
        ])
        if not profiles:
            return self.env['edi.profile']
        if len(profiles) == 1:
            return profiles[0]
        import re
        match = re.search(r'<([A-Za-z][A-Za-z0-9_:.-]*)', content)
        if match:
            root_tag = match.group(1)
            for p in profiles:
                if p.xml_root_tag and p.xml_root_tag == root_tag:
                    return p
                if p.xml_record_tag and p.xml_record_tag == root_tag:
                    return p
        return profiles[0]

    def action_regenerate_token(self):
        self.ensure_one()
        self.token = str(uuid.uuid4())

    def action_poll(self):
        for rec in self:
            rec._poll()
        return True

    def action_test_connection(self):
        self.ensure_one()
        try:
            if self.channel_type == 'ftp':
                import ftplib
                with ftplib.FTP() as ftp:
                    ftp.connect(self.host, self.port or 21, timeout=self.timeout or 10)
                    ftp.login(self.username or '', self.password or '')
                    ftp.nlst(self.remote_path or '/')
                msg = f"Connexion FTP réussie sur {self.host}:{self.port or 21}"
            elif self.channel_type == 'sftp':
                import paramiko
                with paramiko.SSHClient() as ssh:
                    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    ssh.connect(self.host, port=self.port or 22, username=self.username, password=self.password, timeout=self.timeout or 10)
                    with ssh.open_sftp() as sftp:
                        sftp.listdir(self.remote_path or '/')
                msg = f"Connexion SFTP réussie sur {self.host}:{self.port or 22}"
            elif self.channel_type == 'webhook':
                if not self.remote_url:
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {'message': "Aucune URL distante configurée", 'type': 'warning', 'sticky': False},
                    }
                import requests
                resp = requests.get(self.remote_url, timeout=self.timeout or 10, allow_redirects=True)
                msg = f"URL distante accessible (HTTP {resp.status_code})"
            else:
                msg = "Test non disponible pour ce type de canal"
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'message': msg, 'type': 'success', 'sticky': False},
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {'message': f"Échec : {e}", 'type': 'danger', 'sticky': True},
            }

    @api.model
    def _cron_poll_ftp(self):
        channels = self.search([('channel_type', 'in', ('ftp', 'sftp')), ('active', '=', True)])
        for channel in channels:
            try:
                channel._poll()
            except Exception as e:
                _logger.error("EDI poll error on channel %s: %s", channel.name, e, exc_info=True)

    def _poll(self):
        self.ensure_one()
        if self.channel_type == 'ftp':
            self._poll_ftp()
        elif self.channel_type == 'sftp':
            self._poll_sftp()

    def _poll_ftp(self):
        import ftplib
        remote_path = (self.remote_path or '/').rstrip('/')
        done_path = (self.done_path or '/done').rstrip('/')

        with ftplib.FTP() as ftp:
            ftp.connect(self.host, self.port or 21, timeout=self.timeout or 30)
            ftp.login(self.username or '', self.password or '')
            names = [f for f in ftp.nlst(remote_path) if f.lower().endswith(('.xml', '.json'))]
            for name in names:
                filename = name.split('/')[-1]
                filepath = f"{remote_path}/{filename}"
                buf = io.BytesIO()
                ftp.retrbinary(f"RETR {filepath}", buf.write)
                content = buf.getvalue().decode('utf-8', errors='replace')
                profile = self._find_profile_for_content(content)
                if not profile:
                    _logger.warning("EDI FTP: aucun profil entrant pour %s sur canal %s", filename, self.name)
                    continue
                exchange = self.env['edi.exchange'].create({
                    'profile_id': profile.id,
                    'channel_id': self.id,
                    'direction': 'in',
                    'raw_content': content,
                })
                exchange._process()
                try:
                    ftp.rename(filepath, f"{done_path}/{filename}")
                except Exception:
                    ftp.delete(filepath)
                _logger.info("EDI FTP: %s → profil '%s' (exchange %s)", filename, profile.name, exchange.name)

    def _poll_sftp(self):
        try:
            import paramiko
        except ImportError:
            raise ImportError("Le module 'paramiko' est requis pour SFTP (pip install paramiko)")
        remote_path = (self.remote_path or '/').rstrip('/')
        done_path = (self.done_path or '/done').rstrip('/')

        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(self.host, port=self.port or 22, username=self.username, password=self.password, timeout=self.timeout or 30)
            with ssh.open_sftp() as sftp:
                files = [f for f in sftp.listdir(remote_path) if f.lower().endswith(('.xml', '.json'))]
                for filename in files:
                    filepath = f"{remote_path}/{filename}"
                    buf = io.BytesIO()
                    sftp.getfo(filepath, buf)
                    content = buf.getvalue().decode('utf-8', errors='replace')
                    profile = self._find_profile_for_content(content)
                    if not profile:
                        _logger.warning("EDI SFTP: aucun profil entrant pour %s sur canal %s", filename, self.name)
                        continue
                    exchange = self.env['edi.exchange'].create({
                        'profile_id': profile.id,
                        'channel_id': self.id,
                        'direction': 'in',
                        'raw_content': content,
                    })
                    exchange._process()
                    try:
                        sftp.rename(filepath, f"{done_path}/{filename}")
                    except Exception:
                        sftp.remove(filepath)
                    _logger.info("EDI SFTP: %s → profil '%s' (exchange %s)", filename, profile.name, exchange.name)
