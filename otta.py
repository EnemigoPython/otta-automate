from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from webdriver_manager.firefox import GeckoDriverManager
from functools import partial
from dotenv import load_dotenv
from enum import Enum, auto
import traceback
import pathlib
import logging
import sys
import os

FILENAME = os.path.basename(__file__)
AUTO = "--auto" in sys.argv
DEBUG = "--debug" in sys.argv

def get_logger():
    logger = logging.getLogger(FILENAME)
    logger.setLevel(logging.INFO)
    handler = logging.FileHandler("otta-automate.log")
    formatter = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

class InputType(Enum):
    TEXTAREA = auto()
    CHECKBOX = auto()
    DROPDOWN = auto()

class QuestionGist(Enum):
    COVER_LETTER = auto()
    AFFIRM_RIGHT_TO_WORK = auto()
    NEED_SPONSORSHIP = auto()
    UNKNOWN = auto()

def extract_question_info(el: WebElement):
    """
    We want to find out the meaning of the question and the type of input so we can boil it down
    to 
    """
    pass

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
        self.driver.find_element_by_data_id = partial(self.find_element_by_data_id, driver=self.driver)
        self.driver.find_elements_by_data_id = partial(self.find_elements_by_data_id, driver=self.driver)
        return self.driver

    def __exit__(self, *exc):
        if any(exc):
            # we get the name of an exception with e.__class__.__name__, but exc[0] is not of type Exception
            self.logger.error(f"Script crashed with a {repr(exc[0].__name__)}: view traceback below")
            self.logger.error(traceback.format_exc())
        else:
            self.logger.info("Script ran to completion: exiting")
        self.driver.quit()

    @staticmethod
    def find_element_by_data_id(id: str, driver: webdriver.Firefox):
        """Find a SINGLE element using an xpath pattern on the `data-testid` tag"""
        return driver.find_element(By.XPATH, f"//*[@data-testid='{id}']")

    @staticmethod
    def find_elements_by_data_id(id: str, driver: webdriver.Firefox):
        """Find MULTIPLE elements using an xpath pattern on the `data-testid` tag"""
        return driver.find_elements(By.XPATH, f"//*[@data-testid='{id}']")

class JobApplication:
    """Used to gather the data and formulate our job application"""
    def __init__(self, driver: webdriver.Firefox):
        self.job_title = self.page_data_text(driver, "job-title") or None
        try:
            self.company_title = self.page_data_text(driver, "ottas-take").split("Otta's take on ")[-1]
        except IndexError:
            self.company_title = None
        self.technologies = self.page_data_text(driver, "job-technology-used").split("\n") or None
        self.office_requirements = self.page_data_text(driver, "office-day-requirements") or None
        self.salary = self.page_data_text(driver, "salary-section").split("k")[0] or None
        if self.salary is not None:
            self.salary += 'k'
        self.location_description = self.page_data_text_list(driver, "job-location-tag")
        self.industries = self.page_data_text_list(driver, "company-sector-tag")
        self.benefits = self.page_data_text_list(driver, "company-benefit-bullet")
        self.values = self.page_data_text_list(driver, "company-value-bullet")
        self.job_involves = self.page_data_text_list(driver, "job-involves-bullet")
        self.job_requirements = self.page_data_text_list(driver, "job-requirements-bullet")
        self.web_link = self.get_web_link(driver)

    def page_data_text(self, driver: webdriver.Firefox, el: str):
        try:
            return driver.find_element_by_data_id(el).text
        except:
            print(traceback.format_exc())
            return ""

    def page_data_text_list(self, driver: webdriver.Firefox, el: str):
        try:
            return [i.text for i in driver.find_elements_by_data_id(el)]
        except:
            return []

    def get_web_link(self, driver: webdriver.Firefox):
        try:
            job_card = driver.find_element_by_data_id("job-card")
            link = job_card.find_element(By.TAG_NAME, "a")
            return link.get_attribute("href")
        except:
            return None

    def minimum_application_requirement(self):
        return self.job_title is not None and self.company_title is not None

    def answer(self, questions: list[str]):
        pass

def main():
    logger = get_logger()
    logger.info(f"Started execution of {FILENAME}")
    logger.info(f"Execution mode: '{'automatic' if AUTO else 'manual'}', debug mode: '{'on' if DEBUG else 'off'}'")
    load_dotenv()

    with DriverManager(logger) as driver:
        driver.get("https://app.otta.com/jobs/theme/apply-via-otta")
        applications_in_session = 0
        while (application := JobApplication(driver)).minimum_application_requirement():
            if DEBUG:
                logger.info(f"Entering debugger at '{application.company_title}' listing page")
                breakpoint()
            buttons_panel = driver.find_element_by_data_id("desktop-action-panel")
            buttons_panel.find_elements(By.TAG_NAME, "button")[1].click()
            apply_modal = driver.find_element_by_data_id("apply-content")
            apply_modal.find_element(By.TAG_NAME, "button").click()
            question_elements = driver.find_elements_by_data_id("application-question-card")
            questions = [i.text for i in question_elements]
            application.answer(questions)
            if DEBUG:
                logger.info(f"Entering debugger at '{application.company_title}' application page")
                breakpoint()
            for question_element in question_elements:
                pass
            applications_in_session += 1
        if applications_in_session > 0:
            logger.info(f"{applications_in_session} job applications made in this session")
        else:
            logger.warning("No job applications made - might be an error or new posts might have been depleted")
            if DEBUG:
                logger.warning("Entering debugger to investigate incident")
                breakpoint()


if __name__ == '__main__':
    main()
