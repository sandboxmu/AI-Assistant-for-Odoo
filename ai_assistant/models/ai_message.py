# ai_message.py

import requests
from odoo import models, fields, api

class AIMessage(models.Model):
    _name = 'ai.message'
    _description = 'AI Message'

    conversation_id = fields.Many2one('ai.conversation', string='Conversation', required=True)
    role = fields.Selection([('user', 'User'), ('assistant', 'Assistant')], required=True)
    content = fields.Text('Content', required=True)

    @api.model
    def create_from_input(self, conversation, user_input):
        config = self.env['ai.assistant.config'].sudo().get_active_config()

        self.create({
            'conversation_id': conversation.id,
            'role': 'user',
            'content': user_input,
        })

        reply = self.send_to_chatwhisperer(
            message=user_input,
            chatbot_id=config.chatwhisperer_bot_id,
            user_id=str(self.env.user.id),
            conversation_id=str(conversation.id)
        )

        return self.create({
            'conversation_id': conversation.id,
            'role': 'assistant',
            'content': reply,
        })

    def send_to_chatwhisperer(self, message, chatbot_id, user_id, conversation_id):
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
            return data.get("response", {}).get("text", "(No reply received)")
        except Exception as e:
            return f"(Error contacting ChatWhisperer: {str(e)})"

