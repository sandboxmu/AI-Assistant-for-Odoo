# ai_assistant/models/ai_assistant_config.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

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
    
    # Additional fields for compatibility with existing code
    provider = fields.Char('Provider', default='chatwhisperer', readonly=True)
    model_name = fields.Char('Model Name', default='chatwhisperer-bot', readonly=True)
    api_key = fields.Char('API Key')
    max_tokens = fields.Integer('Max Tokens', default=1000)
    temperature = fields.Float('Temperature', default=0.7)
    cost_per_1k_tokens = fields.Float('Cost per 1K Tokens', default=0.002)
    markup_percentage = fields.Float('Markup Percentage', default=300.0)
    credit_rate = fields.Float('Credit Rate', default=10.0)
    api_status = fields.Char('API Status', default='active', readonly=True)
    last_api_call = fields.Datetime('Last API Call')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model
    def get_active_config(self):
        config = self.search([('is_active', '=', True)], limit=1)
        if not config:
            # Create default config if none exists
            config = self.create({
                'name': 'Default Chat Whisperer Config',
                'chatbot_id': '1754325699224x235880637442555900',
                'is_active': True,
            })
        return config

    @api.constrains('is_active')
    def _ensure_only_one_active(self):
        for rec in self:
            if rec.is_active:
                others = self.search([('id', '!=', rec.id), ('is_active', '=', True)])
                if others:
                    others.write({'is_active': False})

    def calculate_credit_cost(self, tokens):
        """Calculate credit cost for given tokens"""
        self.ensure_one()
        cost_usd = (tokens / 1000) * self.cost_per_1k_tokens
        markup_multiplier = 1 + (self.markup_percentage / 100)
        return (cost_usd * markup_multiplier) * self.credit_rate

