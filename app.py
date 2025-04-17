import os
import fitz  # PyMuPDF for PDF handling
from openai import OpenAI
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif"}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///chat_history.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

class Chat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    messages = db.relationship("Message", backref="chat", lazy=True)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey("chat.id"), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.form.get("message")
    chat_id = request.form.get("chat_id")
    file = request.files.get("file")
    file_content = ""
    messages = []
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)
        image_url = f"http://127.0.0.1:5000/uploads/{filename}"
        
        # Modify message format to send image
        # messages = [{"role": "user", "content": [{"type": "image_url", "image_url": image_url}]}]
        messages = [{"role": "user", "content": file}]
    
    if user_message:
        messages.append({"role": "user", "content": user_message})
    else:
        messages = [{"role": "user", "content": user_message}]
        
    
    if not user_message and not file_content:
        return jsonify({"error": "No message or file provided"}), 400
    
    if not chat_id:
        chat_count = Chat.query.count() + 1
        new_chat = Chat(title=f"Chat {chat_count}")
        db.session.add(new_chat)
        db.session.commit()
        chat_id = new_chat.id
    
    user_text = f"{file_content}\n {user_message}" if file_content else user_message
    user_msg = Message(chat_id=chat_id, role="user", content=user_text)
    db.session.add(user_msg)
    db.session.commit()
    
    messages = Message.query.filter_by(chat_id=chat_id).all()
    history = [{"role": msg.role, "content": msg.content} for msg in messages]
    
    system_prompt = "You are an AI assistant. Keep responses short and concise."
    
    response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "system", "content": system_prompt}] + history
)
    
    ai_reply = response.choices[0].message.content.replace("\n", "<br>")
    bot_msg = Message(chat_id=chat_id, role="assistant", content=ai_reply)
    db.session.add(bot_msg)
    db.session.commit()
    
    return jsonify({"reply": ai_reply, "chat_id": chat_id})

@app.route("/chats", methods=["GET"])
def get_chats():
    chats = Chat.query.all()
    return jsonify({"chats": [{"id": chat.id, "title": chat.title} for chat in chats]})

@app.route("/messages/<int:chat_id>", methods=["GET"])
def get_messages(chat_id):
    messages = Message.query.filter_by(chat_id=chat_id).all()
    return jsonify({"messages": [{"role": msg.role, "content": msg.content} for msg in messages]})

@app.route("/new-chat", methods=["POST"])
def new_chat():
    chat_count = Chat.query.count() + 1
    new_chat = Chat(title=f"Chat {chat_count}")
    db.session.add(new_chat)
    db.session.commit()
    return jsonify({"id": new_chat.id, "title": new_chat.title})

if __name__ == "__main__":
    app.run(debug=True)
