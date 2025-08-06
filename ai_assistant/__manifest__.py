{
    'name': 'AI Assistant for Odoo - Chat Whisperer Integration',
    'version': '17.0.1.0.0',
    'category': 'Productivity',
    'summary': 'ChatWhisperer-powered assistant for Odoo with conversation tracking and configuration management.',
    'description': """
AI Assistant for Odoo - Chat Whisperer Edition
=============================================

Seamlessly integrate a powerful AI chatbot (powered by ChatWhisperer) directly into your Odoo system.

Features:
---------
🤖 Smart Chat Assistant
- Custom chatbot connection via ChatWhisperer API
- Personalized replies and conversation context

🛠 Admin Config Panel
- Activate/deactivate bot configurations
- Enforce single active config

🧠 Message Memory
- Conversation and message model support
- Stores user and assistant interactions

🚀 Fast Setup
- Lightweight and self-contained
- Demo data for testing
""",
    'author': 'Chat Whisperer',
    'website': 'https://bot.chatwhisperer.ai/chatbot/1754325699224x235880637442555900i',
    'support': 'omamet@chatwhisperer.ai',
    'maintainer': 'Chat Whisperer',

    'license': 'OPL-1',
    'price': 0.00,
    'currency': 'USD',
    'application': True,
    'installable': True,
    'auto_install': False,

    'depends': ['base', 'web'],
    'external_dependencies': {
        'python': ['requests'],
    },

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/ai_assistant_config_views.xml',
    ],

    'demo': [
        'data/ai_assistant_demo.xml',
    ],

    'assets': {
        'web.assets_backend': [
            'ai_assistant/static/src/js/ai_chat_widget.js',
            'ai_assistant/static/src/css/ai_chat.css',
            'ai_assistant/static/src/xml/ai_chat_templates.xml',
        ],
    },

    'images': [
        'static/description/banner.gif',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
    ],
}

