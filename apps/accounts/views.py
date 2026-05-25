from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout

def login_view(request):
    return render(request, 'accounts/login.html')

def logout_view(request):
    auth_logout(request)
    return redirect('accounts:login')

def cac_required(request):
    return render(request, 'accounts/cac_required.html')
