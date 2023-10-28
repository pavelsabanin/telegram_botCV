import os
import time

import logging
import requests
import telegram
import sys

from http import HTTPStatus
from dotenv import load_dotenv

from exceptions import RequestException

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяем наличие токенов."""
    tokens = ('TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID', 'PRACTICUM_TOKEN')
    for token in tokens:
        if not globals()[token]:
            logging.critical(f"отсутствует нужный токен {token}")
            sys.exit(1)


def send_message(bot, message):
    """Попытка отправить сообщение."""
    logging.info('Отправляем сообщение')
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug("Сообщение отправлено")
    except telegram.error.TelegramError as error:
        logging.error(f"Ошибка отправки сообщения в Телеграм: {error}")


def get_api_answer(timestamp):
    """Получаем ответ от API."""
    payload = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise RequestException(f'Статус код: {response.status_code}')
        return response.json()
    except requests.RequestException as error:
        raise RequestException(f'Ошибка: {error}')


def check_response(response):
    """Проверяем ответ."""
    logging.info('Проверяем ответ')
    if not isinstance(response, dict):
        raise TypeError('Ответ API имеет неккоректный формат')
    if 'current_date' not in response:
        raise KeyError('отсутствует ключ "current_date"')
    if 'homeworks' not in response:
        raise TypeError('Отсутствует ключ "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ключ "homeworks" не имеет значения в формате списка')
    logging.info('Ответ получен и соответствует требованиям.')
    return response['homeworks']


def parse_status(homework):
    """Проверяем статус домашней работы."""
    logging.info('Проверяем статус работы')
    status = homework.get('status')
    if status is None:
        raise KeyError('нет ключа "status"')
    if not isinstance(status, str):
        raise KeyError('некорректный формат статуса')
    homework_name = homework.get('homework_name')
    if homework_name is None:
        raise KeyError('нет ключа "homework_name"')
    if not isinstance(homework_name, str):
        raise KeyError('"homework_name" не является строкой')
    verdict = HOMEWORK_VERDICTS.get(status)
    if verdict is None:
        raise KeyError(f'Недокументированный статус: {status}')
    logging.info('Статус домашней работы корректен')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = None
    while True:
        try:
            api_answer = get_api_answer(timestamp)
            homework = check_response(api_answer)
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
                timestamp = int(time.time())
            else:
                logging.debug("Статус не изменился")
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, filename='main.log',
                        format='%(asctime)s, %(levelname)s, %(name)s,'
                        '%(message)s, %(created)f')
    logging.StreamHandler(sys.stdout)
    logging.FileHandler('spam.log')
    main()
