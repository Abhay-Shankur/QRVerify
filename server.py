import json
import os
import random
import string
from functools import wraps

import qrcode
from flask import Flask, render_template, request, jsonify, session, redirect, url_for

from handlers.organization import Organization

app = Flask(__name__)
app.secret_key = 'qr_verify_3812'
# fb = RealtimeDatabaseListener()
# admin = Admin()
app_name = 'QRVerify'
# fb = FirebaseOperations(app_name=app_name)
org = Organization(app_name=app_name)
# handler = ApiHandler(fb)

# List of protected URLs
protected_urls = None
if org.is_logged_in():
    protected_urls = org.get_list(collection='ORG', field='urls', uid=session['uid'])
    print(protected_urls)
else:
    protected_urls = [
        "https://www.youtube.com",
    ]


# Function to generate dynamic QR code content
def generate_qr_code_content():
    # Include some dynamic data, e.g., timestamp or random token
    dynamic_data = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    # JSON content for the QR code
    content_dict = {
        "type": ["VerifiableCredential", "OptiSecure"],
        "token": dynamic_data,
        "next_url": getattr(app, 'next_url', ''),
    }
    content_json = json.dumps(content_dict)

    # Store the token in Firebase Database
    org.firebaseHandler.add_doc(collection_name='Tokens', doc=content_dict, doc_id=dynamic_data)

    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content_json)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    # Save the QR code image
    img_path = os.path.join("static", "dynamic_qr_code.png")
    img.save(img_path)

    # Broadcast the new QR code URL to connected clients
    with app.app_context():
        app.qr_code_img_path = img_path
        app.content = content_dict


@app.route('/check_url', methods=['POST'])
def protected_redirect():
    data = request.get_json()
    url = data.get('url', '')

    with app.app_context():
        app.next_url = url

    if 'uid' in session:
        protected_urls = org.get_list(collection='ORG', field='urls', uid=session['uid'])
    else:
        protected_urls = [
            "https://www.youtube.com",
        ]

    # Perform URL protection check
    protected = any(url.startswith(prefix) for prefix in protected_urls)

    return jsonify({'protected': protected})


@app.route('/qr_code', methods=['GET', 'POST'])
def qr_code():
    # Pass the dynamic QR code URL to the template
    generate_qr_code_content()
    qr_code_content = getattr(app, 'content', None)
    next_url = getattr(app, 'next_url', '')

    if request.method == 'POST':
        data = request.get_json()
        next_url = data.get('next_url', '')

    # Retrieve the latest token from Firebase Realtime Database
    # location = '/Tokens/' + qr_code_content['token']
    token = qr_code_content['token']

    # return render_template('qr_code.html', location=location, next_url=next_url)
    return render_template('qr_code.html', token=token, next_url=next_url)


@app.route('/check_value', methods=['GET'])
def check_value():
    # Retrieve the location from the query parameters
    token = request.args.get('token')

    result = org.firebaseHandler.get_updated_document(collection_name='Tokens', document_id=token)

    with app.app_context():
        app.next_url = result.get('next_url', '')

    result = result.get('verified', False)

    org.firebaseHandler.close_connection()

    return jsonify({'verified': result})


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'uid' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    if request.method == 'POST':
        pass
    collections = ''
    if session['uid'] is not None:
        # session_org = org.get_org()
        list_urls = org.get_list(collection='ORG', field='urls', uid=session['uid'])
        if list_urls is None:
            list_urls = list()
        list_users = org.get_list(collection='ORG', field='users', uid=session['uid'])
        if list_users is None:
            list_users = list()
        list_emails = org.get_list(collection='ORG', field='userEmail', uid=session['uid'])
        if list_emails is None:
            list_emails = list()
    # return render_template('index.html', collections=collections)
    return render_template('dashboard.html', users=list_users, urls=list_urls, emails=list_emails)


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # TODO:Store Auth uid in session.
        # Get the form data
        orgName = request.form.get('orgName')
        orgEmail = request.form.get('orgEmail')
        orgPass = request.form.get('orgPass')

        formData = {
            'orgName': orgName,
            'orgEmail': orgEmail,
            'orgPass': orgPass
        }

        uid = org.authenticate_org(details=formData)
        if uid is not None:
            session['uid'] = uid
            print("UID set in session:", uid)
            return redirect(url_for('index'))

    return render_template('login.html')


# Route to handle logout
@app.route('/logout')
def logout():
    # Clear the uid from the session
    if 'uid' in session:
        session.pop('uid', None)
    return redirect(url_for('login'))


@app.route('/issue_credentials', methods=['POST'])
def issue_credentials():
    if request.method == 'POST':
        # Get the form data
        user_id = request.form.get('userID')
        username = request.form.get('username')
        email = request.form.get('email')
        aadhar = request.form.get('aadhar')
        dob = request.form.get('dob')

        # Process the data as needed
        # For example, you can store it in a database or perform any other actions

        # For now, let's just print the data
        print(f"Issuing credentials for User ID: {user_id}")
        print(f"Username: {username}")
        print(f"Email: {email}")
        print(f"Aadhar Number: {aadhar}")
        print(f"Date of Birth: {dob}")
        creds = {
            'username': username,
            'email': email,
            'aadhar': aadhar,
            'dob': dob
        }

        # You can return a response as needed
        if org.issue_credentials(subjectTo=user_id, credentials=creds):
            print("Credentials issued Successfully!")
        else:
            print("Credentials issued failed!")
    return redirect(url_for('index'))


@app.route('/add-user', methods=['POST'])
def add_user():
    if request.method == 'POST':
        # Get the form data
        user = request.form.get('user')

        # For now, let's just print the data
        print(f"Added User ID: {user}")
        uid = session['uid']
        org.set_list(collection='ORG', field='userEmail', value=user, uid=uid)
        # You can return a response as needed
        print("User ID Added successfully!")

    return redirect(url_for('index'))


@app.route('/add-url', methods=['POST'])
def add_url():
    if request.method == 'POST':
        # Get the form data
        url = request.form.get('url')

        # For now, let's just print the data
        print(f"Adding Url: {url}")
        uid = session['uid']
        org.set_list(collection='ORG', field='urls', value=url, uid=uid)
        # You can return a response as needed
        print("Added URL successfully!")
    return redirect(url_for('index'))


@app.route('/join', methods=['GET', 'POST'])
def join():
    emails = org.get_org_mails()
    if request.method == 'POST':
        # Get the form data
        _organization = request.form.get('organization')
        _did = request.form.get('did')
        _email = request.form.get('email')
        _ip_address = request.remote_addr
        res1 = org.firebaseHandler.set_value_to_list_field(collection_name='ORG', document_id=_organization, field_name='users', new_value={_ip_address: _did})
        res2 = org.firebaseHandler.set_value_to_list_field(collection_name='ORG', document_id=_organization, field_name='userEmail', new_value=_email)
        return render_template('join.html', emails=emails, result=(res1 and res2))

    return render_template('join.html', emails=emails)


if __name__ == '__main__':
    app.run(debug=True)
