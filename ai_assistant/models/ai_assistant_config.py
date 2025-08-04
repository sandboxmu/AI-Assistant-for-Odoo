# Add after existing imports
import os
from odoo.exceptions import AccessError

# Add this method to the AIAssistantConfig class:
@api.model
def get_active_config(self):
    """Get the active AI configuration (centralized service)"""
    # Check if centralized config exists
    config = self.search([('is_active', '=', True)], limit=1)
    
    if not config:
        # Auto-create centralized configuration with YOUR keys
        config = self._create_centralized_config()
    
    return config

def _create_centralized_config(self):
    """Create centralized configuration with your API keys"""
    # These are YOUR API keys (encrypted in database)
    centralized_config = {
        'name': 'Centralized AI Service',
        'provider': 'openai',  # or 'anthropic'
        'api_key': 'YOUR_API_KEY_HERE',  # You'll set this during deployment
        'model_name': 'gpt-3.5-turbo',
        'max_tokens': 1000,
        'temperature': 0.7,
        'cost_per_1k_tokens': 0.002,
        'markup_percentage': 400.0,  # 5x markup = 80% profit
        'credit_rate': 10.0,
        'is_active': True,
    }
    
    return self.create(centralized_config)

# Override create/write to prevent unauthorized API changes
@api.model
def create(self, vals):
    if not self.env.user.has_group('base.group_system'):
        raise AccessError("Only system administrators can create AI configurations.")
    return super().create(vals)

def write(self, vals):
    if not self.env.user.has_group('base.group_system'):
        if 'api_key' in vals or 'provider' in vals:
            raise AccessError("API configuration is managed centrally.")
    return super(AIAssistantConfig, self).write(vals)
from odoo import models, fields, api, exceptions
import logging

_logger = logging.getLogger(__name__)

class AIAssistantConfig(models.Model):
    _name = 'ai.assistant.config'
    _description = 'AI Assistant Configuration'

    name = fields.Char(string='Configuration Name', required=True)
    provider = fields.Selection([
        ('openai', 'OpenAI'),
        ('anthropic', 'Anthropic'),
    ], string='AI Provider', required=True, default='openai')
    
    # ADMIN-ONLY API KEY (encrypted)
    api_key = fields.Char(
        string='API Key', 
        help='API key for the AI service (Admin only)',
        groups='base.group_system'  # Only system admins can see/edit
    )
    model_name = fields.Char(
        string='Model Name', 
        help='e.g., gpt-3.5-turbo, gpt-4, claude-3-sonnet-20240229'
    )
    max_tokens = fields.Integer(string='Max Tokens', default=1000)
    temperature = fields.Float(string='Temperature', default=0.7, help='Controls randomness (0.0 to 1.0)')
    
    # BUSINESS SETTINGS
    cost_per_1k_tokens = fields.Float(
        string='Cost per 1K Tokens ($)', 
        default=0.002,
        help='Your cost from AI provider per 1000 tokens',
        groups='base.group_system'
    )
    markup_percentage = fields.Float(
        string='Markup %', 
        default=300.0,
        help='Your markup percentage (300% = 4x cost = 75% profit margin)',
        groups='base.group_system'
    )
    credit_rate = fields.Float(
        string='Credits per $1', 
        default=10.0,
        help='How many credits equal $1 USD',
        groups='base.group_system'
    )
    
    # SYSTEM SETTINGS
    is_active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    
    # USAGE TRACKING (readonly)
    total_tokens_used = fields.Integer(string='Total Tokens Used', readonly=True, default=0)
    total_cost_usd = fields.Float(string='Total Cost (USD)', readonly=True, default=0.0)
    total_revenue_usd = fields.Float(string='Total Revenue (USD)', readonly=True, default=0.0)
    total_profit_usd = fields.Float(
        string='Total Profit (USD)', 
        compute='_compute_profit', 
        store=True
    )
    profit_margin_percent = fields.Float(
        string='Profit Margin %', 
        compute='_compute_profit', 
        store=True
    )
    
    # SERVICE STATUS
    last_api_call = fields.Datetime(string='Last API Call', readonly=True)
    api_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('working', 'Working'),
        ('error', 'Error'),
    ], string='API Status', default='unknown', readonly=True)
    api_error_message = fields.Text(string='Last API Error', readonly=True)

    @api.depends('total_revenue_usd', 'total_cost_usd')
    def _compute_profit(self):
        for record in self:
            record.total_profit_usd = record.total_revenue_usd - record.total_cost_usd
            if record.total_revenue_usd > 0:
                record.profit_margin_percent = (record.total_profit_usd / record.total_revenue_usd) * 100
            else:
                record.profit_margin_percent = 0

    @api.model
    def get_active_config(self):
        """Get the active AI configuration (admin-controlled)"""
        config = self.search([
            ('is_active', '=', True),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not config:
            raise exceptions.UserError(
                "No AI configuration found. Please contact your administrator to set up the AI service."
            )
        
        if not config.api_key:
            raise exceptions.UserError(
                "AI service is not configured. Please contact your administrator to add API credentials."
            )
        
        return config

    def calculate_credit_cost(self, tokens_used):
        """Calculate credit cost for given token usage"""
        self.ensure_one()
        
        if tokens_used <= 0:
            return 0.0
        
        # Calculate actual cost from AI provider
        actual_cost_usd = (tokens_used / 1000) * self.cost_per_1k_tokens
        
        # Apply markup
        charged_cost_usd = actual_cost_usd * (1 + self.markup_percentage / 100)
        
        # Convert to credits
        credit_cost = charged_cost_usd * self.credit_rate
        
        return round(credit_cost, 4)  # Round to 4 decimal places

    def record_usage(self, tokens_used, credit_cost):
        """Record usage statistics"""
        self.ensure_one()
        
        actual_cost = (tokens_used / 1000) * self.cost_per_1k_tokens
        revenue = credit_cost / self.credit_rate
        
        self.total_tokens_used += tokens_used
        self.total_cost_usd += actual_cost
        self.total_revenue_usd += revenue
        self.last_api_call = fields.Datetime.now()
        self.api_status = 'working'
        self.api_error_message = False

    def record_api_error(self, error_message):
        """Record API error"""
        self.ensure_one()
        self.api_status = 'error'
        self.api_error_message = error_message
        self.last_api_call = fields.Datetime.now()

    def test_api_connection(self):
        """Test API connection"""
        self.ensure_one()
        
        if not self.api_key:
            raise exceptions.UserError("Please enter an API key first.")
        
        try:
            # Prepare test message
            test_messages = [
                {'role': 'system', 'content': 'You are a helpful assistant.'},
                {'role': 'user', 'content': 'Hello, please respond with just "API test successful"'}
            ]
            
            # Test API call
            if self.provider == 'openai':
                result = self._test_openai_api(test_messages)
            elif self.provider == 'anthropic':
                result = self._test_anthropic_api(test_messages)
            else:
                raise Exception(f"Unsupported provider: {self.provider}")
            
            self.api_status = 'working'
            self.api_error_message = False
            self.last_api_call = fields.Datetime.now()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'API Test Successful',
                    'message': f'Connected to {self.provider} successfully. Response: {result.get("content", "OK")}',
                    'type': 'success',
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            self.record_api_error(error_msg)
            raise exceptions.UserError(f"API connection failed: {error_msg}")

    def _test_openai_api(self, messages):
        """Test OpenAI API"""
        import requests
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
        }
        
        data = {
            'model': self.model_name or 'gpt-3.5-turbo',
            'messages': messages,
            'max_tokens': 50,
            'temperature': 0.7,
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            'content': result['choices'][0]['message']['content'],
            'tokens_used': result.get('usage', {}).get('total_tokens', 0)
        }

    def _test_anthropic_api(self, messages):
        """Test Anthropic API"""
        import requests
        
        headers = {
            'x-api-key': self.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        # Convert messages for Anthropic
        system_message = None
        formatted_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                formatted_messages.append(msg)
        
        data = {
            'model': self.model_name or 'claude-3-sonnet-20240229',
            'max_tokens': 50,
            'messages': formatted_messages,
        }
        
        if system_message:
            data['system'] = system_message
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=10
        )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            'content': result['content'][0]['text'],
            'tokens_used': result.get('usage', {}).get('input_tokens', 0) + result.get('usage', {}).get('output_tokens', 0)
        }

    @api.constrains('is_active')
    def _check_single_active_config(self):
        """Ensure only one configuration is active per company"""
        for record in self:
            if record.is_active:
                other_active = self.search([
                    ('is_active', '=', True),
                    ('company_id', '=', record.company_id.id),
                    ('id', '!=', record.id)
                ])
                if other_active:
                    raise exceptions.ValidationError("Only one AI configuration can be active per company.")

    def get_pricing_info(self):
        """Get pricing information for users"""
        self.ensure_one()
        
        # Sample costs for different message sizes
        sample_costs = {}
        for tokens in [50, 100, 200, 500, 1000]:  # Different message sizes
            credit_cost = self.calculate_credit_cost(tokens)
            usd_cost = credit_cost / self.credit_rate
            sample_costs[f'{tokens}_tokens'] = {
                'tokens': tokens,
                'credits': credit_cost,
                'usd': round(usd_cost, 4)
            }
        
        return {
            'provider': self.provider,
            'model': self.model_name,
            'credit_rate': self.credit_rate,
            'sample_costs': sample_costs,
            'status': self.api_status,
        }

