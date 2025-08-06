# ai_assistant/models/ai_message.py
from odoo import models, fields, api, _
from odoo.exceptions import UserError
import requests
import json
import time
import logging

_logger = logging.getLogger(__name__)

class AIMessage(models.Model):
    _name = 'ai.message'
    _description = 'AI Message'
    _order = 'create_date asc'

    conversation_id = fields.Many2one('ai.conversation', string='Conversation', required=True, ondelete='cascade')
    content = fields.Text('Content', required=True)
    is_user_message = fields.Boolean('Is User Message', default=False)
    
    # AI Response metadata
    tokens_used = fields.Integer('Tokens Used', default=0)
    response_time = fields.Float('Response Time (seconds)', default=0.0)
    credit_cost = fields.Float('Credit Cost', default=0.0)
    actual_cost_usd = fields.Float('Actual Cost (USD)', default=0.0)
    revenue_usd = fields.Float('Revenue (USD)', default=0.0)
    error_message = fields.Text('Error Message')

    @api.model
    def send_message_to_ai(self, conversation_id, message_content):
        """Send message to AI and return response"""
        try:
            # Get user credit
            user_credit = self.env['ai.user.credit'].get_or_create_user_credit()
            
            # Check if user can send message
            can_send, reason = user_credit.check_usage_limit()
            if not can_send:
                return {
                    'error': True,
                    'insufficient_credits': True,
                    'message': reason,
                }

            # Get active config
            config = self.env['ai.assistant.config'].get_active_config()
            
            # Create user message
            user_message = self.create({
                'conversation_id': conversation_id,
                'content': message_content,
                'is_user_message': True,
            })

            # Send to Chat Whisperer
            start_time = time.time()
            ai_response = self._send_to_chat_whisperer(
                message_content, 
                config.chatbot_id,
                conversation_id
            )
            response_time = time.time() - start_time

            if ai_response.get('error'):
                # Create error message
                ai_message = self.create({
                    'conversation_id': conversation_id,
                    'content': f"Error: {ai_response['message']}",
                    'is_user_message': False,
                    'error_message': ai_response['message'],
                    'response_time': response_time,
                })
                return {
                    'error': True,
                    'message': ai_response['message'],
                    'user_message': user_message.read()[0],
                    'ai_message': ai_message.read()[0],
                }

            # Estimate tokens and cost (since Chat Whisperer doesn't provide this)
            estimated_tokens = len(ai_response['content'].split()) * 1.3  # Rough estimate
            credit_cost = max(0.01, estimated_tokens / 1000 * 0.1)  # Minimum cost
            
            # Create AI response message
            ai_message = self.create({
                'conversation_id': conversation_id,
                'content': ai_response['content'],
                'is_user_message': False,
                'tokens_used': int(estimated_tokens),
                'response_time': response_time,
                'credit_cost': credit_cost,
                'actual_cost_usd': credit_cost * 0.1,  # 10% of credit cost
                'revenue_usd': credit_cost * 0.1,
            })

            # Consume credits
            user_credit.consume_credits(
                credit_cost, 
                ai_message.id, 
                f"AI response - {int(estimated_tokens)} tokens"
            )

            # Update conversation title if it's the first exchange
            conversation = self.env['ai.conversation'].browse(conversation_id)
            if conversation.message_count <= 2 and conversation.title.startswith('New Conversation'):
                # Generate title from first message
                title_words = message_content.split()[:6]
                new_title = ' '.join(title_words)
                if len(new_title) > 50:
                    new_title = new_title[:47] + '...'
                conversation.title = new_title

            return {
                'success': True,
                'user_message': user_message.read()[0],
                'ai_message': ai_message.read()[0],
                'credits_used': credit_cost,
                'remaining_credits': user_credit.remaining_credits,
            }

        except Exception as e:
            _logger.error(f"Error in send_message_to_ai: {str(e)}")
            return {
                'error': True,
                'message': 'An unexpected error occurred. Please try again.',
            }

    def _send_to_chat_whisperer(self, message, chatbot_id, conversation_id):
        """Send message to Chat Whisperer API"""
        url = "https://bot.chatwhisperer.ai/api/1.1/wf/chat"
        payload = {
            "message": message,
            "chatbotId": chatbot_id,
            "userId": str(self.env.user.id),
            "conversationId": str(conversation_id)
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            reply_text = data.get("response", {}).get("text", "")
            if not reply_text:
                return {
                    'error': True,
                    'message': 'No response received from AI service'
                }
            
            return {
                'content': reply_text,
                'error': False
            }
            
        except requests.exceptions.Timeout:
            return {
                'error': True,
                'message': 'Request timed out. Please try again.'
            }
        except requests.exceptions.RequestException as e:
            return {
                'error': True,
                'message': f'Connection error: {str(e)}'
            }
        except Exception as e:
            return {
                'error': True,
                'message': f'Unexpected error: {str(e)}'
            }
