import requests
import os
import time
import pprint
import logging
from exceptions import (TokenMissingError, EmptyResponseError,
                        NoApiResponseError)
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
VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в случае успеха."""
    logging.info(f'Начинаем отправлять сообщение. Содержание: {message}')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID,
                         text=message,)
    except BadRequest:
        raise BadRequest('Сообщения не отправляются')
    else:
        logging.info(f'Бот успешно отправил сообщение:{message}')


def get_api_answer(current_timestamp):
    """Делает запрос к единственному эндпоинту API-сервиса."""
    timestamp = current_timestamp or int(time.time())
    request_params = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': dict(from_date=timestamp),
    }
    try:
        homework_statuses = requests.get(**request_params)
    except Exception as error:
        logging.error(f'Ошибка {error} при получении ответа:{request_params}')
    else:
        if homework_statuses.status_code == 200:
            return homework_statuses.json()
        else:
            message = (f'При запросе к апи {request_params} не получен ответ.'
                       f'Статус запроса:{homework_statuses.status_code}')
            raise Exception(message)


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not response:
        logging.error('APi не присылает словарь.')
        raise NoApiResponseError('APi не присылает словарь.')
    if len(response) == 0:
        logging.debug('API принес пустой словарь.')
        raise EmptyResponseError('Api принес пустой словарь.')
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
    """Извлекает статус домашней работы."""
    if not homework:
        logging.error('API не передал инфу о статусе домашней работы.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in VERDICTS:
        logging.error(f'API передал неизвестный ключ: {homework_status}.')
        raise KeyError('Бот не знает о ключ, который передал API.')
    verdict = VERDICTS[homework_status]
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
    if not check_tokens():
        raise TokenMissingError('Не хватает какого-то токена')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    prev_report = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            if homework:
                current_report = {'status': homework[0]}
                message = parse_status(homework[0])
                if current_report != prev_report:
                    send_message(bot, message)
                    prev_report = current_report.copy()
            else:
                logging.debug(
                    'Пока никаких обновлений, но зато все работает.')
            current_timestamp = int(time.time()) - RETRY_TIME
        except Exception as error:
            try:
                message = f'Сбой в работе программы: {error}'
                current_report = {'report': error}
                if current_report != prev_report:
                    send_message(bot, message)
                    prev_report = current_report.copy()
                else:
                    logging.info(f'Ошибка {error} повторилась.')
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
