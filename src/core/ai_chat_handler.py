"""AI Chat Handler for Misty Aicco Assistant.

Handles conversation with OpenAI GPT models.
"""

import logging
from typing import Optional, List, Dict
from openai import OpenAI


class AIChatHandler:
    """Handles AI conversation using OpenAI Chat API.
    
    This class handles:
    - Sending queries to OpenAI GPT models
    - Managing conversation history
    - System prompt configuration
    - Error handling and retries
    """
    
    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini", 
                 max_tokens: int = 512, temperature: float = 0.7,
                 conversation_history_length: int = 5):
        """Initialize the AI Chat Handler.
        
        Args:
            openai_api_key: OpenAI API key
            model: GPT model to use (default: "gpt-4o-mini")
            max_tokens: Maximum tokens in response (default: 512)
            temperature: Response creativity 0.0-1.0 (default: 0.7)
            conversation_history_length: Number of exchanges to keep in history (default: 5)
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.conversation_history_length = conversation_history_length
        self.logger = logging.getLogger("AIChatHandler")
        
        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=openai_api_key)
            self.logger.info(f"OpenAI client initialized (model: {model})")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
        
        # Conversation history: list of message dicts
        self.conversation_history: List[Dict[str, str]] = []
        
        # System prompt defines Misty's personality
        self.system_prompt = """You are Aicco, a helpful and friendly AI assistant inside a Misty II robot. 
You have a warm personality and enjoy helping people. Keep your responses concise and conversational, 
as they will be spoken aloud. Aim for responses under 100 words unless asked for detailed information.
You can see and recognize people through your camera, and you can move and express yourself through 
LED lights and sounds."""
        
        self.logger.info("AI Chat Handler initialized successfully")
    
    def get_response(self, user_query: str) -> Optional[str]:
        """Get AI response for user query.
        
        Args:
            user_query: The user's transcribed question or statement
        
        Returns:
            AI response text, or None if generation failed
        """
        try:
            self.logger.info(f"💬 Getting AI response for: '{user_query}'")
            
            # Build messages list with system prompt, history, and new query
            messages = self._build_messages(user_query)
            
            # Call OpenAI Chat API
            self.logger.debug(f"Calling OpenAI Chat API ({self.model})...")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            # Extract response text
            ai_response = response.choices[0].message.content.strip()
            
            if ai_response:
                self.logger.info(f"✅ AI Response: '{ai_response}'")
                
                # Add to conversation history
                self._add_to_history(user_query, ai_response)
                
                return ai_response
            else:
                self.logger.warning("Empty response from OpenAI")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting AI response: {e}", exc_info=True)
            return None
    
    def _build_messages(self, user_query: str) -> List[Dict[str, str]]:
        """Build messages list for OpenAI API.
        
        Args:
            user_query: Current user query
        
        Returns:
            List of message dictionaries
        """
        messages = []
        
        # Add system prompt
        messages.append({
            "role": "system",
            "content": self.system_prompt
        })
        
        # Add conversation history
        for exchange in self.conversation_history:
            messages.append(exchange)
        
        # Add current user query
        messages.append({
            "role": "user",
            "content": user_query
        })
        
        self.logger.debug(f"Built messages with {len(messages)} items (including system prompt)")
        return messages
    
    def _add_to_history(self, user_query: str, ai_response: str):
        """Add exchange to conversation history.
        
        Args:
            user_query: User's query
            ai_response: AI's response
        """
        # Add user message
        self.conversation_history.append({
            "role": "user",
            "content": user_query
        })
        
        # Add assistant response
        self.conversation_history.append({
            "role": "assistant",
            "content": ai_response
        })
        
        # Trim history to max length (keep last N exchanges = 2N messages)
        max_messages = self.conversation_history_length * 2
        if len(self.conversation_history) > max_messages:
            # Remove oldest messages (keep most recent)
            self.conversation_history = self.conversation_history[-max_messages:]
            self.logger.debug(f"Trimmed conversation history to {len(self.conversation_history)} messages")
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history.clear()
        self.logger.info("Conversation history cleared")
    
    def get_history_summary(self) -> str:
        """Get summary of conversation history.
        
        Returns:
            String summary of conversation
        """
        if not self.conversation_history:
            return "No conversation history"
        
        exchanges = len(self.conversation_history) // 2
        return f"{exchanges} exchange(s) in history"
    
    def set_system_prompt(self, prompt: str):
        """Update the system prompt.
        
        Args:
            prompt: New system prompt
        """
        self.system_prompt = prompt
        self.logger.info("System prompt updated")
    
    def get_response_with_retry(self, user_query: str, max_retries: int = 2) -> Optional[str]:
        """Get AI response with retry logic.
        
        Args:
            user_query: User's query
            max_retries: Maximum retry attempts (default: 2)
        
        Returns:
            AI response, or None if all attempts failed
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                self.logger.info(f"Retry attempt {attempt}/{max_retries}...")
            
            response = self.get_response(user_query)
            
            if response:
                return response
            
            if attempt < max_retries:
                self.logger.warning("AI response failed, retrying...")
        
        self.logger.error(f"AI response failed after {max_retries + 1} attempts")
        return None

