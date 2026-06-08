from odoo import api, fields, models


class EdiTrigger(models.Model):
    _name = 'edi.trigger'
    _description = 'EDI Trigger'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    profile_id = fields.Many2one(
        'edi.profile', required=True, ondelete='cascade',
        domain=[('direction', 'in', ('out', 'both'))]
    )
    trigger_type = fields.Selection([
        ('on_create', 'Création'),
        ('on_create_or_write', 'Création ou modification'),
        ('on_unlink', 'Suppression'),
    ], required=True, default='on_create_or_write', string='Déclencheur')
    filter_domain = fields.Char(
        string='Condition (après)',
        help="Ex: [('state', '=', 'sale')] pour déclencher quand le record satisfait ce domaine"
    )
    filter_pre_domain = fields.Char(
        string='Condition (avant modification)',
        help="Ex: [('state', '!=', 'sale')] pour déclencher uniquement lors du changement vers l'état souhaité"
    )
    automation_id = fields.Many2one('base.automation', readonly=True, ondelete='set null', copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_automation()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_automation()
        return res

    def unlink(self):
        automations = self.sudo().mapped('automation_id')
        res = super().unlink()
        automations.sudo().unlink()
        return res

    def _sync_automation(self):
        for rec in self:
            if not rec.profile_id.model_id:
                continue
            code = f"env['edi.profile'].browse({rec.profile_id.id}).send_for_record(record)"
            vals = {
                'name': f"[EDI] {rec.name}",
                'model_id': rec.profile_id.model_id.id,
                'trigger': rec.trigger_type,
                'active': rec.active,
                'filter_domain': rec.filter_domain or False,
                'filter_pre_domain': rec.filter_pre_domain or False,
            }
            if rec.automation_id:
                rec.automation_id.sudo().write(vals)
                if rec.automation_id.action_server_ids:
                    rec.automation_id.action_server_ids[0].sudo().write({'code': code})
            else:
                vals['action_server_ids'] = [(0, 0, {
                    'name': f"[EDI] {rec.name}",
                    'model_id': rec.profile_id.model_id.id,
                    'state': 'code',
                    'code': code,
                })]
                rec.automation_id = self.env['base.automation'].sudo().create(vals)
