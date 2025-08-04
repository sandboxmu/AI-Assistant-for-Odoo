from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AIConversation(models.Model):
    _name = 'ai.conversation'
    _description = 'AI Conversation'
    _order = 'create_date desc'
    _rec_name = 'title'

    title = fields.Char(string='Title', required=True, default='New Conversation')
    user_id = fields.Many2one('res.users', string='User', required=True, default=lambda self: self.env.user)
    message_ids = fields.One2many('ai.message', 'conversation_id', string='Messages')
    message_count = fields.Integer(string='Message Count', compute='_compute_message_count')
    last_message_date = fields.Datetime(string='Last Message', compute='_compute_last_message_date')
    is_active = fields.Boolean(string='Active', default=True)
    context_info = fields.Text(string='Context Information', help='Additional context about user\'s current Odoo session')
    
    # Analytics fields
    total_tokens_used = fields.Integer(string='Total Tokens Used', compute='_compute_analytics', store=True)
    total_cost_usd = fields.Float(string='Total Cost (USD)', compute='_compute_analytics', store=True)
    total_credits_used = fields.Float(string='Total Credits Used', compute='_compute_analytics', store=True)

    @api.depends('message_ids')
    def _compute_message_count(self):
        for record in self:
            record.message_count = len(record.message_ids)

    @api.depends('message_ids.create_date')
    def _compute_last_message_date(self):
        for record in self:
            if record.message_ids:
                record.last_message_date = max(record.message_ids.mapped('create_date'))
            else:
                record.last_message_date = False

    @api.depends('message_ids.tokens_used', 'message_ids.credit_cost', 'message_ids.actual_cost_usd')
    def _compute_analytics(self):
        for record in self:
            ai_messages = record.message_ids.filtered(lambda m: not m.is_user_message)
            record.total_tokens_used = sum(ai_messages.mapped('tokens_used'))
            record.total_cost_usd = sum(ai_messages.mapped('actual_cost_usd'))
            record.total_credits_used = su
