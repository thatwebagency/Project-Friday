// static/js/topbar.js

// Topbar setup
class Topbar {
    constructor() {
        this.init();
    }
    
    init() {
        // Create and display the greeting based on time of day
        this.createGreeting();
    }
    
    createGreeting() {
        // Get current hour
        const currentHour = new Date().getHours();
        
        // Determine greeting based on time
        let greeting;
        if (currentHour >= 5 && currentHour < 12) {
            greeting = "Good Morning";
        } else if (currentHour >= 12 && currentHour < 18) {
            greeting = "Good Afternoon";
        } else if (currentHour >= 18 && currentHour < 22) {
            greeting = "Good Evening";
        } else {
            greeting = "Good Night";
        }
        
        // Create h1 element with the greeting
        const h1 = document.createElement('h1');
        h1.textContent = greeting;
        h1.className = 'topbar-greeting';
        
        // Find topbar element and insert greeting
        const topbarElement = document.querySelector('.dashboard-topbar');
        if (topbarElement) {
            topbarElement.prepend(h1);
        } else {
            console.error('Topbar element not found');
        }
    }
};

// Initialize topbar when the page loads
document.addEventListener('DOMContentLoaded', () => {
    window.topbar = new Topbar();
});