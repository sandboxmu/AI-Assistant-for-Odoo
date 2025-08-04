{
    'name': 'AI Assistant for Odoo - Helper ask anything',
    'version': '17.0.1.0.0',
    'category': 'Productivity',  # Changed from 'Tools'
    'summary': 'AI-powered assistant with built-in credit system',
    'description': """
AI Assistant for Odoo - Professional Edition
===========================================

Transform your Odoo experience with an intelligent AI assistant that understands your business needs.

🤖 **Smart AI Integration**
- Powered by advanced GPT models
- Understands Odoo terminology and processes
- Context-aware responses for better accuracy
- Real-time chat interface with conversation history

💰 **Built-in Credit System**
- Pay-per-use model with transparent pricing
- Pre-loaded with free credits to get started
- Automatic billing and usage tracking
- No setup required - works out of the box

🏢 **Enterprise Features**
- Multi-user support with individual credit tracking
- Business analytics and usage reports
- Mobile-responsive design
- Secure and GDPR compliant

🎯 **Perfect For:**
- New Odoo users learning the system
- Support teams reducing ticket volume
- Training departments onboarding staff
- Any business wanting instant Odoo expertise

Start chatting immediately after installation!
    """,
    'author': 'Chat Whisperer',
    'website': 'https://www.chatwhisperer.ai',
    'support': 'omamet@chatwhisperer.ai',
    'maintainer': 'Chat Whisperer',
    
    # App Store specific fields
    'price': 0.00,  # Free to install (revenue from credits)
    'currency': 'USD',
    'live_test_url': 'https://chatwhisperer.ai',
    'demo': [
        'demo/demo_data.xml',
    ],
    'images': [
        'static/description/banner.gif',
        'static/description/screenshot_1.png',
        'static/description/screenshot_2.png',
        'static/description/screenshot_3.png',
    ],
    
    'depends': ['base', 'web'],  # Minimal dependencies
    'external_dependencies': {
        'python': ['requests'],  # Only essential dependencies
    },
    
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/ai_provider_data.xml',
        'data/centralized_config.xml',  # Your API keys
        'views/ai_conversation_views.xml',
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
    'license': 'OPL-1',  # Odoo Proprietary License for App Store
    
    # App Store categories
    'cloc_exclude': ['./**/*'],
}
