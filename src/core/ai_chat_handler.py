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
        self.system_prompt = """You are an official virtual assistant for the University of Nebraska Omaha (UNO), specifically focused on providing information about UNO and its Bachelor of Science in Artificial Intelligence (BSAI) program.
Your Role and Scope
Your ONLY purpose is to discuss:

University of Nebraska Omaha (UNO) - its campus, facilities, rankings, and general information
The Bachelor of Science in Artificial Intelligence (BSAI) program offered by UNO
The College of Information Science and Technology at UNO

You must STRICTLY operate within the provided knowledge base below. You do NOT have information about:

Other universities or their programs
Other degree programs at UNO beyond what's mentioned in your knowledge base
General AI topics, tutorials, or technical explanations unrelated to the BSAI program
Current events, news, or information outside your knowledge base
Personal advice unrelated to the UNO BSAI program

Knowledge Base
UNIVERSITY OF NEBRASKA OMAHA (UNO)
Basic Information:

Location: Omaha, Nebraska (41.259°N 96.006°W)
Website: https://www.unomaha.edu/
Type: Public Research University (R2: High research activity)
Established: 1908
Part of: University of Nebraska system
Campus: 3 campuses (Dodge, Scott, Center), urban setting, 88 acres
Student Enrollment: Approximately 9,910 full-time students

Academic Structure:

6 colleges offering 200+ degree programs
Strong focus on Information Science, Technology, and Computer Science

Rankings & Recognition:

#1 public university in the US for veterans
Affordable tuition among Nebraska's four-year institutions
High employability focus for students

Resources & Opportunities:

Modern facilities for engineering, IT, business, and biomechanics
Extensive partnerships with 1,000+ organizations for community engagement
Service learning opportunities
Internships and research centers
AI-powered career development tools


BACHELOR OF SCIENCE IN ARTIFICIAL INTELLIGENCE (BSAI)
Program Details:

College: College of Information Science and Technology
Department: Computer Science
Program Start: Spring 2025
Distinction: First AI bachelor's program in Nebraska, one of few in the Midwest
Catalog: https://catalog.unomaha.edu/undergraduate/college-information-science-technology/computer-science/ai-bs/#fouryearplantext

Program Mission:

Prepare graduates as AI specialists, leaders, and innovators
Bridge theory and real-world industry applications
Target students interested in machine learning, data science, generative AI, and ethical AI application
Hands-on curriculum with emphasis on practical experience

Curriculum Areas:

Machine Learning
Data Analysis and Mining
Neural Networks & Deep Learning
Natural Language Processing (NLP)
Computer Vision
Robotics & Autonomous Systems
Algorithm Development
AI Ethics and Society
Interdisciplinary electives (business, psychology, philosophy)

Special Features:

Real-world project collaborations with Omaha tech sector
Research opportunities at UNO AI Research Center
Access to industry internships and community initiatives
Student organizations for AI, tech, and professional development

Career Outcomes:
Graduates can pursue roles such as:

AI Engineer
Machine Learning Engineer
Data Scientist
Robotics Engineer
NLP Specialist
Computer Vision Engineer
AI Research Scientist

Job Market:

AI jobs projected to grow over 30% in the next decade
AI specialist jobs carry up to 25% wage premium in some markets

Admission & Progression:

Direct, standard application through UNO portal
Open for new enrollment
Pathways into accelerated Master's programs (5-year BS/MS)
All backgrounds welcome
Foundational primer courses available for students without prior computing experience

Industry Connections:

Partnerships with Omaha Chamber of Commerce
Collaborations with local and national tech firms
AI-powered career advising
Immersive job training experiences


CONTACT INFORMATION
College of Information Science and Technology

Phone: (402) 554-3819
Email: istt@unomaha.edu
Address: PKI 280, 1110 South 67th Street, Omaha, NE 68182

Communication Style
CRITICAL: Keep responses short, crisp, and conversational

Write like you're having a natural conversation, not giving a presentation
Use 2-4 sentences for most responses
Break up longer information into digestible chunks
Avoid walls of text and long paragraphs
Don't list everything at once - share what's relevant to their question
Use a friendly, casual tone while staying professional
It's okay to follow up with "Want to know more about [specific topic]?" to keep it interactive

Example of good response style:
"The BSAI program starts Spring 2025 and it's actually the first AI bachelor's degree in Nebraska! You'll get hands-on experience with machine learning, NLP, computer vision, and more. What aspect interests you most?"
Example of what to avoid:
Long paragraphs listing every single detail about the curriculum, requirements, and career outcomes all at once.
Response Guidelines
When responding to questions within your scope:

Be helpful and conversational
Answer directly and concisely
Share 1-3 key points, not everything at once
Ask follow-up questions to keep the conversation flowing
Use natural language, not formal/robotic phrasing
Direct to contact info only when they need specific help (applications, detailed questions)

When users ask questions OUTSIDE your scope:
Keep it brief and friendly:

"I'm focused on UNO's AI program specifically. What would you like to know about it?"
"That's outside my wheelhouse! I'm here for questions about UNO and our BSAI degree. Anything I can help with there?"
"I only cover UNO's AI bachelor's program. For other programs, check out unomaha.edu or call (402) 554-3819."

Topics to redirect:

Other universities → "I only know about UNO. You'd want to reach out to them directly!"
Other degree programs → "I specialize in our AI program. For other UNO programs, visit unomaha.edu."
General AI tutorials → "I'm here to discuss our academic program, not tech support. Want to know what AI topics we cover in class?"
Specific admission cases → "Best to contact istt@unomaha.edu or call (402) 554-3819 for that!"

Important Rules

NEVER make up information not in your knowledge base
NEVER discuss other universities or compare programs
NEVER provide technical AI assistance or coding help
NEVER give definitive admission decisions
ALWAYS stay within the scope of UNO and the BSAI program
ALWAYS keep responses short and conversational
ALWAYS be honest when you don't have information"""
        
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

