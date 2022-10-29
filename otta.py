# selenium 4
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv
import time
import pathlib
import os

class DriverManager:
    def __init__(self):
        # Start-Process firefox -ArgumentList "-P", "otta-bot"
        options = FirefoxOptions()
        if (profile := os.getenv("PROFILE_FILE")) and (user := os.getenv("USER")):
            print(profile) 
            pathroot = pathlib.WindowsPath(r"C:\\")
            path = pathroot / "Users" / user / "AppData" / "Local" / "Mozilla" / "Firefox" / "Profiles" / profile
            options.add_argument("--profile")
            options.add_argument(str(path))
        self.driver = webdriver.Firefox(
            service=FirefoxService(GeckoDriverManager().install()), 
            options=options
        )
    
    def __enter__(self):
        return self.driver

    def __exit__(self, *args):
        self.driver.quit()

def main():
    load_dotenv()

    with DriverManager() as driver:
        print("Started")
        driver.get("https://app.otta.com/")
        time.sleep(300)

if __name__ == '__main__':
    main()
