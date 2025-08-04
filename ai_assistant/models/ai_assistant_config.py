# ai_assistant_config.py

from odoo import models, fields, api

class AssistantConfig(models.Model):
    _name = 'ai.assistant.config'
    _description = 'Chat Whisperer Assistant Configuration'

    name = fields.Char('Configuration Name', required=True)
    chatbot_id = fields.Char(
        string='Chat Whisperer Bot ID',
        required=True,
        default="1754325699224x235880637442555900"
    )
    is_active = fields.Boolean('Use This Configuration', default=False)

    @api.model
    def get_active_config(self):
        config = self.search([('is_active', '=', True)], limit=1)
        if not config:
            raise ValueError("No active Chat Whisperer config found.")
        return config
