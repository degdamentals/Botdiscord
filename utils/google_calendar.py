"""
Google Calendar API helper functions
"""
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import config
import pytz

# Scopes required for Google Calendar API
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarManager:
    """
    Manager class for Google Calendar operations
    """

    def __init__(self):
        """
        Initialize the Google Calendar API service
        """
        self.service = None
        self._init_service()

    def _init_service(self):
        """
        Initialize the Google Calendar service with credentials
        """
        try:
            # Use service account credentials
            creds = service_account.Credentials.from_service_account_file(
                config.GOOGLE_CREDENTIALS_PATH,
                scopes=SCOPES
            )
            self.service = build('calendar', 'v3', credentials=creds)
            print("Google Calendar service initialized successfully")
        except Exception as e:
            print(f"Error initializing Google Calendar service: {e}")
            self.service = None

    def get_available_slots(
        self,
        start_date: datetime,
        end_date: datetime,
        duration_minutes: int = 60
    ) -> List[datetime]:
        """
        Get available time slots between start_date and end_date

        Args:
            start_date: Start of the search period
            end_date: End of the search period
            duration_minutes: Duration of each slot in minutes

        Returns:
            List of available datetime slots
        """
        if not self.service:
            print("Google Calendar service not initialized")
            return []

        try:
            # Get existing events
            events_result = self.service.events().list(
                calendarId=config.GOOGLE_CALENDAR_ID,
                timeMin=start_date.isoformat(),
                timeMax=end_date.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Define business hours (9h-20h)
            available_slots = []
            current_time = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
            slot_duration = timedelta(minutes=duration_minutes)

            while current_time < end_date:
                # Skip if outside business hours
                if current_time.hour < 9 or current_time.hour >= 20:
                    current_time += timedelta(days=1)
                    current_time = current_time.replace(hour=9, minute=0, second=0, microsecond=0)
                    continue

                # Check if slot is available
                slot_end = current_time + slot_duration
                is_available = True

                for event in events:
                    event_start = datetime.fromisoformat(event['start'].get('dateTime', event['start'].get('date')))
                    event_end = datetime.fromisoformat(event['end'].get('dateTime', event['end'].get('date')))

                    # Make timezone-aware if needed
                    if event_start.tzinfo is None:
                        event_start = config.TIMEZONE.localize(event_start)
                    if event_end.tzinfo is None:
                        event_end = config.TIMEZONE.localize(event_end)

                    # Check for overlap
                    if (current_time < event_end and slot_end > event_start):
                        is_available = False
                        break

                if is_available:
                    available_slots.append(current_time)

                # Move to next slot
                current_time += timedelta(minutes=30)  # Check every 30 minutes

            return available_slots

        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

    def create_booking_event(
        self,
        start_time: datetime,
        duration_minutes: int,
        booking_type: str,
        client_name: str,
        discord_id: str,
        notes: Optional[str] = None
    ) -> Optional[str]:
        """
        Create a booking event in Google Calendar

        Args:
            start_time: Start time of the booking
            duration_minutes: Duration in minutes
            booking_type: Type of booking (gratuit/payant)
            client_name: Discord name of the client
            discord_id: Discord ID of the client
            notes: Optional notes

        Returns:
            Event ID if successful, None otherwise
        """
        if not self.service:
            print("Google Calendar service not initialized")
            return None

        try:
            end_time = start_time + timedelta(minutes=duration_minutes)

            # Make timezone-aware
            if start_time.tzinfo is None:
                start_time = config.TIMEZONE.localize(start_time)
            if end_time.tzinfo is None:
                end_time = config.TIMEZONE.localize(end_time)

            type_label = "GRATUIT" if booking_type == config.BOOKING_TYPE_FREE else "PAYANT"

            event = {
                'summary': f'[{type_label}] Coaching - {client_name}',
                'description': f"""Discord ID: {discord_id}
Type: {booking_type}
Réservé le: {datetime.now(config.TIMEZONE).strftime('%d/%m/%Y à %H:%M')}
{f'Notes: {notes}' if notes else ''}""",
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(config.TIMEZONE),
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(config.TIMEZONE),
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 60},
                        {'method': 'popup', 'minutes': 1440},  # 24 hours
                    ],
                },
            }

            event_result = self.service.events().insert(
                calendarId=config.GOOGLE_CALENDAR_ID,
                body=event
            ).execute()

            print(f"Event created: {event_result.get('htmlLink')}")
            return event_result.get('id')

        except HttpError as error:
            print(f"An error occurred: {error}")
            return None

    def update_event(
        self,
        event_id: str,
        start_time: Optional[datetime] = None,
        duration_minutes: Optional[int] = None,
        notes: Optional[str] = None
    ) -> bool:
        """
        Update an existing calendar event

        Args:
            event_id: Google Calendar event ID
            start_time: New start time (optional)
            duration_minutes: New duration (optional)
            notes: Updated notes (optional)

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            return False

        try:
            event = self.service.events().get(
                calendarId=config.GOOGLE_CALENDAR_ID,
                eventId=event_id
            ).execute()

            if start_time:
                if start_time.tzinfo is None:
                    start_time = config.TIMEZONE.localize(start_time)
                event['start']['dateTime'] = start_time.isoformat()

                if duration_minutes:
                    end_time = start_time + timedelta(minutes=duration_minutes)
                    event['end']['dateTime'] = end_time.isoformat()

            if notes:
                current_description = event.get('description', '')
                event['description'] = f"{current_description}\n\nNotes: {notes}"

            updated_event = self.service.events().update(
                calendarId=config.GOOGLE_CALENDAR_ID,
                eventId=event_id,
                body=event
            ).execute()

            print(f"Event updated: {updated_event.get('htmlLink')}")
            return True

        except HttpError as error:
            print(f"An error occurred: {error}")
            return False

    def delete_event(self, event_id: str) -> bool:
        """
        Delete a calendar event

        Args:
            event_id: Google Calendar event ID

        Returns:
            True if successful, False otherwise
        """
        if not self.service:
            return False

        try:
            self.service.events().delete(
                calendarId=config.GOOGLE_CALENDAR_ID,
                eventId=event_id
            ).execute()

            print(f"Event deleted: {event_id}")
            return True

        except HttpError as error:
            print(f"An error occurred: {error}")
            return False

    def get_event(self, event_id: str) -> Optional[Dict]:
        """
        Get event details by ID

        Args:
            event_id: Google Calendar event ID

        Returns:
            Event dictionary if found, None otherwise
        """
        if not self.service:
            return None

        try:
            event = self.service.events().get(
                calendarId=config.GOOGLE_CALENDAR_ID,
                eventId=event_id
            ).execute()

            return event

        except HttpError as error:
            print(f"An error occurred: {error}")
            return None
