/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AIChatWidget extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.chatContainerRef = useRef("chatContainer");
        this.messageInputRef = useRef("messageInput");
        
        this.state = useState({
            conversations: [],
            currentConversation: null,
            messages: [],
            isLoading: false,
            newMessage: "",
            isTyping: false,
            userCredits: null,
            showCreditWarning: false,
            connectionStatus: 'connected',
        });

        onMounted(() => {
            this.loadConversations();
            this.loadUserCredits();
            this.checkAIService();
            
            // Load specific conversation if provided in context
            if (this.props.action?.context?.default_conversation_id) {
                this.loadConversation(this.props.action.context.default_conversation_id);
            }
        });

        onWillUnmount(() => {
            // Cleanup any pending requests
        });
    }

    async loadConversations() {
        try {
            const conversations = await this.orm.searchRead(
                "ai.conversation",
                [["user_id", "=", this.env.services.user.userId]],
                ["id", "title", "last_message_date", "message_count", "total_credits_used"],
                { order: "last_message_date desc" }
            );
            this.state.conversations = conversations;
        } catch (error) {
            console.error("Failed to load conversations:", error);
            this.notification.add("Failed to load conversations", { type: "danger" });
        }
    }

    async loadUserCredits() {
        try {
            const userCredit = await this.orm.call("ai.user.credit", "get_or_create_user_credit", []);
            this.state.userCredits = userCredit;
            
            // Show warning if credits are low
            if (userCredit.remaining_credits < 2 && !userCredit.is_subscription_active) {
                this.state.showCreditWarning = true;
            }
        } catch (error) {
            console.error("Failed to load user credits:", error);
        }
    }

    async checkAIService() {
        try {
            const config = await this.orm.call("ai.assistant.config", "get_active_config", []);
            if (config.api_status === 'error') {
                this.state.connectionStatus = 'error';
                this.notification.add("AI service is currently unavailable. Please contact your administrator.", {
                    type: "warning",
                    sticky: true
                });
            } else {
                this.state.connectionStatus = 'connected';
            }
        } catch (error) {
            this.state.connectionStatus = 'error';
            this.notification.add("AI service is not configured. Please contact your administrator.", {
                type: "danger",
                sticky: true
            });
        }
    }

    async loadConversation(conversationId) {
        try {
            this.state.isLoading = true;
            
            // Load conversation details
            const conversation = await this.orm.read("ai.conversation", [conversationId], ["id", "title"]);
            if (conversation.length === 0) {
                throw new Error("Conversation not found");
            }
            this.state.currentConversation = conversation[0];

            // Load messages
            const messages = await this.orm.searchRead(
                "ai.message",
                [["conversation_id", "=", conversationId]],
                ["id", "content", "is_user_message", "create_date", "tokens_used", "response_time", "credit_cost", "error_message"],
                { order: "create_date asc" }
            );
            this.state.messages = messages;
            
            // Scroll to bottom after a short delay
            setTimeout(() => this.scrollToBottom(), 100);
        } catch (error) {
            console.error("Failed to load conversation:", error);
            this.notification.add("Failed to load conversation", { type: "danger" });
        } finally {
            this.state.isLoading = false;
        }
    }

    async createNewConversation() {
        try {
            const conversation = await this.orm.call("ai.conversation", "create_conversation", []);
            await this.loadConversations();
            this.selectConversation(conversation.id);
            
            // Focus on input after creating conversation
            setTimeout(() => {
                if (this.messageInputRef.el) {
                    this.messageInputRef.el.focus();
                }
            }, 100);
        } catch (error) {
            console.error("Failed to create conversation:", error);
            this.notification.add("Failed to create conversation", { type: "danger" });
        }
    }

    selectConversation(conversationId) {
        this.loadConversation(conversationId);
    }

    async sendMessage() {
        if (!this.state.newMessage.trim()) return;
        
        // Check connection status
        if (this.state.connectionStatus === 'error') {
            this.notification.add("AI service is currently unavailable", { type: "danger" });
            return;
        }

        // Create conversation if none selected
        if (!this.state.currentConversation) {
            await this.createNewConversation();
            if (!this.state.currentConversation) return;
        }

        const message = this.state.newMessage.trim();
        this.state.newMessage = "";
        this.state.isTyping = true;

        // Add user message immediately for better UX
        const tempUserMessage = {
            id: 'temp-' + Date.now(),
            content: message,
            is_user_message: true,
            create_date: new Date().toISOString(),
            temp: true
        };
        this.state.messages.push(tempUserMessage);
        this.scrollToBottom();

        try {
            const result = await this.orm.call(
                "ai.message",
                "send_message_to_ai",
                [this.state.currentConversation.id, message]
            );

            // Remove temporary message
            this.state.messages = this.state.messages.filter(m => m.id !== tempUserMessage.id);

            if (result.insufficient_credits) {
                this.notification.add(result.message, { 
                    type: "warning",
                    title: "Insufficient Credits"
                });
                this.state.showCreditWarning = true;
                this.showPurchaseCreditsDialog();
                return;
            }

            // Add real messages
            if (result.user_message) {
                this.state.messages.push(result.user_message);
            }
            if (result.ai_message) {
                this.state.messages.push(result.ai_message);
            }

            // Update user credits display
            if (result.remaining_credits !== undefined) {
                this.state.userCredits.remaining_credits = result.remaining_credits;
            }

            // Refresh conversations list to update message counts
            await this.loadConversations();
            
            setTimeout(() => this.scrollToBottom(), 100);

            // Show success message with usage info
            if (result.credits_used) {
                const usageInfo = `Used ${result.credits_used.toFixed(3)} credits. ${result.remaining_credits.toFixed(2)} remaining.`;
                this.notification.add(usageInfo, { 
                    type: "info",
                    title: "Message Sent"
                });
            }

            if (result.error) {
                this.notification.add("AI response had an error", { type: "warning" });
            }

        } catch (error) {
            // Remove temporary message on error
            this.state.messages = this.state.messages.filter(m => m.id !== tempUserMessage.id);
            
            console.error("Failed to send message:", error);
            this.notification.add("Failed to send message. Please try again.", { type: "danger" });
        } finally {
            this.state.isTyping = false;
        }
    }

    scrollToBottom() {
        if (this.chatContainerRef.el) {
            this.chatContainerRef.el.scrollTop = this.chatContainerRef.el.scrollHeight;
        }
    }

    onKeyPress(event) {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            this.sendMessage();
        }
    }

    onInputChange(event) {
        this.state.newMessage = event.target.value;
        
        // Auto-resize textarea
        const textarea = event.target;
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
    }

    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffMs = now - date;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        
        if (diffDays === 0) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (diffDays === 1) {
            return 'Yesterday ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (diffDays < 7) {
            return date.toLocaleDateString([], { weekday: 'short' }) + ' ' + 
                   date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString();
        }
    }

    getMessageClass(message) {
        let baseClass = message.is_user_message ? "user-message" : "ai-message";
        if (message.temp) baseClass += " temp-message";
        if (message.error_message) baseClass += " error-message";
        return baseClass;
    }

    getConversationPreview(conversation) {
        if (conversation.message_count === 0) {
            return "No messages yet";
        }
        return `${conversation.message_count} messages`;
    }

    showPurchaseCreditsDialog() {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'My Credits',
            res_model: 'ai.user.credit',
            view_mode: 'form',
            domain: [['user_id', '=', this.env.services.user.userId]],
            target: 'current',
        });
    }

    dismissCreditWarning() {
        this.state.showCreditWarning = false;
    }

    async refreshCredits() {
        await this.loadUserCredits();
        this.state.showCreditWarning = false;
        this.notification.add("Credits refreshed", { type: "success" });
    }

    getCreditStatusClass() {
        if (!this.state.userCredits) return "text-muted";
        
        if (this.state.userCredits.is_subscription_active) return "text-success";
        
        const remaining = this.state.userCredits.remaining_credits;
        if (remaining < 1) return "text-danger";
        if (remaining < 5) return "text-warning";
        return "text-info";
    }

    getCreditStatusText() {
        if (!this.state.userCredits) return "Loading...";
        
        if (this.state.userCredits.is_subscription_active) {
            return "Unlimited (Subscription)";
        }
        
        const remaining = Math.round(this.state.userCredits.remaining_credits * 100) / 100;
        return `${remaining} Credits`;
    }

    getEstimatedMessages() {
        if (!this.state.userCredits || this.state.userCredits.is_subscription_active) {
            return "∞";
        }
        
        const remaining = this.state.userCredits.remaining_credits;
        const avgCostPerMessage = 0.1; // Rough estimate
        return Math.floor(remaining / avgCostPerMessage);
    }

    async archiveConversation(conversationId) {
        try {
            await this.orm.call("ai.conversation", "archive_conversation", [conversationId]);
            await this.loadConversations();
            
            // Clear current conversation if it was archived
            if (this.state.currentConversation?.id === conversationId) {
                this.state.currentConversation = null;
                this.state.messages = [];
            }
            
            this.notification.add("Conversation archived", { type: "success" });
        } catch (error) {
            console.error("Failed to archive conversation:", error);
            this.notification.add("Failed to archive conversation", { type: "danger" });
        }
    }

    copyMessage(content) {
        navigator.clipboard.writeText(content).then(() => {
            this.notification.add("Message copied to clipboard", { type: "success" });
        }).catch(() => {
            this.notification.add("Failed to copy message", { type: "warning" });
        });
    }

    regenerateResponse(messageId) {
        // Find the user message before this AI message
        const messageIndex = this.state.messages.findIndex(m => m.id === messageId);
        if (messageIndex > 0) {
            const userMessage = this.state.messages[messageIndex - 1];
            if (userMessage.is_user_message) {
                this.state.newMessage = userMessage.content;
                // Remove the AI response and regenerate
                this.state.messages = this.state.messages.slice(0, messageIndex);
                this.sendMessage();
            }
        }
    }
}

AIChatWidget.template = "ai_assistant.ChatWidget";

registry.category("actions").add("ai_chat_widget", AIChatWidget);

