
// Hamburger Menu Logic
const mobileMenuButton = document.getElementById('mobile-menu-button');
const mobileMenu = document.getElementById('mobile-menu');
const closeMenuButton = document.getElementById('close-menu-button');
const mobileMenuOverlay = document.getElementById('mobile-menu-overlay');
const hamburgerIcon = document.querySelector('.hamburger-icon');

function toggleMobileMenu() {
    mobileMenu.classList.toggle('-translate-x-full');
    mobileMenuOverlay.classList.toggle('hidden');
    hamburgerIcon.classList.toggle('open');
}

mobileMenuButton.addEventListener('click', toggleMobileMenu);
closeMenuButton.addEventListener('click', toggleMobileMenu);
mobileMenuOverlay.addEventListener('click', toggleMobileMenu);

// "Contact Us" button functionality
window.addEventListener('scroll', function() {
    const contactButton = document.getElementById('contact-button');
    if (window.scrollY > 200) {
        contactButton.classList.remove('invisible', 'opacity-0', 'scale-0');
        contactButton.classList.add('visible', 'opacity-100', 'scale-100');
    } else {
        contactButton.classList.remove('visible', 'opacity-100', 'scale-100');
        contactButton.classList.add('invisible', 'opacity-0', 'scale-0');
    }
});

// Preloader functionality with animated text
const preloaderMessages = [
    "Loading your next adventure...",
    "Please be patient while we get things ready.",
    "Almost there! Just a moment more.",
    "Getting the best urban stays for you."
];
let messageIndex = 0;
let preloaderInterval;

function updatePreloaderText() {
    const container = document.getElementById('preloader-text-container');
    container.innerHTML = `<span class="preloader-text">${preloaderMessages[messageIndex]}</span>`;
    messageIndex = (messageIndex + 1) % preloaderMessages.length;
}

setTimeout(() => {
    updatePreloaderText();
    preloaderInterval = setInterval(updatePreloaderText, 1000); // Change message every 3 seconds
}, 1000);

window.addEventListener('load', () => {
    clearInterval(preloaderInterval);
    const preloader = document.getElementById('preloader');
    preloader.style.opacity = '0';
    setTimeout(() => {
        preloader.style.display = 'none';
    }, 500);
});

// Intersection Observer for scroll-in animations
document.addEventListener("DOMContentLoaded", function() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('is-visible');
            } else {
                // This else block is a good practice to remove the class if the element scrolls out of view
                entry.target.classList.remove('is-visible');
            }
        });
    }, {
        threshold: 0.2
    });

    document.querySelectorAll('.fade-in-section').forEach(section => {
        observer.observe(section);
    });

    // Auto-dismiss messages after a delay
    document.querySelectorAll('#messages-container .animate-slide-in-down').forEach(messageEl => {
        setTimeout(() => {
            dismissMessage(messageEl.querySelector('button'));
        }, 10000); // Messages will be auto-dismissed after 5 seconds
    });
});

// Function to handle message dismissal with animation
function dismissMessage(button) {
    const message = button.closest('[role="alert"]');
    message.classList.remove('animate-slide-in-down');
    message.classList.add('animate-slide-out-up');
    message.addEventListener('animationend', () => {
        message.remove();
    });
}

// Newsletter Form with Loader Animation and Custom Alert
const newsletterForm = document.getElementById('newsletter-form');
const subscribeButton = document.getElementById('subscribe-button');
const subscribeIcon = document.getElementById('subscribe-icon');
const loaderSpinner = document.getElementById('loader-spinner');
const emailInput = document.getElementById('email-input');
const newsletterAlert = document.getElementById('newsletter-alert');
const alertMessage = document.getElementById('alert-message');

// Function to show the animated alert
function showAlert(message) {
    // Set the message and make the alert visible
    alertMessage.textContent = message;
    newsletterAlert.classList.remove('hidden', 'animate-slide-out-up');
    newsletterAlert.classList.add('flex', 'animate-slide-in-down');

    // Set a timer to start the fade-out animation after 3 seconds
    setTimeout(hideAlert, 3000);
}

// Function to hide the animated alert
function hideAlert() {
    // Apply slide-out animation classes
    newsletterAlert.classList.remove('animate-slide-in-down');
    newsletterAlert.classList.add('animate-slide-out-up');
}

// Listen for the end of the slide-out animation to reclaim space
// This is a crucial step to prevent a layout shift and properly hide the element
newsletterAlert.addEventListener('animationend', function(event) {
    if (event.animationName === 'slide-out-up') {
        newsletterAlert.classList.add('hidden');
    }
});

newsletterForm.addEventListener('submit', function(event) {
    event.preventDefault(); // Prevent default form submission

    const email = emailInput.value.trim();
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    if (email === '') {
        showAlert('Please fill out this form.');
        return;
    }

    if (!emailPattern.test(email)) {
        showAlert('Please enter a valid email address.');
        return;
    }

    // If a valid email is present, proceed with the submission logic
    // Disable button and show loader
    subscribeButton.disabled = true;
    subscribeIcon.classList.add('hidden');
    loaderSpinner.classList.remove('hidden');

    // Simulate form submission with a delay
    setTimeout(() => {
        // Re-enable button and hide loader
        subscribeButton.disabled = false;
        subscribeIcon.classList.remove('hidden');
        loaderSpinner.classList.add('hidden');

        // For this demo, we just clear the input field.
        // In a real application, you would make a fetch request here.
        emailInput.value = '';

    }, 2000); // Loader visible for 2 seconds
});

