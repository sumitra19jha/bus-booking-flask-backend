# Server Setup 
1. Create a Virtual Env
```bash
virtualenv venv
```

2. Activate the Virtual Env
```bash
source env/bin/activate
```

3. Download Packages
```bash
pip install -r requirements.txt
```

4. Create a .env file and provide all details
```bash
MAIL_SERVER=
MAIL_PORT=
MAIL_USE_TLS=
MAIL_USERNAME=
MAIL_PASSWORD=
SQLALCHEMY_DATABASE_URI=
SECRET_KEY=
```

5. Run the server
```bash
python app.py
```