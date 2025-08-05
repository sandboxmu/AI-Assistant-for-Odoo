import requests
from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class AIMessage(models.Model):
    _name = 'ai.message'
    _description = 'AI Message'
    _order = 'create_date asc'

    conversation_id = fields.Many2one('ai.conversation', string='Conversation', required=True, ondelete='cascade')
    content = fields.Text('Content', required=True)
    is_user_message = fields.Boolean('Is User Message', default=False)
    
    # Old role field for compatibility
    role = fields.Selection([('user', 'User'), ('assistant', 'Assistant')], compute='_compute_role')
    
    # Analytics fields
    tokens_used = fields.Integer('Tokens Used', default=0)
    response_time = fields.Float('Response Time (s)', default=0.0)
    credit_cost = fields.Float('Credit Cost', default=0.0)
    actual_cost_usd = fields.Float('Actual Cost USD', default=0.0)
    revenue_usd = fields.Float('Revenue USD', default=0.0)
    error_message = fields.Text('Error Message')

    @api.depends('is_user_message')
    def _compute_role(self):
        for record in self:
            record.role = 'user' if record.is_user_message else 'assistant'

    @api.model
    def send_message_to_ai(self, conversation_id, message_content):
        """Send message to AI and get response"""
        try:
            # Get or create user credit
            user_credit = self.env['ai.user.credit'].get_or_create_user_credit()
            
            # Check if user has sufficient credits
            can_proceed, reason = user_credit.check_usage_limit(estimated_tokens=len(message_content.split()) * 2)
            
            if not can_proceed:
                return {
                    'error': True,
                    'insufficient_credits': True,
                    'message': reason,
                    'remaining_credits': user_credit.remaining_credits
                }
            
            # Create user message
            user_message = self.create({
                'conversation_id': conversation_id,
                'content': message_content,
                'is_user_message': True,
            })
            
            # Get AI configuration
            config = self.env['ai.assistant.config'].get_active_config()
            
            # Send to ChatWhisperer
            ai_response = self._send_to_chatwhisperer(
                message=message_content,
                chatbot_id=config.chatbot_id,
                user_id=str(self.env.user.id),
                conversation_id=str(conversation_id)
            )
            
            # Calculate costs (simplified)
            tokens_used = len(message_content.split()) + len(ai_response.split())
            credit_cost = tokens_used * 0.0001  # Example rate
            
            # Create AI response message
            ai_message = self.create({
                'conversation_id': conversation_id,
                'content': ai_response,
                'is_user_message': False,
                'tokens_used': tokens_used,
                'credit_cost': credit_cost,
                'response_time': 1.0,  # Would measure actual time
            })
            
            # Consume credits
            user_credit.consume_credits(credit_cost, message_id=ai_message.id)
            
            # Update conversation title if it's the first message
            conversation = self.env['ai.conversation'].browse(conversation_id)
            if conversation.message_count <= 2:  # First exchange
                # Use first few words of user message as title
                title_words = message_content.split()[:5]
                conversation.title = ' '.join(title_words) + '...' if len(title_words) >= 5 else message_content
            
            return {
                'success': True,
                'user_message': user_message.read()[0],
                'ai_message': ai_message.read()[0],
                'credits_used': credit_cost,
                'remaining_credits': user_credit.remaining_credits,
            }
            
        except Exception as e:
            _logger.error(f"Error sending message to AI: {str(e)}")
            return {
                'error': True,
                'message': str(e)
            }

    def _send_to_chatwhisperer(self, message, chatbot_id, user_id, conversation_id):
        """Send message to ChatWhisperer API"""
        url = "https://bot.chatwhisperer.ai/api/1.1/wf/chat"
        payload = {
            "message": message,
            "chatbotId": chatbot_id,
            "userId": user_id,
            "conversationId": conversation_id
        }
        
        try:
            response = requests.post(url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            return data.get("response", {}).get("text", "I apologize, but I couldn't generate a response. Please try again.")
        except requests.exceptions.Timeout:
            return "I apologize, but the response is taking too long. Please try again."
        except requests.exceptions.RequestException as e:
            _logger.error(f"ChatWhisperer API error: {str(e)}")
            return f"I'm having trouble connecting to the AI service. Please try again later."
        except Exception as e:
            _logger.error(f"Unexpected error with ChatWhisperer: {str(e)}")
            return "An unexpected error occurred. Please contact support if this persists."
