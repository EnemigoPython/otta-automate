# selenium 4
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv
import time
import os

class DriverManager:
    def __init__(self):
        options = FirefoxOptions()
        if profile := os.getenv("PROFILE_PATH"):
            options.add_argument(rf'--profile={profile}')
        self.driver = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=options)
    
    def __enter__(self):
        return self.driver

    def __exit__(self, *args):
        self.driver.quit()

load_dotenv()

with DriverManager() as driver:
    driver.get("https://app.otta.com/")
    time.sleep(30)
