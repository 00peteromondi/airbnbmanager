from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import HostRegistrationForm, ListingForm
from .models import Listing
from django.contrib.auth.forms import AuthenticationForm
from django.http import HttpResponseForbidden
from django.urls import reverse


def register_host(request):
    if request.method == 'POST':
        form = HostRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome to Aurban.")
            return redirect('hosts:dashboard')
        messages.error(request, "Registration failed. Invalid information.")
    else:
        form = HostRegistrationForm()
    return render(request, 'hosts/register.html', {'form': form})



def login_host(request):
    """
    Handles the host login process.

    This function processes both GET and POST requests.
    - On GET, it displays an empty login form.
    - On POST, it attempts to authenticate and log in the user.
    """
    if request.method == 'POST':
        # Create an instance of the AuthenticationForm with the request data.
        # This form handles validation of the username and password fields.
        form = AuthenticationForm(request, data=request.POST)
        
        # Check if the form data is valid.
        if form.is_valid():
            # The form is valid, now use the cleaned data to authenticate the user.
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            # The authenticate function checks the credentials against the database.
            # It returns a User object on success, and None on failure.
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                # The user was found and authenticated.
                # The login function creates the user's session.
                login(request, user)
                
                # Send a success message to the user.
                messages.success(request, f"Welcome back, {username}!")
                
                # Redirect the user to the dashboard.
                return redirect('hosts:dashboard')
            else:
                # The user was not authenticated.
                # This could be due to an incorrect username or password.
                messages.error(request, "Invalid username or password.")
        else:
            # The form itself was invalid (e.g., fields were left empty).
            # The AuthenticationForm will automatically add errors to itself.
            messages.error(request, "Invalid username or password. Please check your details.")
    else:
        # For a GET request, create an empty form to display.
        form = AuthenticationForm()
        
    # Render the login page, passing the form and any messages.
    return render(request, 'hosts/login.html', {'form': form})

# View for host logout
def logout_host(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('hosts:login')


@login_required
def dashboard(request):
    """
    Displays the host dashboard with a list of all their properties.
    """
    listings = Listing.objects.filter(host=request.user).order_by('-created_at')
    context = {
        'listings': listings,
    }
    return render(request, 'hosts/dashboard.html', context)

@login_required
def add_listing(request):
    """
    Handles creating a new listing.
    """
    if request.method == 'POST':
        form = ListingForm(request.POST)
        if form.is_valid():
            listing = form.save(commit=False)
            listing.host = request.user
            listing.save()
            messages.success(request, 'New listing added successfully!')
            return redirect('hosts:dashboard')
    else:
        form = ListingForm()
    
    context = {
        'form': form,
    }
    return render(request, 'hosts/add_listing.html', context)


@login_required
def edit_listing(request, listing_id):
    """
    Handles the logic for the edit listing page.
    This view retrieves an existing listing and allows a user to update it.
    """
    
    # Use get_object_or_404 to fetch the listing.
    # This will return a 404 page if the ID doesn't exist.
    listing = get_object_or_404(Listing, id=listing_id)
    
    # Check if the form has been submitted
    if request.method == 'POST':
        # Create a form instance and populate it with data from the request
        # and the existing listing instance.
        form = ListingForm(request.POST, instance=listing)
        
        # Validate the form
        if form.is_valid():
            # Save the updated listing to the database
            form.save()
            
            # Redirect to the listing's detail page or another success page
            # after a successful update.
            return redirect(reverse('hosts:view_listing', args=[listing.id]))
    else:
        # If the request is a GET, create a new form instance
        # pre-populated with the data from the listing.
        form = ListingForm(instance=listing)
    
    # Pass both the form and the listing object to the template context.
    # This is the crucial step that was likely missing.
    context = {
        'form': form,
        'listing': listing,
    }
    
    return render(request, 'hosts/edit_listing.html', context)

@login_required
def view_listing(request, listing_id):
    """
    Displays the details of a specific listing.
    """
    listing = get_object_or_404(Listing, id=listing_id, host=request.user)
    context = {
        'listing': listing,
    }
    return render(request, 'hosts/view_listing.html', context)

@login_required
def delete_listing(request, pk):
    """
    Handles deleting a listing.
    """
    listing = get_object_or_404(Listing, pk=pk)
    
    # Security check: ensure the current user is the owner of the listing
    if listing.host != request.user:
        return HttpResponseForbidden()

    if request.method == 'POST':
        listing.delete()
        messages.success(request, 'Listing deleted successfully!')
        return redirect('hosts:dashboard')
    
    context = {
        'listing': listing,
    }
    return render(request, 'hosts/delete_listing.html', context)

# View to list all listings for the current hosts
@login_required
def my_listings(request):
    listings = request.user.listings.all()
    context = {'listings': listings}
    return render(request, 'hosts/my_listings.html', context)



