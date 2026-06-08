import json
import logging
from datetime import datetime
from xml.etree import ElementTree as ET

from odoo import api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class EdiExchange(models.Model):
    _name = 'edi.exchange'
    _description = 'EDI Exchange'
    _order = 'date desc, id desc'

    name = fields.Char(default='/', copy=False, readonly=True)
    profile_id = fields.Many2one('edi.profile', required=True, ondelete='restrict')
    channel_id = fields.Many2one('edi.channel', ondelete='set null')
    direction = fields.Selection([('in', 'Entrant'), ('out', 'Sortant')], required=True)
    state = fields.Selection([
        ('pending', 'En attente'),
        ('done', 'Succès'),
        ('error', 'Erreur'),
    ], default='pending', readonly=True)
    raw_content = fields.Text(string='Contenu')
    error_log = fields.Text(readonly=True)
    processed_ids_json = fields.Text(string='Records traités (JSON)', readonly=True)
    record_count = fields.Integer(compute='_compute_record_count', string='Records')
    date = fields.Datetime(default=fields.Datetime.now, readonly=True)

    def _compute_record_count(self):
        for rec in self:
            try:
                rec.record_count = len(json.loads(rec.processed_ids_json or '[]'))
            except Exception:
                rec.record_count = 0

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence'].next_by_code('edi.exchange')
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = seq or '/'
        return super().create(vals_list)

    def action_open_processed_records(self):
        self.ensure_one()
        try:
            records = json.loads(self.processed_ids_json or '[]')
        except Exception:
            records = []
        if not records:
            return False
        by_model = {}
        for r in records:
            by_model.setdefault(r['model'], []).append(r['id'])
        model = list(by_model.keys())[0]
        ids = by_model[model]
        model_rec = self.env['ir.model'].search([('model', '=', model)], limit=1)
        return {
            'type': 'ir.actions.act_window',
            'name': model_rec.name or model,
            'res_model': model,
            'view_mode': 'list,form',
            'domain': [('id', 'in', ids)],
        }

    def action_process(self):
        for rec in self:
            rec._process()
        return True

    def action_retry(self):
        for rec in self:
            rec.write({'state': 'pending', 'error_log': False})
            if rec.direction == 'out':
                rec._send()
            else:
                rec._process()
        return True

    def _send(self):
        import requests
        channel = self.channel_id
        timeout = (channel.timeout or 30) if channel else 30
        try:
            if not channel:
                raise ValueError("Aucun canal configuré sur le profil")
            content = (self.raw_content or '').encode('utf-8')
            content_type = 'application/json' if self.profile_id.format == 'json' else 'application/xml'
            if channel.channel_type == 'webhook':
                if not channel.remote_url:
                    raise ValueError("L'URL distante n'est pas configurée sur le canal")
                resp = requests.post(
                    channel.remote_url,
                    data=content,
                    headers={'Content-Type': content_type},
                    timeout=timeout,
                )
                resp.raise_for_status()
            elif channel.channel_type == 'ftp':
                self._send_ftp()
            elif channel.channel_type == 'sftp':
                self._send_sftp()
            elif channel.channel_type == 'manual':
                ext = 'json' if self.profile_id.format == 'json' else 'xml'
                self.env['ir.attachment'].create({
                    'name': f"{self.name}.{ext}",
                    'res_model': 'edi.exchange',
                    'res_id': self.id,
                    'raw': content,
                    'mimetype': content_type,
                })
            self.write({'state': 'done', 'error_log': False})
        except Exception as e:
            _logger.error("EDI _send error on %s: %s", self.name, e, exc_info=True)
            self.write({'state': 'error', 'error_log': str(e)})

    def _send_ftp(self):
        import ftplib, io
        ch = self.channel_id
        filename = ch._get_filename(self)
        with ftplib.FTP() as ftp:
            ftp.connect(ch.host, ch.port or 21, timeout=ch.timeout or 30)
            ftp.login(ch.username or '', ch.password or '')
            ftp.storbinary(
                f"STOR {(ch.remote_path or '/').rstrip('/')}/{filename}",
                io.BytesIO((self.raw_content or '').encode('utf-8'))
            )

    def _send_sftp(self):
        import io
        try:
            import paramiko
        except ImportError:
            raise ImportError("Le module 'paramiko' est requis pour SFTP (pip install paramiko)")
        ch = self.channel_id
        filename = ch._get_filename(self)
        with paramiko.SSHClient() as ssh:
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ch.host, port=ch.port or 22, username=ch.username, password=ch.password, timeout=ch.timeout or 30)
            with ssh.open_sftp() as sftp:
                sftp.putfo(
                    io.BytesIO((self.raw_content or '').encode('utf-8')),
                    f"{(ch.remote_path or '/').rstrip('/')}/{filename}"
                )

    def _process(self):
        profile = self.profile_id
        try:
            if profile.format == 'json':
                self._process_json()
            else:
                self._process_xml()
        except Exception as e:
            _logger.error("EDI Exchange %s processing error: %s", self.name, e, exc_info=True)
            self.write({'state': 'error', 'error_log': str(e)})

    def _process_xml(self):
        profile = self.profile_id
        root = ET.fromstring(self.raw_content)
        record_els = root.findall(f'.//{profile.xml_record_tag}')
        if not record_els and root.tag == profile.xml_record_tag:
            record_els = [root]

        Model = self.env[profile.model_name]
        mappings = profile.field_mapping_ids.sorted('sequence')
        key_mappings = mappings.filtered('is_key')
        rules = profile.action_rule_ids.filtered('active').sorted('sequence')
        processed = []

        for el in record_els:
            values = self._build_values_xml(el, mappings)
            for rule in rules:
                if rule.condition_code:
                    try:
                        if not safe_eval(rule.condition_code, {'values': values}):
                            continue
                    except Exception as e:
                        _logger.warning("EDI condition eval error on rule %s: %s", rule.name, e)
                        continue
                record = self._apply_rule(Model, values, key_mappings, rule)
                if record:
                    processed.append({'model': profile.model_name, 'id': record.id})

        self.write({'state': 'done', 'processed_ids_json': json.dumps(processed), 'error_log': False})

    def _process_json(self):
        profile = self.profile_id
        data = json.loads(self.raw_content)
        record_key = profile.xml_record_tag or 'record'
        root_key = profile.xml_root_tag

        if root_key and root_key in data:
            items = data[root_key]
            if isinstance(items, list):
                records_data = [item.get(record_key, item) if isinstance(item, dict) else item for item in items]
            else:
                records_data = [items.get(record_key, items)]
        elif record_key in data:
            records_data = [data[record_key]]
        elif isinstance(data, list):
            records_data = data
        else:
            records_data = [data]

        Model = self.env[profile.model_name]
        mappings = profile.field_mapping_ids.sorted('sequence')
        key_mappings = mappings.filtered('is_key')
        rules = profile.action_rule_ids.filtered('active').sorted('sequence')
        processed = []

        for item in records_data:
            values = self._build_values_json(item, mappings)
            for rule in rules:
                if rule.condition_code:
                    try:
                        if not safe_eval(rule.condition_code, {'values': values}):
                            continue
                    except Exception as e:
                        _logger.warning("EDI condition eval error on rule %s: %s", rule.name, e)
                        continue
                record = self._apply_rule(Model, values, key_mappings, rule)
                if record:
                    processed.append({'model': profile.model_name, 'id': record.id})

        self.write({'state': 'done', 'processed_ids_json': json.dumps(processed), 'error_log': False})

    def _build_values_xml(self, element, mappings):
        values = {}
        for mapping in mappings:
            raw = self._extract_xml(element, mapping.source_path)
            if raw is None and mapping.default_value is not None:
                raw = mapping.default_value
            if raw is not None:
                transformed = self._transform(raw, mapping)
                if transformed is not None:
                    values[mapping.odoo_field_name] = transformed
        return values

    def _build_values_json(self, item, mappings):
        values = {}
        for mapping in mappings:
            raw = item.get(mapping.source_path) if isinstance(item, dict) else None
            if raw is None and mapping.default_value is not None:
                raw = mapping.default_value
            if raw is not None:
                transformed = self._transform(str(raw), mapping)
                if transformed is not None:
                    values[mapping.odoo_field_name] = transformed
        return values

    # Compat alias for XML
    def _build_values(self, element, mappings, Model=None):
        return self._build_values_xml(element, mappings)

    def _extract_xml(self, element, path):
        if path.startswith('@'):
            return element.get(path[1:])
        found = element.find(path)
        return found.text if found is not None else None

    # Compat alias
    def _extract(self, element, path):
        return self._extract_xml(element, path)

    def _transform(self, value, mapping):
        t = mapping.transformer
        try:
            if t == 'none':
                return value
            if t == 'float':
                return float(str(value).replace(',', '.'))
            if t == 'int':
                return int(value)
            if t == 'bool':
                return str(value).lower() in ('true', '1', 'yes', 'oui')
            if t == 'date':
                return datetime.strptime(value, '%Y-%m-%d').date()
            if t == 'date_dmy':
                return datetime.strptime(value, '%d/%m/%Y').date()
            if t in ('m2o_name', 'm2o_ref'):
                relation = mapping.odoo_field_id.relation
                search_field = mapping.m2o_search_field or ('ref' if t == 'm2o_ref' else 'name')
                rec = self.env[relation].search([(search_field, '=', value)], limit=1)
                return rec.id or False
            if t == 'python':
                return safe_eval(mapping.transform_code or 'value', {'value': value})
        except Exception as e:
            _logger.warning("EDI transform error (field %s, value %r): %s", mapping.odoo_field_name, value, e)
        return value

    def _build_key_domain(self, key_mappings, values):
        return [(m.odoo_field_name, '=', values[m.odoo_field_name]) for m in key_mappings if m.odoo_field_name in values]

    def _apply_rule(self, Model, values, key_mappings, rule):
        domain = self._build_key_domain(key_mappings, values)
        existing = Model.search(domain, limit=1) if domain else Model.browse()

        if rule.action_type == 'create':
            return Model.create(values)
        if rule.action_type == 'update' and existing:
            existing.write(values)
            return existing
        if rule.action_type == 'upsert':
            if existing:
                existing.write(values)
                return existing
            return Model.create(values)
        if rule.action_type == 'call_method' and rule.method_name and existing:
            getattr(existing, rule.method_name)()
            return existing
        if rule.action_type == 'notify' and existing:
            existing.message_post(body=f"EDI {self.name}: enregistrement traité via profil {self.profile_id.name}")
            return existing
        return Model.browse()
