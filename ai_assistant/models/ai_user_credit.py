from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)

class AIUserCredit(models.Model):
    _name = 'ai.user.credit'
    _description = 'AI User Credits'
    _rec_name = 'user_id'

    user_id = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    # Credit tracking
    total_credits = fields.Float(string='Total Credits', default=10.0, help='Total credits purchased/granted')
    used_credits = fields.Float(string='Used Credits', default=0.0, help='Credits consumed')
    remaining_credits = fields.Float(string='Remaining Credits', compute='_compute_remaining_credits', store=True)
    
    # Subscription info (for future subscription feature)
    subscription_id = fields.Many2one('ai.subscription', string='Active Subscription')
    subscription_start = fields.Datetime(string='Subscription Start')
    subscription_end = fields.Datetime(string='Subscription End')
    is_subscription_active = fields.Boolean(string='Subscription Active', compute='_compute_subscription_status')
    
    # Usage tracking
    total_messages_sent = fields.Integer(string='Total Messages', default=0)
    total_tokens_used = fields.Integer(string='Total Tokens', default=0)
    total_spent_usd = fields.Float(string='Total Spent (USD)', default=0.0)
    last_usage_date = fields.Datetime(string='Last Usage')
    
    # Account status
    is_active = fields.Boolean(string='Account Active', default=True)
    credit_limit = fields.Float(string='Credit Limit', default=1000.0, help='Maximum credits user can have')
    low_credit_warning_sent = fields.Boolean(string='Low Credit Warning Sent', default=False)
    
    # Credit transactions
    credit_transaction_ids = fields.One2many('ai.credit.transaction', 'user_credit_id', string='Credit Transactions')

    @api.depends('total_credits', 'used_credits')
    def _compute_remaining_credits(self):
        for record in self:
            record.remaining_credits = record.total_credits - record.used_credits

    @api.depends('subscription_end', 'subscription_start')
    def _compute_subscription_status(self):
        now = fields.Datetime.now()
        for record in self:
            record.is_subscription_active = (
                record.subscription_start and record.subscription_end and
                record.subscription_start <= now <= record.subscription_end
            )

    @api.model
    def get_or_create_user_credit(self, user_id=None):
        """Get or create user credit record"""
        if not user_id:
            user_id = self.env.user.id
        
        credit = self.search([('user_id', '=', user_id)], limit=1)
        if not credit:
            # Create new user with free credits
            free_credits = self.env['ir.config_parameter'].sudo().get_param('ai_assistant.free_credits', '10.0')
            credit = self.create({
                'user_id': user_id,
                'total_credits': float(free_credits),
                'used_credits': 0.0,
            })
            
            # Create welcome transaction
            self.env['ai.credit.transaction'].create({
                'user_credit_id': credit.id,
                'transaction_type': 'bonus',
                'amount': float(free_credits),
                'description': 'Welcome bonus - Free credits to get started!',
                'balance_before': 0.0,
                'balance_after': float(free_credits),
            })
            
            _logger.info(f"Created new AI credit account for user {user_id} with {free_credits} free credits")
        
        return credit

    def consume_credits(self, amount, message_id=None, description=None):
        """Consume credits for AI usage"""
        self.ensure_one()
        
        # Check if subscription is active (unlimited usage)
        if self.is_subscription_active:
            # Don't deduct credits for subscription users, just track usage
            self.total_messages_sent += 1
            self.last_usage_date = fields.Datetime.now()
            
            # Still create transaction for tracking
            self.env['ai.credit.transaction'].create({
                'user_credit_id': self.id,
                'transaction_type': 'subscription',
                'amount': 0,  # No charge for subscription users
                'description': description or f'Subscription usage - {amount} credits worth',
                'message_id': message_id,
                'balance_before': self.remaining_credits,
                'balance_after': self.remaining_credits,
            })
            return
        
        # Check credit balance
        if self.remaining_credits < amount:
            raise exceptions.UserError(
                f"Insufficient credits. You have {self.remaining_credits:.2f} credits remaining. "
                f"This action requires {amount:.2f} credits. Please purchase more credits to continue."
            )
        
        # Record balance before transaction
        balance_before = self.remaining_credits
        
        # Consume credits
        self.used_credits += amount
        self.total_messages_sent += 1
        self.last_usage_date = fields.Datetime.now()
        
        # Create transaction record
        self.env['ai.credit.transaction'].create({
            'user_credit_id': self.id,
            'transaction_type': 'usage',
            'amount': -amount,
            'description': description or f'AI message usage',
            'message_id': message_id,
            'balance_before': balance_before,
            'balance_after': self.remaining_credits,
        })
        
        # Check for low credit warning
        if self.remaining_credits < 5.0 and not self.low_credit_warning_sent:
            self._send_low_credit_warning()
        
        # Reset warning flag if credits are topped up
        if self.remaining_credits >= 10.0:
            self.low_credit_warning_sent = False

    def add_credits(self, amount, description=None, invoice_id=None, transaction_type='purchase'):
        """Add credits to user account"""
        self.ensure_one()
        
        if amount <= 0:
            raise exceptions.ValidationError("Credit amount must be positive")
        
        # Check credit limit
        if self.total_credits + amount > self.credit_limit:
            raise exceptions.UserError(
                f"Adding {amount} credits would exceed your credit limit of {self.credit_limit}. "
                f"Please contact support for higher limits."
            )
        
        # Record balance before transaction
        balance_before = self.remaining_credits
        
        # Add credits
        self.total_credits += amount
        
        # Convert credits to USD for tracking
        config = self.env['ai.assistant.config'].get_active_config()
        usd_amount = amount / config.credit_rate
        self.total_spent_usd += usd_amount
        
        # Create transaction record
        self.env['ai.credit.transaction'].create({
            'user_credit_id': self.id,
            'transaction_type': transaction_type,
            'amount': amount,
            'description': description or f'Credit {transaction_type}',
            'invoice_id': invoice_id,
            'balance_before': balance_before,
            'balance_after': self.remaining_credits,
        })
        
        # Reset low credit warning
        self.low_credit_warning_sent = False
        
        _logger.info(f"Added {amount} credits to user {self.user_id.name} (ID: {self.user_id.id})")

    def check_usage_limit(self, tokens_to_use=0):
        """Check if user can make AI request"""
        self.ensure_one()
        
        if not self.is_active:
            return False, "Account is inactive. Please contact support."
        
        # Calculate estimated credit cost
        if tokens_to_use > 0:
            config = self.env['ai.assistant.config'].get_active_config()
            estimated_cost = config.calculate_credit_cost(tokens_to_use)
        else:
            estimated_cost = 0.1  # Default minimum cost
        
        # Subscription users have unlimited usage
        if self.is_subscription_active:
            return True, "Subscription active - unlimited usage"
        
        # Check credit balance
        if self.remaining_credits >= estimated_cost:
            return True, f"Sufficient credits ({self.remaining_credits:.2f} remaining)"
        
        return False, f"Insufficient credits. Need {estimated_cost:.2f}, have {self.remaining_credits:.2f}"

    def get_usage_summary(self, days=30):
        """Get usage summary for the user"""
        self.ensure_one()
        
        from datetime import datetime, timedelta
        date_from = datetime.now() - timedelta(days=days)
        
        # Get recent transactions
        recent_transactions = self.credit_transaction_ids.filtered(
            lambda t: t.create_date >= date_from
        )
        
        # Calculate metrics
        usage_transactions = recent_transactions.filtered(lambda t: t.transaction_type == 'usage')
        purchase_transactions = recent_transactions.filtered(lambda t: t.transaction_type == 'purchase')
        
        credits_used = sum(abs(t.amount) for t in usage_transactions)
        credits_purchased = sum(t.amount for t in purchase_transactions)
        messages_sent = len(usage_transactions)
        
        return {
            'period_days': days,
            'credits_used': credits_used,
            'credits_purchased': credits_purchased,
            'messages_sent': messages_sent,
            'avg_credits_per_message': credits_used / max(messages_sent, 1),
            'current_balance': self.remaining_credits,
            'total_spent_usd': self.total_spent_usd,
            'subscription_active': self.is_subscription_active,
        }

    def _send_low_credit_warning(self):
        """Send low credit warning to user"""
        self.ensure_one()
        
        # Mark warning as sent
        self.low_credit_warning_sent = True
        
        # You can implement email notification here
        # For now, just log the warning
        _logger.info(f"Low credit warning for user {self.user_id.name} (ID: {self.user_id.id}) - {self.remaining_credits:.2f} credits remaining")
        
        # Could send notification to user interface
        self.env['bus.bus']._sendone(
            self.user_id.partner_id,
            'ai_assistant.low_credits',
            {
                'message': f'Low credits: {self.remaining_credits:.2f} remaining',
                'remaining_credits': self.remaining_credits,
                'user_id': self.user_id.id,
            }
        )

    def reset_account(self):
        """Reset account (admin only)"""
        self.ensure_one()
        
        # Check permissions
        if not self.env.user.has_group('base.group_system'):
            raise exceptions.AccessError("Only system administrators can reset accounts")
        
        # Reset counters
        self.used_credits = 0.0
        self.total_messages_sent = 0
        self.total_tokens_used = 0
        self.low_credit_warning_sent = False
        self.is_active = True
        
        # Create reset transaction
        self.env['ai.credit.transaction'].create({
            'user_credit_id': self.id,
            'transaction_type': 'bonus',
            'amount': 0,
            'description': 'Account reset by administrator',
            'balance_before': self.remaining_credits,
            'balance_after': self.remaining_credits,
        })
        
        _logger.info(f"Reset AI credit account for user {self.user_id.name} (ID: {self.user_id.id})")

# Credit Transaction Model
class AICreditTransaction(models.Model):
    _name = 'ai.credit.transaction'
    _description = 'AI Credit Transactions'
    _order = 'create_date desc'

    user_credit_id = fields.Many2one('ai.user.credit', string='User Credit', required=True, ondelete='cascade')
    user_id = fields.Many2one(related='user_credit_id.user_id', string='User', store=True)
    
    transaction_type = fields.Selection([
        ('purchase', 'Credit Purchase'),
        ('usage', 'Credit Usage'),
        ('refund', 'Refund'),
        ('bonus', 'Bonus Credits'),
        ('subscription', 'Subscription Usage'),
    ], string='Type', required=True)
    
    amount = fields.Float(string='Amount', required=True, help='Positive for additions, negative for usage')
    description = fields.Text(string='Description')
    
    # Related records
    message_id = fields.Many2one('ai.message', string='Related Message')
    invoice_id = fields.Many2one('account.move', string='Related Invoice')
    
    # Balance tracking
    balance_before = fields.Float(string='Balance Before')
    balance_after = fields.Float(string='Balance After')
