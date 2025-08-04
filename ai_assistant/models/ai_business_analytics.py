from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class AIBusinessAnalytics(models.Model):
    _name = 'ai.business.analytics'
    _description = 'AI Business Analytics'

    @api.model
    def get_business_metrics(self, days=30):
        """Get comprehensive business performance metrics"""
        
        date_from = datetime.now() - timedelta(days=days)
        
        # Get AI messages from the period
        messages = self.env['ai.message'].search([
            ('create_date', '>=', date_from),
            ('is_user_message', '=', False),
            ('credit_cost', '>', 0)
        ])
        
        # Revenue metrics
        total_revenue = sum(msg.revenue_usd or 0 for msg in messages)
        total_cost = sum(msg.actual_cost_usd or 0 for msg in messages)
        profit = total_revenue - total_cost
        margin = (profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Usage metrics
        total_messages = len(messages)
        total_tokens = sum(msg.tokens_used or 0 for msg in messages)
        total_credits_sold = sum(msg.credit_cost or 0 for msg in messages)
        avg_tokens_per_message = total_tokens / max(total_messages, 1)
        avg_credits_per_message = total_credits_sold / max(total_messages, 1)
        
        # User metrics
        active_users = len(set(msg.conversation_id.user_id.id for msg in messages))
        conversations = len(set(msg.conversation_id.id for msg in messages))
        
        # Credit transactions in period
        credit_transactions = self.env['ai.credit.transaction'].search([
            ('create_date', '>=', date_from),
            ('transaction_type', '=', 'purchase')
        ])
        credits_purchased = sum(t.amount for t in credit_transactions)
        purchase_revenue = credits_purchased / 10.0  # Assuming 10 credits = $1
        
        return {
            'period_days': days,
            'date_from': date_from.strftime('%Y-%m-%d'),
            'date_to': datetime.now().strftime('%Y-%m-%d'),
            'revenue': {
                'total_revenue_usd': round(total_revenue, 2),
                'total_cost_usd': round(total_cost, 2),
                'profit_usd': round(profit, 2),
                'profit_margin_percent': round(margin, 1),
                'purchase_revenue_usd': round(purchase_revenue, 2),
                'avg_revenue_per_message': round(total_revenue / max(total_messages, 1), 4),
            },
            'usage': {
                'total_messages': total_messages,
                'total_tokens': total_tokens,
                'total_credits_sold': round(total_credits_sold, 2),
                'avg_tokens_per_message': round(avg_tokens_per_message, 0),
                'avg_credits_per_message': round(avg_credits_per_message, 3),
                'active_users': active_users,
                'active_conversations': conversations,
            },
            'user_metrics': {
                'revenue_per_user': round(total_revenue / max(active_users, 1), 2),
                'messages_per_user': round(total_messages / max(active_users, 1), 1),
                'credits_per_user': round(total_credits_sold / max(active_users, 1), 2),
            },
            'growth': self._calculate_growth_metrics(days),
        }

    def _calculate_growth_metrics(self, days):
        """Calculate growth metrics comparing current period to previous period"""
        
        current_end = datetime.now()
        current_start = current_end - timedelta(days=days)
        previous_start = current_start - timedelta(days=days)
        previous_end = current_start
        
        # Current period
        current_messages = self.env['ai.message'].search_count([
            ('create_date', '>=', current_start),
            ('create_date', '<=', current_end),
            ('is_user_message', '=', False),
        ])
        
        current_users = len(set(
            self.env['ai.message'].search([
                ('create_date', '>=', current_start),
                ('create_date', '<=', current_end),
                ('is_user_message', '=', False),
            ]).mapped('conversation_id.user_id.id')
        ))
        
        # Previous period
        previous_messages = self.env['ai.message'].search_count([
            ('create_date', '>=', previous_start),
            ('create_date', '<', previous_end),
            ('is_user_message', '=', False),
        ])
        
        previous_users = len(set(
            self.env['ai.message'].search([
                ('create_date', '>=', previous_start),
                ('create_date', '<', previous_end),
                ('is_user_message', '=', False),
            ]).mapped('conversation_id.user_id.id')
        ))
        
        # Calculate growth rates
        message_growth = ((current_messages - previous_messages) / max(previous_messages, 1)) * 100
        user_growth = ((current_users - previous_users) / max(previous_users, 1)) * 100
        
        return {
            'message_growth_percent': round(message_growth, 1),
            'user_growth_percent': round(user_growth, 1),
            'current_period': {
                'messages': current_messages,
                'users': current_users,
            },
            'previous_period': {
                'messages': previous_messages,
                'users': previous_users,
            }
        }

    @api.model
    def get_top_users(self, days=30, limit=10):
        """Get top users by usage"""
        
        date_from = datetime.now() - timedelta(days=days)
        
        # Get user usage data
        self.env.cr.execute("""
            SELECT 
                u.id as user_id,
                u.name as user_name,
                COUNT(m.id) as message_count,
                SUM(m.tokens_used) as total_tokens,
                SUM(m.credit_cost) as total_credits,
                SUM(m.revenue_usd) as total_revenue,
                MAX(m.create_date) as last_usage
            FROM ai_message m
            JOIN ai_conversation c ON m.conversation_id = c.id
            JOIN res_users u ON c.user_id = u.id
            WHERE m.create_date >= %s 
                AND m.is_user_message = False
            GROUP BY u.id, u.name
            ORDER BY total_revenue DESC
            LIMIT %s
        """, (date_from, limit))
        
        results = self.env.cr.dictfetchall()
        
        for result in results:
            result['total_credits'] = round(result['total_credits'] or 0, 2)
            result['total_revenue'] = round(result['total_revenue'] or 0, 2)
            result['avg_credits_per_message'] = round(
                (result['total_credits'] or 0) / max(result['message_count'], 1), 3
            )
        
        return results

    @api.model
    def get_daily_usage_chart(self, days=30):
        """Get daily usage data for charts"""
        
        date_from = datetime.now() - timedelta(days=days)
        
        self.env.cr.execute("""
            SELECT 
                DATE(m.create_date) as usage_date,
                COUNT(m.id) as message_count,
                SUM(m.tokens_used) as total_tokens,
                SUM(m.credit_cost) as total_credits,
                SUM(m.revenue_usd) as total_revenue,
                COUNT(DISTINCT c.user_id) as active_users
            FROM ai_message m
            JOIN ai_conversation c ON m.conversation_id = c.id
            WHERE m.create_date >= %s 
                AND m.is_user_message = False
            GROUP BY DATE(m.create_date)
            ORDER BY usage_date
        """, (date_from,))
        
        results = self.env.cr.dictfetchall()
        
        # Fill in missing dates with zeros
        all_dates = []
        current_date = date_from.date()
        end_date = datetime.now().date()
        
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            existing_data = next((r for r in results if r['usage_date'].strftime('%Y-%m-%d') == date_str), None)
            
            if existing_data:
                all_dates.append({
                    'date': date_str,
                    'messages': existing_data['message_count'],
                    'tokens': existing_data['total_tokens'] or 0,
                    'credits': round(existing_data['total_credits'] or 0, 2),
                    'revenue': round(existing_data['total_revenue'] or 0, 2),
                    'users': existing_data['active_users'],
                })
            else:
                all_dates.append({
                    'date': date_str,
                    'messages': 0,
                    'tokens': 0,
                    'credits': 0,
                    'revenue': 0,
                    'users': 0,
                })
            
            current_date += timedelta(days=1)
        
        return all_dates

    @api.model
    def get_provider_breakdown(self, days=30):
        """Get usage breakdown by AI provider"""
        
        date_from = datetime.now() - timedelta(days=days)
        
        self.env.cr.execute("""
            SELECT 
                ac.provider,
                ac.model_name,
                COUNT(m.id) as message_count,
                SUM(m.tokens_used) as total_tokens,
                SUM(m.actual_cost_usd) as total_cost,
                SUM(m.revenue_usd) as total_revenue,
                AVG(m.response_time) as avg_response_time
            FROM ai_message m
            JOIN ai_conversation c ON m.conversation_id = c.id
            JOIN ai_assistant_config ac ON ac.is_active = True
            WHERE m.create_date >= %s 
                AND m.is_user_message = False
                AND m.tokens_used > 0
            GROUP BY ac.provider, ac.model_name
            ORDER BY total_revenue DESC
        """, (date_from,))
        
        results = self.env.cr.dictfetchall()
        
        for result in results:
            result['total_cost'] = round(result['total_cost'] or 0, 4)
            result['total_revenue'] = round(result['total_revenue'] or 0, 4)
            result['profit'] = round((result['total_revenue'] or 0) - (result['total_cost'] or 0), 4)
            result['avg_response_time'] = round(result['avg_response_time'] or 0, 2)
            result['cost_per_1k_tokens'] = round(
                (result['total_cost'] or 0) / max(result['total_tokens'] or 1, 1) * 1000, 4
            )
        
        return results

    @api.model
    def get_conversation_analytics(self, days=30):
        """Get conversation-level analytics"""
        
        date_from = datetime.now() - timedelta(days=days)
        
        conversations = self.env['ai.conversation'].search([
            ('create_date', '>=', date_from)
        ])
        
        total_conversations = len(conversations)
        active_conversations = len(conversations.filtered(lambda c: c.message_count > 0))
        
        # Calculate conversation metrics
        message_counts = conversations.mapped('message_count')
        avg_messages_per_conversation = sum(message_counts) / max(len(message_counts), 1)
        
        # Conversation length distribution
        short_conversations = len([c for c in message_counts if c <= 5])
        medium_conversations = len([c for c in message_counts if 6 <= c <= 20])
        long_conversations = len([c for c in message_counts if c > 20])
        
        return {
            'total_conversations': total_conversations,
            'active_conversations': active_conversations,
            'avg_messages_per_conversation': round(avg_messages_per_conversation, 1),
            'conversation_distribution': {
                'short_1_5_messages': short_conversations,
                'medium_6_20_messages': medium_conversations,
                'long_20_plus_messages': long_conversations,
            },
            'engagement_rate': round((active_conversations / max(total_conversations, 1)) * 100, 1),
        }

    @api.model
    def export_business_report(self, days=30):
        """Export comprehensive business report"""
        
        metrics = self.get_business_metrics(days)
        top_users = self.get_top_users(days)
        daily_usage = self.get_daily_usage_chart(days)
        provider_breakdown = self.get_provider_breakdown(days)
        conversation_analytics = self.get_conversation_analytics(days)
        
        return {
            'report_generated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'period_days': days,
            'summary': metrics,
            'top_users': top_users,
            'daily_usage': daily_usage,
            'provider_breakdown': provider_breakdown,
            'conversation_analytics': conversation_analytics,
        }
