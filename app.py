import os
import sqlite3
import uuid  # Unique ID generate karne ke liye
from flask import Flask, render_template, request, send_file, redirect, session
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

app = Flask(__name__)
app.secret_key = 'super_secret_key_change_this' # Session secure karne ke liye
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

KEY = b'MySecretKey12345' 
BLOCK_SIZE = 16

def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Database mein 'user_id' column add kiya gaya hai
conn = get_db_connection()
conn.execute('CREATE TABLE IF NOT EXISTS files (id INTEGER PRIMARY KEY, name TEXT, user_id TEXT)')
conn.commit()
conn.close()

def encrypt_file(data):
    cipher = AES.new(KEY, AES.MODE_CBC)
    return cipher.iv + cipher.encrypt(pad(data, BLOCK_SIZE))

def decrypt_file(data):
    iv = data[:BLOCK_SIZE]
    cipher = AES.new(KEY, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(data[BLOCK_SIZE:]), BLOCK_SIZE)

@app.before_request
def ensure_user_id():
    # Agar user ke paas ID nahi hai, toh nayi generate karein
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())

@app.route('/')
def index():
    user_id = session.get('user_id')
    conn = get_db_connection()
    # Sirf wahi files mangwayein jo is user ki hain
    files = conn.execute('SELECT * FROM files WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()
    return render_template('index.html', files=files)

@app.route('/process', methods=['POST'])
def process():
    if 'file' not in request.files: return redirect('/')
    file = request.files['file']
    action = request.form.get('action')
    user_id = session.get('user_id')
    
    if file.filename == '': return redirect('/')
    original_data = file.read()

    if action == 'encrypt':
        data = encrypt_file(original_data)
        path = os.path.join(UPLOAD_FOLDER, file.filename + ".enc")
        with open(path, 'wb') as f: f.write(data)
        return send_file(path, as_attachment=True)

    elif action == 'decrypt':
        try:
            data = decrypt_file(original_data)
            path = os.path.join(UPLOAD_FOLDER, file.filename.replace(".enc", ""))
            with open(path, 'wb') as f: f.write(data)
            return send_file(path, as_attachment=True)
        except: return "Error: Invalid file!"

    elif action == 'store':
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        with open(path, 'wb') as f: f.write(original_data)
        conn = get_db_connection()
        # Database mein user_id ke saath save karein
        conn.execute('INSERT INTO files (name, user_id) VALUES (?, ?)', (file.filename, user_id))
        conn.commit()
        conn.close()
        return redirect('/')

@app.route('/download/<filename>')
def download_file(filename):
    user_id = session.get('user_id')
    conn = get_db_connection()
    # Security check: Kya ye file isi user ki hai?
    file_owner = conn.execute('SELECT user_id FROM files WHERE name = ?', (filename,)).fetchone()
    conn.close()
    
    if file_owner and file_owner['user_id'] == user_id:
        return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)
    return "Permission Denied!", 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
