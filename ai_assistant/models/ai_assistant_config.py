# ai_assistant_config.py

from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AssistantConfig(models.Model):
    _name = 'ai.assistant.config'
    _description = 'Chat Whisperer Assistant Configuration'
    _rec_name = 'name'

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
            raise UserError(_("No active Chat Whisperer configuration found. Please create and activate one in settings."))
        return config

    @api.constrains('is_active')
    def _ensure_only_one_active(self):
        for rec in self:
            if rec.is_active:
                others = self.search([('id', '!=', rec.id), ('is_active', '=', True)])
                if others:
                    raise UserError(_("Only one Chat Whisperer configuration can be active at a time."))

