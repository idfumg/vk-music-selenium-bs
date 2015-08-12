#!/usr/bin/env python

'''
Maybe use raw requests without selenium, sometime...
'''

from os import path
from multiprocessing import Process, Queue

import requests

from selenium import webdriver
#from selenium.common.exceptions import NoSuchElementException

from bs4 import BeautifulSoup

LOGIN = 'email@gmail.com'
PASSWORD = 'password'
URL = 'https://vk.com/audios......'

PROCESSNUM = 3
DOWNLOAD_TRY_COUNT = 3
CHUNK_SIZE = 500000
DIRECTORY = '/home/user/Downloads'

def login(browser):
    '''
    If exception raises - fall.
    '''
    email = browser.find_element_by_name('email')
    email.click()
    email.clear()
    email.send_keys(LOGIN)

    password = browser.find_element_by_name('pass')
    password.click()
    password.clear()
    password.send_keys(PASSWORD)

    buttons = browser.find_elements_by_class_name('flat_button')
    for button in buttons:
        if 'quick_login' in button.get_attribute('onclick'):
            button.click()
            break


def is_login_window(browser):
    return 'login.php' in browser.current_url


def scroll_maximum_down(browser):
    script = "window.scrollTo(0, document.body.scrollHeight);"
    prev_size = len(browser.page_source)

    while True:
        browser.execute_script(script)

        new_size = len(browser.page_source)
        if (prev_size != new_size):
            prev_size = new_size
        else:
            break


def find_dummy(tag, selector, fn):
    return getattr(tag, fn)(selector)


def find_elem(tag, selector):
    return find_dummy(tag, selector, 'select')[0]


def find_elems(tag, selector):
    return find_dummy(tag, selector, 'select')


def find_audio_divs(html):
    '''
    Using iterators from beautiful soup - many divs.
    '''
    div = html.find('div', { 'class': 'audio fl_l' })

    while div:
        yield div
        div = div.find_next_sibling('div', 'audio fl_l')


def find_url(audio_div):
    input_elem = find_elem(audio_div, 'div.play_btn.fl_l input')
    return input_elem.get('value')


def find_group(audio_div):
    return find_elem(audio_div, 'div.title_wrap.fl_l b a').text


def find_name(audio_div):
    span = find_elem(audio_div, 'span.title')

    try:

        return find_elem(span, 'a').text

    except IndexError as e:
        return span.text


def find_url_filename(audio_div):
    filename = "{}/{}-{}".format(DIRECTORY,
                                 find_group(audio_div),
                                 find_name(audio_div))
    filename = filename[:100] + '.mp3'

    return (find_url(audio_div), filename)


def download_file_dummy(url, filename):
    print(filename)

    try:

        r = requests.head(url)

    except requests.exceptions.RequestException:
        return False

    size = int(r.headers['content-length'])

    if path.exists(filename) and path.getsize(filename) == size:
        return True

    try:

        r = requests.get(url)

        with open(filename, 'wb') as fd:
            for buf in r.iter_content(CHUNK_SIZE):
                if not buf:
                    continue

                fd.write(buf)

    except (requests.exceptions.RequestException, FileNotFoundError):
        return False

    return True


def download_file(queue):
    mp3 = []

    while True:
        record = queue.get()

        if not record:
            break

        rc = False
        for i in range(DOWNLOAD_TRY_COUNT):
            rc = download_file_dummy(*record)
            if rc:
                break

        if not rc:
            print('Cant download:', record)
            mp3.append(record)

    if mp3:
        while True:
            print('Try to repeat download {} files...'.format(len(mp3)))
            for composition in mp3[:]:
                if download_file_dummy(*composition):
                    mp3.remove(composition)


def main():
    # disable images, stylesheets, flash.
    firefox_profile = webdriver.FirefoxProfile()
    firefox_profile.set_preference('permissions.default.stylesheet', 2)
    firefox_profile.set_preference('permissions.default.image', 2)
    firefox_profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')

    browser = webdriver.Firefox(firefox_profile=firefox_profile)
    browser.get(URL)

    if is_login_window(browser):
        login(browser)

    scroll_maximum_down(browser)

    soup = BeautifulSoup(browser.page_source, 'lxml')
    browser.quit()

    queue = Queue()
    processes = []
    for num in range(PROCESSNUM):
        process = Process(target=download_file, args=(queue,))
        processes.append(process)
        process.daemon = True
        process.start()

    for audio_div in find_audio_divs(soup):
        queue.put(find_url_filename(audio_div), True, 30)

    for num in range(PROCESSNUM):
        queue.put(None)

    queue.close()

    for process in processes:
        process.join()


if __name__ == "__main__":
    main()
