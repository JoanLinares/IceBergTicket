"""
IBTicket - Plataforma de Gestió de Tickets amb Data Warehouse
"""
import os
import psycopg2
from dotenv import load_dotenv
from flask import Flask

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(
    __name__,
    template_folder='src/web/templates',
    static_folder='src/web/static'
)

app.config['DATABASE_URL'] = DATABASE_URL


# CORS
@app.after_request
def cors(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# Registrar rutes
from src.api.routers import api_blueprint
from src.web.routers import web_blueprint

app.register_blueprint(api_blueprint, url_prefix='/api/v1')
app.register_blueprint(web_blueprint, url_prefix='/')


def test_connection():
    """Test Supabase PostgreSQL connection"""
    try:
        connection = psycopg2.connect(DATABASE_URL)
        print("Connection successful!")
        
        cursor = connection.cursor()
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print("Current Time:", result)

        cursor.close()
        connection.close()
        print("Connection closed.")
        return True

    except Exception as e:
        print(f"Failed to connect: {e}")
        return False


if __name__ == "__main__":
    test_connection()
    port = int(os.getenv('PORT', 5000))
    print(f"⚡️ IBTicket running at http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=True)
