from flask import Blueprint, redirect, url_for, session, request, flash, current_app
from authlib.integrations.flask_client import OAuth
from functools import wraps
import os
import binascii
auth_bp = Blueprint('auth', __name__)

oauth = OAuth()

google = oauth.register(
    name='google',
    client_id=os.environ.get('GOOGLE_CLIENT_ID', ''),
    client_secret=os.environ.get('GOOGLE_CLIENT_SECRET', ''),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    access_token_params=None,
    refresh_token_url=None,
    redirect_uri='https://six.zzam.us/auth/auth',  # 수정된 URI
    jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
    client_kwargs={'scope': 'openid profile email'}
)

ALLOWED_EMAILS = ['eastflow06@gmail.com']

@auth_bp.route('/login')
def login():
    return google.authorize_redirect(redirect_uri=url_for('auth.auth', _external=True, _scheme='https'))

@auth_bp.route('/auth')
def auth():
    try:
        token = google.authorize_access_token()
        user_info = google.get('https://www.googleapis.com/oauth2/v3/userinfo').json()

        # Debugging output
        print("User Info:", user_info)

        if 'email' not in user_info:
            print("Email not found in user info")
            flash("Authentication failed: email not found.", "error")
            return redirect(url_for('login_page'))

        if user_info['email'] not in ALLOWED_EMAILS:
            print("Unauthorized email:", user_info['email'])
        
            # Show the flash message before clearing session and logging out
            flash("Access denied: You are not authorized to access this application.", "error")
            
            # Clear the session
            session.clear()
        
            # Initiate logout from Google (if using a method like this)
            google.logout()
        
            # Redirect to the login route (replace 'login' with your login route)
            return redirect(url_for('slideshow'))  # Ensure 'login' points to your Google OAuth login page

        session['user_info'] = user_info  # 사용자 정보 세션에 저장
        print("User info saved to session:", session['user_info'])

        return redirect(url_for('index'))  # 로그인 후 메인 페이지로 리디렉션

    except Exception as e:
        print("Error during authentication:", str(e))
        session.clear()  # Clear session on error
        flash("An error occurred during authentication.", "error")
        return redirect(url_for('login_page'))
        
@auth_bp.route('/logout')
def logout():
    session.clear()
    response = redirect(url_for('login_page'))
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_info' not in session:
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function