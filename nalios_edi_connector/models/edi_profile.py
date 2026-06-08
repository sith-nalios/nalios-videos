import json
from odoo import models, fields


class EdiProfile(models.Model):
    _name = 'edi.profile'
    _description = 'EDI Profile'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    format = fields.Selection([('xml', 'XML'), ('json', 'JSON')], required=True, default='xml')
    direction = fields.Selection([
        ('in', 'Entrant'),
        ('out', 'Sortant'),
        ('both', 'Les deux'),
    ], required=True, default='in')
    model_id = fields.Many2one('ir.model', required=True, ondelete='cascade', string='Modèle Odoo')
    model_name = fields.Char(related='model_id.model', store=True)
    channel_id = fields.Many2one('edi.channel', string='Canal')
    xml_root_tag = fields.Char(string='Tag racine XML', help="Tag racine du document (ex: Orders). Sert aussi à identifier le profil lors du polling FTP multi-profils.")
    xml_record_tag = fields.Char(string='Tag enregistrement', help="Tag représentant un enregistrement (ex: Order). Requis pour XML.")
    batch_size = fields.Integer(default=0, string='Taille de lot', help="Nombre max d'enregistrements par fichier sortant. 0 = pas de limite.")
    field_mapping_ids = fields.One2many('edi.field.mapping', 'profile_id', string='Mappings de champs')
    action_rule_ids = fields.One2many('edi.action.rule', 'profile_id', string="Règles d'action")
    exchange_count = fields.Integer(compute='_compute_exchange_count', string='Échanges')

    def _compute_exchange_count(self):
        data = self.env['edi.exchange']._read_group([('profile_id', 'in', self.ids)], ['profile_id'], ['__count'])
        counts = {profile.id: count for profile, count in data}
        for rec in self:
            rec.exchange_count = counts.get(rec.id, 0)

    def action_view_exchanges(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Échanges',
            'res_model': 'edi.exchange',
            'view_mode': 'list,form',
            'domain': [('profile_id', '=', self.id)],
            'context': {'default_profile_id': self.id},
        }

    def send_for_record(self, record):
        self.ensure_one()
        if isinstance(record, int):
            record = self.env[self.model_name].browse(record)
        return self.send_for_records(record)

    def send_for_records(self, records):
        self.ensure_one()
        if isinstance(records, (int, list)):
            records = self.env[self.model_name].browse(records)
        batch_size = self.batch_size or len(records)
        batches = [records[i:i + batch_size] for i in range(0, len(records), batch_size)] if batch_size else [records]
        for batch in batches:
            content = self._build_content_for_records(batch)
            exchange = self.env['edi.exchange'].create({
                'profile_id': self.id,
                'channel_id': self.channel_id.id if self.channel_id else False,
                'direction': 'out',
                'raw_content': content,
            })
            exchange._send()
        return True

    def _build_content_for_records(self, records):
        if self.format == 'json':
            return self._build_json_for_records(records)
        return self._build_xml_for_records(records)

    def _build_xml_for_records(self, records):
        from xml.etree import ElementTree as ET
        items = [self._build_xml_element(r) for r in records]
        if self.xml_root_tag:
            wrapper = ET.Element(self.xml_root_tag)
            for item in items:
                wrapper.append(item)
            return ET.tostring(wrapper, encoding='unicode')
        if len(items) == 1:
            return ET.tostring(items[0], encoding='unicode')
        wrapper = ET.Element('Records')
        for item in items:
            wrapper.append(item)
        return ET.tostring(wrapper, encoding='unicode')

    def _build_xml_element(self, record):
        from xml.etree import ElementTree as ET
        root = ET.Element(self.xml_record_tag or 'Record')
        for mapping in self.field_mapping_ids.sorted('sequence'):
            value = record[mapping.odoo_field_name]
            if value is False or value is None:
                text = mapping.default_value or ''
            elif hasattr(value, 'display_name'):
                text = value.display_name or ''
            else:
                text = str(value)
            path = mapping.source_path
            if path.startswith('@'):
                root.set(path[1:], text)
            else:
                self._set_xml_element(root, path, text)
        return root

    def _build_json_for_records(self, records):
        items = [self._build_json_dict(r) for r in records]
        root_key = self.xml_root_tag or 'records'
        record_key = self.xml_record_tag or 'record'
        if len(items) == 1 and not self.xml_root_tag:
            return json.dumps({record_key: items[0]}, ensure_ascii=False, indent=2)
        return json.dumps({root_key: [{record_key: item} for item in items]}, ensure_ascii=False, indent=2)

    def _build_json_dict(self, record):
        result = {}
        for mapping in self.field_mapping_ids.sorted('sequence'):
            value = record[mapping.odoo_field_name]
            if value is False or value is None:
                result[mapping.source_path] = mapping.default_value or None
            elif hasattr(value, 'display_name'):
                result[mapping.source_path] = value.display_name or None
            else:
                result[mapping.source_path] = value
        return result

    def _set_xml_element(self, parent, path, text):
        from xml.etree import ElementTree as ET
        parts = path.lstrip('./').split('/')
        el = parent
        for part in parts[:-1]:
            existing = el.find(part)
            el = existing if existing is not None else ET.SubElement(el, part)
        ET.SubElement(el, parts[-1]).text = text

    # Compat alias
    def _build_xml_for_record(self, record):
        from xml.etree import ElementTree as ET
        el = self._build_xml_element(record)
        if self.xml_root_tag:
            wrapper = ET.Element(self.xml_root_tag)
            wrapper.append(el)
            return ET.tostring(wrapper, encoding='unicode')
        return ET.tostring(el, encoding='unicode')
