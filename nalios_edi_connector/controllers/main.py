import json
from odoo import http
from odoo.http import request


class EdiController(http.Controller):

    @http.route('/edi/receive/<string:token>', type='http', auth='none', methods=['POST'], csrf=False)
    def receive(self, token, **kwargs):
        env = request.env(user=1)

        channel = env['edi.channel'].search([
            ('token', '=', token),
            ('channel_type', '=', 'webhook'),
            ('active', '=', True),
        ], limit=1)
        if not channel:
            return self._json_response({'error': 'Invalid token'}, 401)

        profile = env['edi.profile'].search([
            ('channel_id', '=', channel.id),
            ('direction', 'in', ('in', 'both')),
            ('active', '=', True),
        ], limit=1)
        if not profile:
            return self._json_response({'error': 'No active inbound profile for this channel'}, 400)

        raw = request.httprequest.data.decode('utf-8')
        if not raw:
            return self._json_response({'error': 'Empty body'}, 400)

        exchange = env['edi.exchange'].create({
            'profile_id': profile.id,
            'channel_id': channel.id,
            'direction': 'in',
            'raw_content': raw,
        })
        exchange._process()

        status = 200 if exchange.state == 'done' else 422
        body = {
            'exchange': exchange.name,
            'state': exchange.state,
            'records_processed': exchange.record_count,
        }
        if exchange.error_log:
            body['error'] = exchange.error_log
        return self._json_response(body, status)

    def _json_response(self, data, status=200):
        return request.make_response(
            json.dumps(data),
            headers=[('Content-Type', 'application/json')],
            status=status,
        )
