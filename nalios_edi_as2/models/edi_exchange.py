import logging

from odoo import models

_logger = logging.getLogger(__name__)


class EdiExchange(models.Model):
    _inherit = 'edi.exchange'

    def _send(self):
        if self.channel_id.channel_type != 'as2':
            return super()._send()
        try:
            self.channel_id._send_as2(self)
            self.write({'state': 'done', 'error_log': False})
        except Exception as e:
            _logger.error("EDI AS2 _send error on %s: %s", self.name, e, exc_info=True)
            self.write({'state': 'error', 'error_log': str(e)})
