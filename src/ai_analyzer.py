import os
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from context_manager import MeetingContext

load_dotenv()


class AIAnalyzer:
    """Handles OpenAI text analysis for meeting context understanding"""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

    def analyze_meeting_context(self, context: MeetingContext) -> Dict[str, str]:
        """Analyze meeting context and generate insights from previous notes"""

        prompt = f"""
        You are a meeting facilitator AI. Analyze the previous meeting notes and current agenda to provide facilitator insights.

        Meeting Topic: {context.meeting_topic}
        Previous Meeting Notes:
        {chr(10).join(context.previous_notes)}

        Current Agenda:
        {chr(10).join(context.agenda)}

        Based on the previous notes, provide brief insights on:
        1. Key follow-ups needed from previous meeting
        2. Potential discussion points for today
        3. Action items to track
        4. Questions to ask the team

        Keep response concise and actionable for a meeting facilitator.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert meeting facilitator focused on extracting actionable insights from previous meeting notes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.6
            )

            return {
                "analysis": response.choices[0].message.content,
                "status": "success"
            }

        except Exception as e:
            return {
                "analysis": f"Context analysis available offline only.",
                "status": "error"
            }

    def generate_meeting_greeting(self, context: MeetingContext) -> str:
        """Generate a personalized meeting greeting based on context"""

        # Include context from previous meeting notes
        previous_context = "\n".join(context.previous_notes[:3])  # Use first 3 notes for context

        prompt = f"""
        You are Alex, a meeting facilitator bot. Generate a brief, contextual greeting for this meeting.

        Meeting Details:
        - Topic: {context.meeting_topic}
        - Participants: {', '.join(context.participants)}

        Previous Meeting Context:
        {previous_context}

        Current Agenda:
        {chr(10).join([f"• {item}" for item in context.agenda[:3]])}

        Generate a greeting that:
        1. Welcomes everyone to the specific meeting topic
        2. Briefly acknowledges context from previous meetings
        3. Sets expectation for today's agenda
        4. Is warm but professional (2-3 sentences max)

        Don't mention "AssemblyAI" or technical terms - focus on the actual meeting content.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are Alex, a friendly meeting facilitator who understands meeting context and helps teams stay focused on their goals."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=120,
                temperature=0.7
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            # Contextual fallback based on actual meeting data
            return f"Hello everyone! Welcome to our {context.meeting_topic}. Based on our previous discussions, let's continue moving forward with today's agenda."

    def analyze_ongoing_discussion(self, transcript: str, context: MeetingContext) -> Dict[str, any]:
        """Analyze ongoing meeting discussion and provide real-time insights"""
        prompt = f"""
        You are facilitating a meeting. Analyze this recent discussion transcript and provide:
        1. Key points discussed
        2. Action items mentioned
        3. Questions that need answers
        4. Suggestions for keeping the meeting on track

        Meeting Topic: {context.meeting_topic}
        Recent Transcript:
        {transcript}

        Provide brief, actionable insights.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an active meeting facilitator providing real-time guidance."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.5
            )

            return {
                "insights": response.choices[0].message.content,
                "status": "success"
            }

        except Exception as e:
            return {
                "insights": f"Error analyzing discussion: {str(e)}",
                "status": "error"
            }

    def _format_context_for_analysis(self, context: MeetingContext) -> str:
        """Format meeting context for AI analysis"""
        return f"""
Topic: {context.meeting_topic}
Date: {context.meeting_date.strftime('%Y-%m-%d')}
Participants: {', '.join(context.participants)}

Agenda Items:
{chr(10).join([f"- {item}" for item in context.agenda])}

Previous Meeting Notes:
{chr(10).join([f"- {note}" for note in context.previous_notes])}
        """.strip()

    def suggest_next_steps(self, context: MeetingContext, discussion_summary: str) -> str:
        """Suggest next steps based on meeting context and discussion"""
        prompt = f"""
        Based on the meeting context and discussion summary, suggest 3-5 concrete next steps or action items.

        Meeting Topic: {context.meeting_topic}
        Discussion Summary: {discussion_summary}

        Provide clear, actionable next steps with suggested owners if possible.
        """

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a meeting facilitator focused on driving actionable outcomes."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.6
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            return "Unable to generate next steps suggestions at this time."