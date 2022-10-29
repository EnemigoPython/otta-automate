from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from webdriver_manager.firefox import GeckoDriverManager
from dotenv import load_dotenv
import traceback
import pathlib
import logging
import sys
import os

FILENAME = os.path.basename(__file__)

def get_logger():
    logger = logging.getLogger(FILENAME)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("otta-automate.log")
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

class NoCredentialsException(Exception):
    """A custom error to reject execution if the proper env variables aren't set"""
    def __init__(self):
        super().__init__("You need 'PROFILE_FILE' and 'USER' environment variables set to run this script")

class DriverManager:
    """A wrapper to run the Selenium driver as a context manager and inject our logger"""
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        try:
            options = FirefoxOptions()
            if (profile := os.getenv("PROFILE_FILE")) and (user := os.getenv("USER")):
                self.logger.info(f"Using profile found for {user}: {profile}")
                pathroot = pathlib.WindowsPath(r"C:\\")
                path = pathroot / "Users" / user / "AppData" / "Local" / "Mozilla" / "Firefox" / "Profiles" / profile
                options.add_argument("--profile")
                options.add_argument(str(path))
            else:
                raise NoCredentialsException()
            self.driver = webdriver.Firefox(
                service=FirefoxService(GeckoDriverManager().install()), 
                options=options
            )
            self.driver.implicitly_wait(30)
            self.logger.info("Driver initialised")
        except Exception as e:
            self.logger.error(f"Crashed on startup with a {repr(e.__class__.__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
            raise e
    
    def __enter__(self):
        return self.driver

    def __exit__(self, *exc):
        if any(exc):
            # we get the name of an exception with e.__class__.__name__, but exc[0] is not of type Exception
            self.logger.error(f"Script crashed with a {repr(exc[0].__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
        else:
            self.logger.info("Script ran to completion: exiting")
        self.driver.quit()

class JobApplication:
    """In this class we will gather the data and formulate our job application"""
    def __init__(self, driver: webdriver.Firefox):
        self.job_title = self.page_data_text(driver, "job-title")
        self.company_title = self.page_data_text(driver, "ottas-take").split("Otta's take on ")[1]
        self.technologies = self.page_data_text(driver, "job-technology-used").split("\n")
        self.office_requirements = self.page_data_text(driver, "office-day-requirements")
        self.salary = self.page_data_text(driver, "salary-section").split("k")[0] + 'k'
        self.industries = self.page_data_text_list(driver, "company-sector-tag")
        self.benefits = self.page_data_text_list(driver, "company-benefit-bullet")
        self.values = self.page_data_text_list(driver, "company-value-bullet")
        self.job_involves = self.page_data_text_list(driver, "job-involves-bullet")
        self.job_requirements = self.page_data_text_list(driver, "job-requirements-bullet")
        self.web_link = self.get_web_link(driver)
        breakpoint()

    def page_element(self, driver: webdriver.Firefox, el: str):
        try:
            return driver.find_element(By.XPATH, f"//*[@data-testid='{el}']")
        except:
            return None

    def page_data_text(self, driver: webdriver.Firefox, el: str):
        try:
            return driver.find_element(By.XPATH, f"//*[@data-testid='{el}']").text
        except:
            return None

    def page_data_text_list(self, driver: webdriver.Firefox, el: str):
        try:
            return [i.text for i in driver.find_elements(By.XPATH, f"//*[@data-testid='{el}']")]
        except:
            return []

    def get_web_link(self, driver: webdriver.Firefox):
        try:
            job_card = driver.find_element(By.XPATH, "//*[@data-testid='job-card']")
            link = job_card.find_element(By.TAG_NAME, "a")
            return link.get_attribute("href")
        except:
            return None

def main():
    logger = get_logger()
    logger.info(f"Started execution of {FILENAME}")
    if "--auto" in sys.argv:
        logger.info("This execution was run automatically")
    load_dotenv()

    with DriverManager(logger) as driver:
        driver.get("https://app.otta.com/jobs/theme/apply-via-otta")
        application = JobApplication(driver)


if __name__ == '__main__':
    main()
