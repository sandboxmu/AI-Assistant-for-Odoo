{
    'name': 'AI Assistant for Odoo',
    'version': '17.0.1.0.0',
    'category': 'Tools',
    'summary': 'AI-powered assistant to answer Odoo-related questions with subscription billing',
    'description': """
AI Assistant for Odoo with Billing
==================================
This module provides an AI-powered chat interface with integrated billing system.
Features:
- Chat interface integrated in Odoo
- Conversation history
- Context-aware responses
- User access controls
- Support for multiple AI providers
- Credit-based billing system
- Subscription management
- Usage tracking and analytics
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'depends': ['base', 'web', 'account', 'sale', 'product'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ai_provider_data.xml',
        'data/billing_data.xml',
        'views/ai_conversation_views.xml',
        'views/ai_assistant_config_views.xml',
        'views/ai_billing_views.xml',
        'views/ai_subscription_views.xml',
        'views/menu_views.xml',
        'views/ai_chat_template.xml',
        'wizard/credit_purchase_wizard_views.xml',
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
}
