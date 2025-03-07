// static/js/sidebar.js

// Calendar events functionality for the sidebar
class SidebarCalendar {
    constructor() {
        this.init();
    }

    init() {
        // Find elements or wait until they are available
        this.findElements();
        // Set up refresh interval
        setInterval(() => this.loadCalendarEvents(), 5 * 60 * 1000); // 5 minutes
        // Initial load
        this.loadCalendarEvents();
    }
    
    findElements() {
        this.todayContent = document.getElementById('todaycontent');
        this.upcomingContent = document.getElementById('upcomingcontent');
        this.wasteContent = document.getElementById('wastecontent');
        // If elements don't exist, try again after a short delay
        if (!this.todayContent || !this.upcomingContent) {
            console.log('Calendar content elements not found, retrying...');
            setTimeout(() => this.findElements(), 500);
            return false;
        }
        return true;
    }

    async loadCalendarEvents() {
        // Ensure we have found the elements before proceeding
        if (!this.findElements()) {
            return; // Elements not ready, exit
        }
        // Show loading spinners in today and upcoming sections
        if (this.todayContent) {
            this.todayContent.innerHTML = `
                <div class="calendar-loader">
                    <div class="loader-spinner"></div>
                </div>
            `;
        }
        
        if (this.upcomingContent) {
            this.upcomingContent.innerHTML = `
                <div class="calendar-loader">
                    <div class="loader-spinner"></div>
                </div>
            `;
        }
        try {
            // Get current date in ISO format
            const today = new Date();
            const todayStr = today.toISOString().split('T')[0];
            
            // Calculate end date (7 days from now)
            const endDate = new Date();
            endDate.setDate(today.getDate() + 7);
            const endDateStr = endDate.toISOString().split('T')[0];
            
            // Fetch calendar events from our API
            const response = await fetch(`/api/calendar/events?start_date=${todayStr}&end_date=${endDateStr}&limit=20`);
            
            if (!response.ok) {
                throw new Error(`Failed to fetch calendar events: ${response.status} ${response.statusText}`);
            }
            
            const data = await response.json();
            console.log('Calendar events:', data);
            if (data.error) {
                throw new Error(data.error);
            }
            
            this.displayEvents(data.events || []);
    } catch (error) {
        console.error('Error loading calendar events:', error);
        if (this.todayContent) {
            hideLoader(this.todayContent);
            this.todayContent.innerHTML = `<p>Unable to load calendar events: ${error.message}</p>`;
        }
        if (this.upcomingContent) {
            hideLoader(this.upcomingContent);
            this.upcomingContent.innerHTML = '<p>Unable to load upcoming events</p>';
        }
        if (this.wasteContent) {
            hideLoader(this.wasteContent);
            this.wasteContent.innerHTML = '<p>Unable to load bin days</p>';
        }
        
        // Try again after a delay if it's a 404 error (might be just starting up)
        if (error.message.includes('404')) {
            console.log('API endpoint not ready, retrying in 5 seconds...');
            setTimeout(() => this.loadCalendarEvents(), 5000);
        }
    }
}

    displayEvents(events) {
        if (!events || events.length === 0) {
            hideLoader(this.todayContent);
            hideLoader(this.upcomingContent);
            this.todayContent.innerHTML = '<p>No events scheduled</p>';
            this.upcomingContent.innerHTML = '<p>No upcoming events</p>';
            return;
        }
        
        // Separate today's events from upcoming events
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);
        
        const todayEvents = [];
        const upcomingEvents = [];
        const wasteEvents = [];
        events.forEach(event => {
            const startDate = new Date(event.start);
            const calendarId = event.calendar_id;
        if (calendarId === 'calendar.bin_cycles')
            wasteEvents.push(event)
        else if (startDate >= today && startDate < tomorrow) {
            todayEvents.push(event);
        } else if (startDate >= tomorrow) {
            upcomingEvents.push(event);
        }
        });
        
        // Display today's events
        this.displayEventList(todayEvents, this.todayContent, 'today');
        
        // Display upcoming events
        this.displayEventList(upcomingEvents, this.upcomingContent, 'upcoming');

        // Display Bin Events
        this.displayEventList(wasteEvents, this.wasteContent, 'waste');
    }

    displayEventList(events, container, type) {
        if (!events || events.length === 0) {
            container.innerHTML = `<p>No ${type === 'today' ? 'events today' : 'upcoming events'}</p>`;
            return;
        }
        hideLoader(container);
        let html = '<ul class="calendar-events">';
        
        events.forEach(event => {
            const startTime = this.formatEventTime(event.start);
            const endTime = this.formatEventTime(event.end);
            const eventDate = this.formatEventDate(event.start);
            const allDay = startTime === endTime;
            const isBin = event.calendar_id === 'calendar.bin_cycles';
            html += `
                <li class="calendar-event">
                    <div class="event-pre"></div>
                    <div class="event-content">
                    <div class="event-summary">${event.summary}</div>
                    ${isBin ? `<div class="event-time">${eventDate}</div>` : 
                    `<div class="event-time">${allDay ? 'All Day' : `${startTime} - ${endTime}`}</div>`}
                    ${type === 'upcoming' ? `<div class="event-date">${eventDate}</div>` : ''}
                    
                    </div>
                </li>
            `;
        });
        
        html += '</ul>';
        container.innerHTML = html;
    }

    formatEventTime(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    formatEventDate(dateStr) {
        const date = new Date(dateStr);
        return date.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
    }
}

// Initialize sidebar calendar when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.sidebarCalendar = new SidebarCalendar();
});