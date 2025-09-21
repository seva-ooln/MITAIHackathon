import json
import os
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MeetingContext:
    """Data class to hold meeting context information"""
    meeting_id: str
    agenda: List[str]
    previous_notes: List[str]
    participants: List[str]
    meeting_date: datetime
    meeting_topic: str


class ContextManager:
    """Manages meeting context including agenda and previous meeting notes"""

    def __init__(self, context_dir: str = "data"):
        self.context_dir = context_dir
        self._ensure_directory_exists()

    def _ensure_directory_exists(self):
        """Create context directory if it doesn't exist"""
        if not os.path.exists(self.context_dir):
            os.makedirs(self.context_dir)

    def load_meeting_context(self, meeting_id: str) -> Optional[MeetingContext]:
        """Load meeting context from JSON file"""
        context_file = os.path.join(self.context_dir, f"{meeting_id}.json")

        if not os.path.exists(context_file):
            return None

        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            return MeetingContext(
                meeting_id=data['meeting_id'],
                agenda=data['agenda'],
                previous_notes=data['previous_notes'],
                participants=data['participants'],
                meeting_date=datetime.fromisoformat(data['meeting_date']),
                meeting_topic=data['meeting_topic']
            )
        except Exception as e:
            print(f"Error loading meeting context: {e}")
            return None

    def save_meeting_context(self, context: MeetingContext):
        """Save meeting context to JSON file"""
        context_file = os.path.join(self.context_dir, f"{context.meeting_id}.json")

        try:
            data = {
                'meeting_id': context.meeting_id,
                'agenda': context.agenda,
                'previous_notes': context.previous_notes,
                'participants': context.participants,
                'meeting_date': context.meeting_date.isoformat(),
                'meeting_topic': context.meeting_topic
            }

            with open(context_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            print(f"Error saving meeting context: {e}")

    def create_context_from_notes_file(self, meeting_id: str, notes_file_path: str,
                                      meeting_topic: str = "Team Meeting",
                                      agenda: List[str] = None,
                                      participants: List[str] = None) -> MeetingContext:
        """Create meeting context dynamically from a txt file containing previous notes"""

        # Read previous notes from txt file
        previous_notes = self._read_notes_from_file(notes_file_path)

        # Use default agenda if none provided
        if agenda is None:
            agenda = [
                "Review previous action items",
                "Discuss project progress",
                "Address current challenges",
                "Plan next steps",
                "Set action items for next meeting"
            ]

        # Use default participants if none provided
        if participants is None:
            participants = ["Seva", "Sid", "Omar", "Andri"]

        context = MeetingContext(
            meeting_id=meeting_id,
            agenda=agenda,
            previous_notes=previous_notes,
            participants=participants,
            meeting_date=datetime.now(),
            meeting_topic=meeting_topic
        )

        self.save_meeting_context(context)
        return context

    def _read_notes_from_file(self, file_path: str) -> List[str]:
        """Read and parse previous meeting notes from a text file"""
        if not os.path.exists(file_path):
            print(f"Notes file not found: {file_path}")
            return ["No previous meeting notes available"]

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            if not content:
                return ["No previous meeting notes available"]

            # Split notes by lines and clean them up
            notes = []
            for line in content.split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):  # Skip empty lines and comments
                    # Remove bullet points if present
                    line = line.lstrip('•-*').strip()
                    if line:
                        notes.append(line)

            return notes if notes else ["No previous meeting notes available"]

        except Exception as e:
            print(f"Error reading notes file: {e}")
            return [f"Error reading notes file: {str(e)}"]

    def get_context_summary(self, context: MeetingContext) -> str:
        """Generate a formatted summary of the meeting context"""
        summary = f"""
Meeting Context Summary:
========================
Topic: {context.meeting_topic}
Date: {context.meeting_date.strftime('%Y-%m-%d %H:%M')}
Meeting ID: {context.meeting_id}

Participants:
{', '.join(context.participants)}

Agenda:
{chr(10).join([f"• {item}" for item in context.agenda])}

Previous Notes: {len(context.previous_notes)} items loaded and analyzed
        """.strip()

        return summary