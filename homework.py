import requests
import os
import time
import pprint
import logging
from exceptions import TokenMissingError
from dotenv import load_dotenv
import telegram
from telegram.error import BadRequest

load_dotenv()
pp = pprint.PrettyPrinter(indent=4)
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в случае успеха."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message,)
    except BadRequest as error:
        logging.error(f'Сообщения не отправляются: {error}')
        raise BadRequest('Сообщения не отправляются')
    else:
        logging.info(f'Бот успешно отправил сообщение:{message}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT,
                                     headers=HEADERS,
                                     params=params)
    if homework_statuses.status_code != 200:
        logging.error('Эндпоинт недоступен')
        raise ConnectionError(
            f'API оказался недоступен по адресу:{ENDPOINT}')
    return homework_statuses.json()


def check_response(response):
    """Проверяет ответ API на корректность."""
    if type(response) is not dict:
        logging.error('API вернул не словарь, а что-то другое.')
        raise TypeError('API вернул не словарь, а что-то другое.')
    if 'homeworks' not in response:
        logging.error('API вернул словарь, но в нем нет ключа homeworks.')
        raise KeyError('API вернул словарь, но в нем нет ключа homeworks.')
    homework = response.get('homeworks')
    if type(homework) is not list:
        logging.error('Список домашек почему-то оказался не списком')
        raise TypeError('Список домашек почему-то оказался не списком')
    return homework


def parse_status(homework):
    """Извлекает  статус домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        logging.error(f'API передал неизвестный ключ: {homework_status}.')
        raise KeyError('Бот не знает о ключ, который передал API.')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность токенов, необходимых для работы программы."""
    if PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID is not None:
        return True
    else:
        logging.critical('У НАС ПРОПАЛИ ТОКЕНЫ!!!')
        return False


def main():
    """Основная логика работы бота."""
    old_message = []
    if not check_tokens():
        raise TokenMissingError('Не хватает какого-то токена')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            logging.debug('Пока никаких обновлений, но зато все работает.')
            current_timestamp = int(time.time()) - RETRY_TIME
        except Exception as error:
            try:
                message = f'Сбой в работе программы: {error}'
                if message not in old_message:
                    old_message.clear()
                    send_message(bot, message)
                    old_message.append(message)
            except BadRequest as error:
                logging.error(f'Сообщения не отправляются: {error}')
                raise BadRequest('Сообщения не отправляются')
            else:
                logging.info(f'Отправлено сообщение об ошибке: {message}')
                time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('homework.log', encoding='UTF-8')],
        format=(
            '%(asctime)s, %(levelname)s, %(message)s, %(lineno)s'
        ))
    main()
