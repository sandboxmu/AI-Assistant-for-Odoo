from odoo import http
from odoo.http import request
import json
import logging
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)

class AIChatController(http.Controller):
    
    @http.route('/ai_assistant/chat/send_message', type='json', auth='user', methods=['POST'], csrf=False)
    def send_message(self, conversation_id, message, **kwargs):
        """API endpoint for sending messages to AI"""
        try:
            # Rate limiting check
            if not self._check_rate_limit():
                return {
                    'error': True,
                    'message': 'Rate limit exceeded. Please wait before sending another message.',
                    'rate_limited': True
                }

            # Validate inputs
            if not conversation_id or not message or not message.strip():
                return {
                    'error': True,
                    'message': 'Invalid conversation ID or empty message'
                }

            # Ensure user has access to the conversation
            conversation = request.env['ai.conversation'].browse(conversation_id)
            if not conversation.exists() or conversation.user_id.id != request.env.user.id:
                return {
                    'error': True,
                    'message': 'Access denied to conversation'
                }
            
            # Send message to AI
            result = request.env['ai.message'].send_message_to_ai(conversation_id, message.strip())
            
            # Log the interaction
            self._log_api_usage('send_message', {
                'conversation_id': conversation_id,
                'message_length': len(message),
                'success': not result.get('error', False)
            })
            
            return result
            
        except Exception as e:
            _logger.error(f"Error in chat controller send_message: {str(e)}")
            return {
                'error': True,
                'message': 'An unexpected error occurred. Please try again.'
            }

    @http.route('/ai_assistant/conversations', type='json', auth='user', methods=['GET'], csrf=False)
    def get_conversations(self, limit=50, offset=0, **kwargs):
        """Get user's conversations with pagination"""
        try:
            # Validate parameters
            limit = min(int(limit), 100)  # Max 100 conversations per request
            offset = max(int(offset), 0)
            
            domain = [('user_id', '=', request.env.user.id)]
            
            conversations = request.env['ai.conversation'].search(
                domain,
                limit=limit,
                offset=offset,
                order='last_message_date desc, create_date desc'
            )
            
            total_count = request.env['ai.conversation'].search_count(domain)
            
            result = {
                'conversations': conversations.read([
                    'id', 'title', 'last_message_date', 'message_count', 
                    'total_credits_used', 'is_active', 'create_date'
                ]),
                'total_count': total_count,
                'has_more': (offset + limit) < total_count
            }
            
            self._log_api_usage('get_conversations', {
                'count': len(result['conversations']),
                'limit': limit,
                'offset': offset
            })
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting conversations: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to load conversations'
            }

    @http.route('/ai_assistant/conversation/<int:conversation_id>/messages', 
                type='json', auth='user', methods=['GET'], csrf=False)
    def get_conversation_messages(self, conversation_id, limit=50, offset=0, **kwargs):
        """Get messages for a specific conversation with pagination"""
        try:
            # Validate parameters
            limit = min(int(limit), 100)  # Max 100 messages per request
            offset = max(int(offset), 0)
            
            # Verify access to conversation
            conversation = request.env['ai.conversation'].browse(conversation_id)
            if not conversation.exists() or conversation.user_id.id != request.env.user.id:
                return {
                    'error': True,
                    'message': 'Access denied to conversation'
                }
            
            # Get messages
            domain = [('conversation_id', '=', conversation_id)]
            messages = request.env['ai.message'].search(
                domain,
                limit=limit,
                offset=offset,
                order='create_date asc'
            )
            
            total_count = request.env['ai.message'].search_count(domain)
            
            result = {
                'conversation': conversation.read(['id', 'title', 'is_active'])[0],
                'messages': messages.read([
                    'id', 'content', 'is_user_message', 'create_date', 
                    'tokens_used', 'response_time', 'credit_cost', 'error_message'
                ]),
                'total_count': total_count,
                'has_more': (offset + limit) < total_count
            }
            
            self._log_api_usage('get_messages', {
                'conversation_id': conversation_id,
                'message_count': len(result['messages'])
            })
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting messages: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to load messages'
            }

    @http.route('/ai_assistant/conversation/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_conversation(self, title=None, **kwargs):
        """Create a new conversation"""
        try:
            # Check if user has reached conversation limit
            user_conversation_count = request.env['ai.conversation'].search_count([
                ('user_id', '=', request.env.user.id),
                ('is_active', '=', True)
            ])
            
            max_conversations = int(request.env['ir.config_parameter'].sudo().get_param(
                'ai_assistant.max_conversations_per_user', '50'
            ))
            
            if user_conversation_count >= max_conversations:
                return {
                    'error': True,
                    'message': f'Maximum number of active conversations ({max_conversations}) reached. Please archive some conversations first.'
                }
            
            # Create conversation
            conversation = request.env['ai.conversation'].create_conversation(title)
            
            result = {
                'conversation': conversation.read(['id', 'title', 'create_date'])[0]
            }
            
            self._log_api_usage('create_conversation', {
                'conversation_id': conversation.id,
                'title': title or 'Auto-generated'
            })
            
            return result
            
        except Exception as e:
            _logger.error(f"Error creating conversation: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to create conversation'
            }

    @http.route('/ai_assistant/conversation/<int:conversation_id>/archive', 
                type='json', auth='user', methods=['POST'], csrf=False)
    def archive_conversation(self, conversation_id, **kwargs):
        """Archive a conversation"""
        try:
            # Verify access to conversation
            conversation = request.env['ai.conversation'].browse(conversation_id)
            if not conversation.exists() or conversation.user_id.id != request.env.user.id:
                return {
                    'error': True,
                    'message': 'Access denied to conversation'
                }
            
            # Archive conversation
            conversation.archive_conversation()
            
            self._log_api_usage('archive_conversation', {
                'conversation_id': conversation_id
            })
            
            return {'success': True}
            
        except Exception as e:
            _logger.error(f"Error archiving conversation: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to archive conversation'
            }

    @http.route('/ai_assistant/user/credits', type='json', auth='user', methods=['GET'], csrf=False)
    def get_user_credits(self, **kwargs):
        """Get user's credit information"""
        try:
            user_credit = request.env['ai.user.credit'].get_or_create_user_credit()
            
            result = {
                'credits': user_credit.read([
                    'total_credits', 'used_credits', 'remaining_credits',
                    'is_subscription_active', 'total_messages_sent',
                    'last_usage_date', 'subscription_end'
                ])[0],
                'usage_summary': user_credit.get_usage_summary(30)
            }
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting user credits: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to load credit information'
            }

    @http.route('/ai_assistant/user/usage_history', 
                type='json', auth='user', methods=['GET'], csrf=False)
    def get_usage_history(self, days=30, limit=50, offset=0, **kwargs):
        """Get user's usage history"""
        try:
            days = min(int(days), 365)  # Max 1 year
            limit = min(int(limit), 100)
            offset = max(int(offset), 0)
            
            date_from = datetime.now() - timedelta(days=days)
            
            domain = [
                ('user_id', '=', request.env.user.id),
                ('create_date', '>=', date_from)
            ]
            
            transactions = request.env['ai.credit.transaction'].search(
                domain,
                limit=limit,
                offset=offset,
                order='create_date desc'
            )
            
            total_count = request.env['ai.credit.transaction'].search_count(domain)
            
            result = {
                'transactions': transactions.read([
                    'id', 'create_date', 'transaction_type', 'amount',
                    'description', 'balance_after'
                ]),
                'total_count': total_count,
                'has_more': (offset + limit) < total_count
            }
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting usage history: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to load usage history'
            }

    @http.route('/ai_assistant/system/status', type='json', auth='user', methods=['GET'], csrf=False)
    def get_system_status(self, **kwargs):
        """Get AI system status"""
        try:
            # Get active configuration
            try:
                config = request.env['ai.assistant.config'].get_active_config()
                system_status = {
                    'status': 'active',
                    'provider': config.provider,
                    'model': config.model_name,
                    'api_status': config.api_status,
                    'last_api_call': config.last_api_call.isoformat() if config.last_api_call else None
                }
            except Exception:
                system_status = {
                    'status': 'unavailable',
                    'message': 'AI service is not configured'
                }
            
            # Get user's rate limit status
            rate_limit_info = self._get_rate_limit_info()
            
            result = {
                'system': system_status,
                'rate_limit': rate_limit_info,
                'timestamp': datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            _logger.error(f"Error getting system status: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to get system status'
            }

    @http.route('/ai_assistant/feedback', type='json', auth='user', methods=['POST'], csrf=False)
    def submit_feedback(self, message_id=None, rating=None, feedback=None, **kwargs):
        """Submit feedback for AI responses"""
        try:
            if not any([message_id, rating, feedback]):
                return {
                    'error': True,
                    'message': 'No feedback data provided'
                }
            
            # Verify message access if message_id provided
            if message_id:
                message = request.env['ai.message'].browse(message_id)
                if not message.exists() or message.conversation_id.user_id.id != request.env.user.id:
                    return {
                        'error': True,
                        'message': 'Access denied to message'
                    }
            
            # Create feedback record (you could create a feedback model)
            feedback_data = {
                'user_id': request.env.user.id,
                'message_id': message_id,
                'rating': rating,
                'feedback': feedback,
                'timestamp': datetime.now(),
                'ip_address': request.httprequest.environ.get('REMOTE_ADDR')
            }
            
            # Log feedback for analysis
            _logger.info(f"User feedback received: {json.dumps(feedback_data, default=str)}")
            
            self._log_api_usage('submit_feedback', feedback_data)
            
            return {'success': True, 'message': 'Thank you for your feedback!'}
            
        except Exception as e:
            _logger.error(f"Error submitting feedback: {str(e)}")
            return {
                'error': True,
                'message': 'Failed to submit feedback'
            }

    def _check_rate_limit(self):
        """Check if user has exceeded rate limits"""
        try:
            user_id = request.env.user.id
            rate_limit = int(request.env['ir.config_parameter'].sudo().get_param(
                'ai_assistant.rate_limit_per_minute', '10'
            ))
            
            # Use session to track rate limiting
            session = request.session
            current_time = datetime.now()
            
            # Initialize rate limit data if not exists
            if 'ai_rate_limit' not in session:
                session['ai_rate_limit'] = {
                    'requests': [],
                    'user_id': user_id
                }
            
            rate_data = session['ai_rate_limit']
            
            # Clean old requests (older than 1 minute)
            cutoff_time = current_time - timedelta(minutes=1)
            rate_data['requests'] = [
                req_time for req_time in rate_data['requests'] 
                if datetime.fromisoformat(req_time) > cutoff_time
            ]
            
            # Check if rate limit exceeded
            if len(rate_data['requests']) >= rate_limit:
                return False
            
            # Add current request
            rate_data['requests'].append(current_time.isoformat())
            session['ai_rate_limit'] = rate_data
            
            return True
            
        except Exception as e:
            _logger.error(f"Error checking rate limit: {str(e)}")
            return True  # Allow request if rate limiting fails

    def _get_rate_limit_info(self):
        """Get current rate limit information for user"""
        try:
            session = request.session
            rate_limit = int(request.env['ir.config_parameter'].sudo().get_param(
                'ai_assistant.rate_limit_per_minute', '10'
            ))
            
            if 'ai_rate_limit' not in session:
                return {
                    'limit': rate_limit,
                    'used': 0,
                    'remaining': rate_limit,
                    'reset_time': None
                }
            
            rate_data = session['ai_rate_limit']
            current_time = datetime.now()
            cutoff_time = current_time - timedelta(minutes=1)
            
            # Count recent requests
            recent_requests = [
                req_time for req_time in rate_data['requests'] 
                if datetime.fromisoformat(req_time) > cutoff_time
            ]
            
            used = len(recent_requests)
            remaining = max(0, rate_limit - used)
            
            # Calculate reset time (when oldest request expires)
            reset_time = None
            if recent_requests:
                oldest_request = min(datetime.fromisoformat(req) for req in recent_requests)
                reset_time = (oldest_request + timedelta(minutes=1)).isoformat()
            
            return {
                'limit': rate_limit,
                'used': used,
                'remaining': remaining,
                'reset_time': reset_time
            }
            
        except Exception as e:
            _logger.error(f"Error getting rate limit info: {str(e)}")
            return {
                'limit': 10,
                'used': 0,
                'remaining': 10,
                'reset_time': None
            }

    def _log_api_usage(self, endpoint, data):
        """Log API usage for analytics"""
        try:
            log_data = {
                'timestamp': datetime.now().isoformat(),
                'user_id': request.env.user.id,
                'endpoint': endpoint,
                'data': data,
                'ip_address': request.httprequest.environ.get('REMOTE_ADDR'),
                'user_agent': request.httprequest.environ.get('HTTP_USER_AGENT', '')[:200]
            }
            
            # Log for analytics (you could store this in a separate model)
            _logger.info(f"API Usage: {json.dumps(log_data, default=str)}")
            
        except Exception as e:
            _logger.error(f"Error logging API usage: {str(e)}")

    @http.route('/ai_assistant/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health_check(self, **kwargs):
        """Health check endpoint for monitoring"""
        try:
            # Basic health checks
            health_status = {
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'database': 'connected',
                'ai_service': 'unknown'
            }
            
            # Check AI service if possible
            try:
                config = request.env['ai.assistant.config'].sudo().get_active_config()
                health_status['ai_service'] = config.api_status
            except Exception:
                health_status['ai_service'] = 'not_configured'
            
            return json.dumps(health_status)
            
        except Exception as e:
            error_response = {
                'status': 'unhealthy',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            return json.dumps(error_response)
