from odoo import models, fields, api, exceptions
import requests
import json
import logging
import time

_logger = logging.getLogger(__name__)

class AIMessage(models.Model):
    _name = 'ai.message'
    _description = 'AI Message'
    _order = 'create_date asc'

    conversation_id = fields.Many2one('ai.conversation', string='Conversation', required=True, ondelete='cascade')
    content = fields.Text(string='Content', required=True)
    is_user_message = fields.Boolean(string='Is User Message', default=True)
    tokens_used = fields.Integer(string='Tokens Used')
    response_time = fields.Float(string='Response Time (seconds)')
    error_message = fields.Text(string='Error Message')
    
    # Business metrics
    credit_cost = fields.Float(string='Credit Cost', help='Credits charged to user')
    actual_cost_usd = fields.Float(string='Actual Cost (USD)', help='Your cost to AI provider')
    revenue_usd = fields.Float(string='Revenue (USD)', help='Revenue from user')
    markup_applied = fields.Float(string='Markup %', help='Markup percentage applied')

    @api.model
    def send_message_to_ai(self, conversation_id, user_message):
        """Send message to AI with centralized billing"""
        try:
            # Get ADMIN-controlled configuration (with your API keys)
            config = self.env['ai.assistant.config'].get_active_config()
            
            # Check user credits
            user_credit = self.env['ai.user.credit'].get_or_create_user_credit()
            
            # Estimate credit cost (conservative estimate)
            estimated_tokens = len(user_message.split()) * 1.5  # Conservative estimate
            estimated_credit_cost = config.calculate_credit_cost(estimated_tokens)
            
            # Check if user has enough credits
            if user_credit.remaining_credits < estimated_credit_cost:
                return {
                    'error': True,
                    'message': f"Insufficient credits. You need {estimated_credit_cost:.2f} credits, but only have {user_credit.remaining_credits:.2f}. Please purchase more credits.",
                    'insufficient_credits': True,
                    'remaining_credits': user_credit.remaining_credits,
                    'required_credits': estimated_credit_cost,
                }

            # Create user message
            user_msg = self.create({
                'conversation_id': conversation_id,
                'content': user_message,
                'is_user_message': True,
            })

            # Prepare conversation history
            conversation = self.env['ai.conversation'].browse(conversation_id)
            messages = self._prepare_conversation_history(conversation)
            messages.append({'role': 'user', 'content': user_message})

            # Send to AI API using YOUR API key
            start_time = time.time()
            ai_response = self._call_ai_api(config, messages)
            response_time = time.time() - start_time
            
            # Calculate actual costs
            tokens_used = ai_response.get('tokens_used', estimated_tokens)
            actual_credit_cost = config.calculate_credit_cost(tokens_used)
            actual_cost_usd = (tokens_used / 1000) * config.cost_per_1k_tokens
            revenue_usd = actual_credit_cost / config.credit_rate

            # Charge the user
            user_credit.consume_credits(
                actual_credit_cost, 
                user_msg.id,
                f'AI message - {tokens_used} tokens'
            )

            # Record your business metrics
            config.record_usage(tokens_used, actual_credit_cost)

            # Create AI response
            ai_msg = self.create({
                'conversation_id': conversation_id,
                'content': ai_response.get('content', 'No response received'),
                'is_user_message': False,
                'tokens_used': tokens_used,
                'response_time': response_time,
                'credit_cost': actual_credit_cost,
                'actual_cost_usd': actual_cost_usd,
                'revenue_usd': revenue_usd,
                'markup_applied': config.markup_percentage,
            })

            # Update conversation title if it's the first exchange
            if conversation.message_count <= 2 and conversation.title.startswith('New Conversation'):
                title = user_message[:50] + '...' if len(user_message) > 50 else user_message
                conversation.title = title

            return {
                'user_message': user_msg.read()[0],
                'ai_message': ai_msg.read()[0],
                'credits_used': actual_credit_cost,
                'remaining_credits': user_credit.remaining_credits,
                'tokens_used': tokens_used,
                'cost_breakdown': {
                    'tokens': tokens_used,
                    'credits_charged': actual_credit_cost,
                    'usd_cost': actual_cost_usd,
                    'usd_revenue': revenue_usd,
                }
            }

        except Exception as e:
            _logger.error(f"Error in AI conversation: {str(e)}")
            error_msg = self.create({
                'conversation_id': conversation_id,
                'content': f"Sorry, I encountered an error: {str(e)}",
                'is_user_message': False,
                'error_message': str(e),
            })
            return {
                'user_message': user_msg.read()[0] if 'user_msg' in locals() else None,
                'ai_message': error_msg.read()[0],
                'error': True,
            }

    def _prepare_conversation_history(self, conversation):
        """Prepare conversation history for AI API"""
        messages = [{
            'role': 'system',
            'content': """You are an AI assistant specialized in helping users with Odoo ERP system. 
            You have extensive knowledge about:
            - Odoo modules and functionality
            - Business processes in ERP systems
            - Odoo development and customization
            - Best practices for using Odoo
            - Troubleshooting common issues
            - Odoo administration and configuration
            
            Please provide helpful, accurate, and practical answers about Odoo. 
            If you're not sure about something, say so rather than guessing.
            Keep your responses clear, actionable, and professional.
            Format longer responses with bullet points or numbered lists when appropriate."""
        }]
        
        # Add last 10 messages to avoid token limits
        for message in conversation.message_ids[-10:]:
            role = 'user' if message.is_user_message else 'assistant'
            messages.append({
                'role': role,
                'content': message.content
            })
        
        return messages

    def _call_ai_api(self, config, messages):
        """Call the configured AI API using admin-controlled keys"""
        if config.provider == 'openai':
            return self._call_openai_api(config, messages)
        elif config.provider == 'anthropic':
            return self._call_anthropic_api(config, messages)
        else:
            raise Exception(f"Unsupported AI provider: {config.provider}")

    def _call_openai_api(self, config, messages):
        """Call OpenAI API"""
        headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json',
        }
        
        data = {
            'model': config.model_name or 'gpt-3.5-turbo',
            'messages': messages,
            'max_tokens': config.max_tokens or 1000,
            'temperature': config.temperature or 0.7,
        }
        
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers=headers,
            json=data,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            'content': result['choices'][0]['message']['content'],
            'tokens_used': result.get('usage', {}).get('total_tokens', 0)
        }

    def _call_anthropic_api(self, config, messages):
        """Call Anthropic API"""
        headers = {
            'x-api-key': config.api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        }
        
        # Convert messages format for Anthropic
        system_message = None
        formatted_messages = []
        
        for msg in messages:
            if msg['role'] == 'system':
                system_message = msg['content']
            else:
                formatted_messages.append(msg)
        
        data = {
            'model': config.model_name or 'claude-3-sonnet-20240229',
            'max_tokens': config.max_tokens or 1000,
            'messages': formatted_messages,
        }
        
        if system_message:
            data['system'] = system_message
        
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=data,
            timeout=30
        )
        
        response.raise_for_status()
        result = response.json()
        
        return {
            'content': result['content'][0]['text'],
            'tokens_used': result.get('usage', {}).get('input_tokens', 0) + result.get('usage', {}).get('output_tokens', 0)
        }
