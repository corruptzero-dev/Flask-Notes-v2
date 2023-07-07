from flask import Flask, jsonify, request
import logging
from flask_sqlalchemy import SQLAlchemy
from flask_swagger_ui import get_swaggerui_blueprint
from sqlalchemy.exc import SQLAlchemyError
from marshmallow import ValidationError
from flask_login import LoginManager, current_user, login_user, logout_user, login_required
from werkzeug.security import check_password_hash
from flask_restx import Api, Resource, fields

from config import Config
from models import db, Note, User
from schemas import NoteSchema

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

# Инициализация Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

note_schema = NoteSchema()
notes_schema = NoteSchema(many=True)

# Настройка логгера
logging.basicConfig(level=logging.INFO)  # Уровень логирования INFO

# Создание объекта логгера
logger = logging.getLogger(__name__)

# Создание базы данных и таблицы
with app.app_context():
    db.create_all()

# Создание экземпляра Api
api = Api(app, version='1.0', title='Notes API', description='API для управления заметками')

# Маршрут для регистрации нового пользователя
@api.route('/register')
class RegisterResource(Resource):
    def post(self):
        try:
            logger.info('Получен запрос на регистрацию')

            data = request.get_json()
            username = data['username']
            password = data['password']

            if User.query.filter_by(username=username).first():
                logger.info(f'Имя пользователя уже занято: {username}')
                return jsonify({'error': f'Имя пользователя уже занято: {username}'}), 400

            user = User(username=username, password=password)
            db.session.add(user)
            db.session.commit()
            logger.info('Пользователь успешно зарегистрирован!')
            return jsonify({'message': 'Пользователь успешно зарегистрирован!'}), 201  # HTTP-статус 201 (Created)
        except SQLAlchemyError as e:
            logger.error(f'Ошибка при регистрации пользователя: {str(e)}')
            return jsonify({'error': f'Ошибка при регистрации пользователя! {str(e)}'}), 500  # HTTP-статус 500 (Internal Server Error)

# Маршрут для входа пользователя в систему
@api.route('/login')
class LoginResource(Resource):
    def post(self):
        try:
            data = request.get_json()
            username = data['username']
            password = data['password']

            user = User.query.filter_by(username=username).first()

            if not user or not check_password_hash(user.password_hash, password):
                logger.error('Неправильное имя пользователя или пароль')
                return jsonify({'error': 'Неправильное имя пользователя или пароль!'}), 401  # HTTP-статус 401 (Unauthorized)

            login_user(user)

            logger.info('Вход в систему выполнен успешно')
            return jsonify({'message': 'Вход в систему выполнен успешно!'})
        except SQLAlchemyError as e:
            logger.error(f'Ошибка при входе в систему: {str(e)}')
            return jsonify({'error': f'Ошибка при входе в систему! {str(e)}'}), 500  # HTTP-статус 500 (Internal Server Error)
        
# Маршрут для выхода пользователя из системы
@api.route('/logout')
class LogoutResource(Resource):
    @login_required
    def post(self):
        logout_user()
        logger.info('Выход из системы выполнен успешно')
        return jsonify({'message': 'Выход из системы выполнен успешно!'})

# Маршрут для работы с заметками
@api.route('/notes')
class NotesResource(Resource):
    @api.expect(api.model('Note', {
        'title': fields.String(required=True, description='Заголовок заметки'),
        'content': fields.String(required=True, description='Содержимое заметки')
    }))
    @login_required
    def post(self):
        try:
            data = request.get_json()
            title = data['title']
            content = data['content']

            note = Note(title=title, content=content, user_id=current_user.id)
            db.session.add(note)
            db.session.commit()

            logger.info('Заметка успешно создана')
            return jsonify({'message': 'Заметка успешно создана!'}), 201  # HTTP-статус 201 (Created)
        except ValidationError as e:
            logger.error(f'Ошибка при создании заметки: {str(e)}')
            return jsonify({'error': f'Ошибка при создании заметки! {str(e)}'}), 400  # HTTP-статус 400 (Bad Request)
        except SQLAlchemyError as e:
            logger.error(f'Ошибка при создании заметки: {str(e)}')
            return jsonify({'error': f'Ошибка при создании заметки! {str(e)}'}), 500  # HTTP-статус 500 (Internal Server Error)

    @login_required
    def get(self):
        notes = Note.query.filter_by(user_id=current_user.id).all()
        result = notes_schema.dump(notes)

        logger.info('Заметки успешно получены')
        return jsonify(result), 200  # HTTP-статус 200 (OK)

# Маршрут для работы с отдельной заметкой
@api.route('/notes/<int:id>')
class NoteResource(Resource):
    @login_required
    def get(self, id):
        note = Note.query.get(id)

        if not note or note.user_id != current_user.id:
            logger.error('Заметка не найдена')
            return jsonify({'error': 'Заметка не найдена!'}), 404  # HTTP-статус 404 (Not Found)

        result = note_schema.dump(note)

        logger.info('Заметка успешно получена')
        return jsonify(result), 200  # HTTP-статус 200 (OK)

    @login_required
    def put(self, id):
        note = Note.query.get(id)

        if not note or note.user_id != current_user.id:
            logger.error('Заметка не найдена')
            return jsonify({'error': 'Заметка не найдена!'}), 404  # HTTP-статус 404 (Not Found)

        data = request.get_json()
        title = data.get('title', note.title)
        content = data.get('content', note.content)

        note.title = title
        note.content = content

        try:
            db.session.commit()

            logger.info('Заметка успешно обновлена')
            return jsonify({'message': 'Заметка успешно обновлена!'})
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f'Ошибка при обновлении заметки: {str(e)}')
            return jsonify({'error': f'Ошибка при обновлении заметки! {str(e)}'}), 500  # HTTP-статус 500 (Internal Server Error)

    @login_required
    def delete(self, id):
        note = Note.query.get(id)

        if not note or note.user_id != current_user.id:
            logger.error('Заметка не найдена')
            return jsonify({'error': 'Заметка не найдена!'}), 404  # HTTP-статус 404 (Not Found)

        try:
            db.session.delete(note)
            db.session.commit()

            logger.info('Заметка успешно удалена')
            return jsonify({'message': 'Заметка успешно удалена!'})
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f'Ошибка при удалении заметки: {str(e)}')
            return jsonify({'error': f'Ошибка при удалении заметки! {str(e)}'}), 500  # HTTP-статус 500 (Internal Server Error)

# Маршрут для Swagger UI
SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.json'
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={'app_name': 'Notes API'})
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

# Обработка ошибок
@app.errorhandler(400)
def bad_request(error):
    logger.error(f'HTTP 400 (Неправильный запрос)')
    return jsonify({'error': 'Неправильный запрос!'}), 400

@app.errorhandler(404)
def not_found(error):
    logger.error(f'HTTP 404 (Ресурс не найден)')
    return jsonify({'error': 'Ресурс не найден!'}), 404

@app.errorhandler(500)
def internal_server_error(error):
    logger.error(f'HTTP 500 (Внутренняя ошибка сервера!)')
    return jsonify({'error': 'Внутренняя ошибка сервера!'}), 500

if __name__ == '__main__':
    app.run()
