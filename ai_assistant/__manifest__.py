{
    'name': 'AI Assistant for Odoo',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'AI-powered assistant with centralized billing system',
    'description': """
AI Assistant for Odoo with Centralized Billing
==============================================
Complete AI chat system with centralized API management and credit-based billing.

Features:
- Multi-provider AI integration (OpenAI, Anthropic)
- Real-time chat interface
- Centralized API key management (admin-controlled)
- Credit-based billing system
- Usage analytics and business metrics
- Mobile-responsive design
- User conversation history
- Admin dashboard for cost/revenue tracking
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'web', 'account', 'sale', 'product'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ai_provider_data.xml',
        'views/ai_conversation_views.xml',
        'views/ai_assistant_config_views.xml',
        'views/ai_user_credit_views.xml',
        'views/menu_views.xml',
        'views/ai_chat_template.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_assistant/static/src/js/ai_chat_widget.js',
            'ai_assistant/static/src/css/ai_chat.css',
            'ai_assistant/static/src/xml/ai_chat_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'price': 0.00,
    'currency': 'USD',
}
