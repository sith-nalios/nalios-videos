import base64
import logging

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class As2Controller(http.Controller):

    @http.route('/edi/as2/receive/<string:token>', type='http', auth='public', methods=['POST'], csrf=False)
    def as2_receive(self, token, **kwargs):
        try:
            from pyas2lib import as2
        except ImportError:
            return Response('pyas2lib not installed', status=500)

        channel = request.env['edi.channel'].sudo().search([
            ('token', '=', token), ('channel_type', '=', 'as2'), ('active', '=', True),
        ], limit=1)
        if not channel:
            return Response('Not Found', status=404)

        raw_headers = ''.join(f"{k}: {v}\r\n" for k, v in request.httprequest.headers.items()).encode()
        raw_data = raw_headers + b'\r\n' + request.httprequest.data

        org = channel._as2_org()

        def find_org(as2_name):
            return org if as2_name == channel.as2_own_id else None

        def find_partner(as2_name):
            if as2_name == channel.as2_partner_as2_id:
                return channel._as2_partner(mdn_mode=None)
            return None

        message = as2.Message()
        status, _, mdn = message.parse(raw_data, find_org_cb=find_org, find_partner_cb=find_partner)

        if status == 'processed' and message.content:
            content = message.content.decode('utf-8', errors='replace')
            profile = channel._find_profile_for_content(content)
            if profile:
                exchange = request.env['edi.exchange'].sudo().create({
                    'profile_id': profile.id,
                    'channel_id': channel.id,
                    'direction': 'in',
                    'raw_content': content,
                })
                exchange._process()
            else:
                _logger.warning("EDI AS2: aucun profil entrant sur canal %s", channel.name)
        else:
            _logger.warning("EDI AS2: statut '%s' sur canal %s", status, channel.name)

        if mdn:
            return Response(mdn.content, headers=dict(mdn.headers), status=200)
        return Response('OK', status=200)

    @http.route('/edi/as2/mdn/<string:token>', type='http', auth='public', methods=['POST'], csrf=False)
    def as2_mdn_async(self, token, **kwargs):
        _logger.info("EDI AS2: MDN asynchrone reçu pour canal token=%s", token)
        return Response('OK', status=200)
